import discord
from discord.ext import commands
import aiohttp
import bs4
from bs4 import BeautifulSoup as soup
import datetime
from datetime import datetime as dt
import re
import math
from typing import Tuple, List

headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}

class Ebay(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.command(aliases=['pc','chk','price','pricecheck'])
    async def check(self, ctx, *, search_term):
        """Gets the average price of an item from Ebay
        
        Usage example:
        !check dell xps 15 -dead -broken -scratched
        words beginning with `-` are added to the list of words to be filtered out"""
        
        # Disable this cog, as the eBay integration is broken.
        await ctx.send("Bot machine :b:roke")
        return
        
        search_term = search_term.lower()
        # If the searchterm with boolean operators removed is less than 6 characters
        if len(' '.join([i for i in search_term.split(' ') if not i.startswith('-')])) < 6:
            embed = self.error_embed('length')
            await ctx.send(embed=embed)
            return

        async with ctx.channel.typing():
            filtered_term, filtered_words = self.get_filter(search_term)
            page = await self.make_soup(filtered_term)
            product_list = page.find('ul', {'class': 'srp-results'}).find_all('li', {'class':'s-item'})
            products = [self.get_product_info(i) for i in product_list if self.get_product_info(i)]
            # Removes listings that don't pass the filter
            filtered_listings = [i for i in products if not self.filtered_out(i['title'], filtered_words)]
            if not filtered_listings: # If no listings pass filter
                await self.no_results(ctx, search_term)
                return
            # If there are listings that passed the filter
            # Get the 25th, 50th and 75th percentiles of the price range
            quartiles = self.find_quartiles([i['price'] for i in filtered_listings])
            box_plot = [i['price'] for i in filtered_listings if quartiles[0] <= i['price'] <= quartiles [2]]
            average = sum(box_plot) / len(box_plot)
            # Get variance
            variance = self.determine_variance(box_plot)
            # Make and send the embed
            embed_details = {"title": f"Results for {filtered_term}",
                            "range": [quartiles[0], quartiles[2]],
                            "median": quartiles[1],
                            "average": average,
                            "variance": variance,
                            "num_of_items": len(box_plot),
                            "filtered_words": [i.strip('-') for i in search_term.split(' ') if i.startswith('-')]}
            embed = self.make_embed(embed_details)
            await ctx.send(embed=embed)

    def filtered_out(self, title: str, filtered_words: list) -> bool:
        """Checks whether any words from the filter are in the listing title"""
        for word in title.split(' '):
            if word.lower() in filtered_words:
                return True
        return False

    def make_embed(self, data: dict) -> discord.Embed:
        """Generate an embed object"""
        colour = self.get_colour(data)

        def as_price(num):
            """Formats a number as a price"""
            return '%.2f' % num if round(num, 2) == int(num) or num < 1 else int(num)

        embed = discord.Embed(title=data['title'], colour=colour)
        embed.add_field(name='Range', value=f"£{as_price(data['range'][0])} - £{as_price(data['range'][1])}", inline=True)
        embed.add_field(name='Median', value=f"£{as_price(data['median'])}", inline=True)
        embed.add_field(name='Average', value=f"£{as_price(data['average'])}", inline=True)
        embed.add_field(name='Variance', value=f"{data['variance']}%", inline=True)
        embed.add_field(name='Number of items', value=data['num_of_items'], inline=True)
        if data['filtered_words']:
            embed.add_field(name="Filtered words", value='\n'.join(data['filtered_words']), inline=False)
        return embed

    async def make_soup(self, search_term):
        """Returns a BeautifulSoup object from an ebay search"""
        url = f"https://www.ebay.co.uk/sch/i.html?_from=R40&_nkw={search_term}&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1&_ipg=200&LH_ItemCondition=4&LH_PrefLoc=1"
        async with aiohttp.ClientSession() as session:
            data = await session.get(url, headers=headers)
            page_text = await data.text()
            await session.close()
        return soup(page_text, 'html.parser')

    def get_filter(self, search_term: str) -> Tuple[str, list]:
        """Filters out listings with certain words"""
        # define filtered words
        search_term = search_term.split(' ')
        edge_cases = {
            'max': ['amd', 'intel'],
            'pc': ['case'],
            'cooler': ['aio', 'air', 'liquid']
        }
        words = [
            'pro', 'plus', 'max', 'super', 'bundle', 'combo', 'faulty',
            'ti', 'xt', 'spare', 'spares', 'repair', 'repairs', 'cooler',
            'pc', 'damaged', 'broken', 'with', 'for', 'dell', 'hp',
            'gigabyte', 'acer', 'lenovo', 'asus', 'alienware', 'parts',
            'charger', 'dock', 'case', 'replicator', 'keyboard', 'mini',
            'lite', 'crack', 'cracked', '5g'
        ]
        words.extend([i.strip('-').lower() for i in search_term if i.startswith('-')])
        # remove duplicates
        words = list(dict.fromkeys(words))
        # collect words that were added to the filter
        filtered_words = [i for i in search_term if i.startswith('-')]
        # search term with boolean operators removed
        filtered_search_term = [i for i in search_term if not i.startswith('-')]
        # remove words in search from filter
        for word in words:
            if word in filtered_search_term:
                words.remove(word)
                if word in filtered_words:
                    filtered_words.remove(word)
        # remove words from filter if searching for certain things
        for key in edge_cases.keys():
            for word in edge_cases[key]:
                if word in filtered_search_term and key in words:
                    words.remove(key)
        return ' '.join(filtered_search_term), words

    def get_product_info(self, product) -> dict:
        """Fetches the product info from a product listing as a dict"""
        try:
            d = {}
            d['title'] = product.find('h3', {'class': 's-item__title'}).contents[-1]
            d['url'] = product.find('a')['href'].split('?')[0]
            d['image'] = product.find('img')['src']
            d['price'] = self.parse_price(product)
            if not d['price']: # If £ not in price
                return None
            d['ended_date'] = self.parse_date(product)
            d['id'] = d['url'].split('/')[-1].split('?')[0]
            # Type enforcement on dictionary object
            return {'title': str(d['title']), 'url': str(d['url']), 'image': str(d['image']), 'price': d['price'], 'ended_date': d['ended_date'], 'id': str(d['id'])}
        except:
            return {}

    def parse_price(self, product):
        """Retrieves the full price from a product listing"""
        log_reg = re.compile('\+\s£(\d+\.\d+).*')
        base_price = product.find('span', {'class': 's-item__price'}).contents[0].contents[0]
        if '£' not in base_price: # Ignore foreign listings
            return None
        base_price = float(product.find('span', {'class': 's-item__price'}).contents[0].contents[0].strip('£').replace(',','')) # Find the listing price
        if not product.find('span', {'class': 's-item__logisticsCost'}): # If there is no postage price return the listing price
            return base_price
        logistics = product.find('span', {'class': 's-item__logisticsCost'}).contents[0]
        if type(logistics) is bs4.element.NavigableString:
            if logistics.lower() in ['free postage', 'postage not specified']: # Ignore common strings
                postage = 0
            elif log_reg.match(logistics): # Find the price if there's a regex match
                postage = float(log_reg.match(logistics).group(1))
            else:
                postage = 0
        else: # If type is not NavigableString (most likely to be Tag)
            logistics = logistics.contents[-1]
            if log_reg.match(logistics): # Apply regex
                postage = float(log_reg.match(logistics).group(1))
            else: # Account for edge cases
                postage = 0
        return base_price + postage

    def parse_date(self, product) -> datetime.datetime:
        """Retrieves the ended date from a product listing"""
        # Fetch the date string
        base = product.find('span', {'class': 's-item__ended-date'}).contents[0]
        # Interpret month and year
        month_regex = re.compile("\d{2}-(\w*)\W\d{2}:\d{2}")
        matched_month = month_regex.match(base).group(1)
        months = {datetime.date(2020, i, 1).strftime('%B')[:3]: str(i) for i in range(1,13)}
        year = dt.now().year if int(months[matched_month]) <= dt.now().month else dt.now().year - 1
        # Convert to datetime.datetime object
        date_string = f"{year} {base.replace(matched_month, months[matched_month])}"
        return dt.strptime(date_string, '%Y %d-%m %H:%M')

    def find_quartiles(self, num_array: List[float]) -> List[float]:
        """Find quartile positions from a list of prices"""
        size = len(num_array)
        if size == 0:
            quartiles = [0,0,0]
        else:
            sorted_array = sorted(num_array)
            lower_pos, median_pos, upper_pos = self.find_quartile_postions(size)
            # Floor so can work in arrays
            floored_lower_pos = math.floor(lower_pos)
            floored_median_pos = math.floor(median_pos)
            floored_upper_pos = math.floor(upper_pos)
            # If position is an integer, the quartile is the elem at position
            # else the quartile is the mean of the elem & the elem one position above
            lower_quartile = sorted_array[floored_lower_pos] if (lower_pos % 1 == 0) else (sorted_array[floored_lower_pos] + sorted_array[floored_lower_pos + 1]) / 2
            median = sorted_array[floored_median_pos] if (median_pos % 1 == 0) else (sorted_array[floored_median_pos] + sorted_array[floored_median_pos + 1]) / 2
            upper_quartile = sorted_array[floored_upper_pos] if (upper_pos % 1 == 0) else (sorted_array[floored_upper_pos] + sorted_array[floored_upper_pos + 1]) / 2
            quartiles = [round(i, 2) for i in [lower_quartile, median, upper_quartile]]
        return quartiles

    def find_quartile_postions(self, size: int) -> Tuple[float]:
        """Determines quartile positions from """
        if size == 1:
            # All quartiles are the first (only) element
            return 0, 0, 0
        elif size == 2:
            # Lower quartile is first element, Upper quartile is second element, Median is average
            return 0, 0.5, 1
        else:
            # Lower quartile is element at 1/4th position, median at 1/2th, upper at 3/4
            # Quartiles can be between positions if size + 1 is not divisible by 4
            return (size + 1) / 4 - 1, (size + 1) / 2 - 1, 3 * (size + 1) / 4 - 1

    def determine_variance(self, price_range: List[float]) -> float:
        """Get the variance of a price range"""
        mean = sum(price_range) / len(price_range) # Get the mean price
        price_range.sort()
        variance = (price_range[-1] - price_range[0]) / mean * 100 # Range over mean as a percentage
        return round(variance, 2)

    def get_colour(self, data: dict) -> int:
        """Determines embed colour based on variance amount"""
        if 0 <= data['variance'] < 16.6:
            return 0x78B159 # green
        elif 16.6 <= data['variance'] < 33.3:
            return 0xFFAC33 # yellow
        elif 33.3 <= data['variance']:
            return 0xDD2E44 # red

    async def no_results(self, ctx, search_term: str):
        filtered_term = [i for i in search_term.split(' ') if not i.startswith('-')]
        desc = [f"No results found for `{filtered_term}`"]
        desc.append("Make sure to include manufacturer for best results")
        desc.append("If you feel this is in error, message one of the bot developers")
        embed = discord.Embed(title='No results found', colour=0xE53238, description='\n'.join(desc))
        filtered_words = [i[1:] for i in search_term.split(' ') if i.startswith('-')]
        if filtered_words:
            embed.add_field(name="Filtered words", value='\n'.join(filtered_words), inline=True)
        await ctx.send(embed=embed)
        return

    def error_embed(self, error: str) -> discord.Embed:
        """Generates an error embed"""
        errors = {
            'length': 'Your search must be more than 6 characters',
            'timeout': 'The server failed to fetch a result'
        }
        return discord.Embed(title='Error', description=errors[error], colour=0xDD2E44)

def setup(client):
    client.add_cog(Ebay(client))
