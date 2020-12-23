import discord
from discord.ext import commands
import aiohttp
import asyncio
import bs4
from bs4 import BeautifulSoup as soup
import datetime
from datetime import datetime as dt
import re
import math
from typing import Tuple, List, Union

headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}


class ListingParsingFailed(Exception):
    """Raised if parsing any part of the listing fails"""
    pass


class Listing:
    def __init__(self, product):
        self.title = str(product.find('h3', {'class': 's-item__title'}).contents[-1])
        self.url = str(product.find('a')['href'].split('?')[0])
        self.image = str(product.find('img')['src'])
        self.id = self.url.split('/')[-1].split('?')[0]


class SoldListing(Listing):
    def __init__(self, product):
        super().__init__(product)
        self.price = self.parse_price(product)
        if not self.price:
            raise ListingParsingFailed("Failed to parse listing")
        self.ended_date = self.parse_date(product)
        self.embed = self.make_listing_embed()

    def parse_price(self, product) -> float:
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

    def make_listing_embed(self) -> discord.Embed:
        """Generate an embed for the listing"""
        embed = discord.Embed(title=self.title, url=self.url)
        embed.add_field(name="Price", value="£{:,.2f}".format(self.price), inline=True)
        embed.add_field(name="Ended at", value=self.ended_date.strftime("%d-%m-%y"), inline=True)
        embed.set_thumbnail(url=self.image)
        return embed


class EbaySearch:
    def __init__(self, search_term):
        self.original_term = search_term
        self.filtered_term, self.filtered_words = self.get_filter()

    def get_statistics(self):
        self.statistics = SearchStatistics(self)

    def filtered_out(self, title: str) -> bool:
        """Checks whether any words from the filter are in the listing title"""
        for word in title.split(' '):
            if word.lower() in self.filtered_words:
                return True
        return False

    async def get_listings(self):
        """Fetch the search results from ebay"""
        page = await self.make_soup()
        product_list = page.find('ul', {'class': 'srp-results'}).find_all('li', {'class':'s-item'})
        products = []
        for i in product_list:
            try:
                listing = SoldListing(i)
                products.append(listing)
            except ListingParsingFailed:
                continue
        # Removes listings that don't pass the filter
        self.filtered_listings = [i for i in products if not self.filtered_out(i.title)]

    async def make_soup(self):
        """Returns a BeautifulSoup object from an ebay search"""
        url = f"https://www.ebay.co.uk/sch/i.html?_from=R40&_nkw={self.filtered_term.lower()}&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1&_ipg=200&LH_ItemCondition=4&LH_PrefLoc=1"
        async with aiohttp.ClientSession() as session:
            data = await session.get(url, headers=headers)
            page_text = await data.text()
            await session.close()
        return soup(page_text, 'html.parser')

    def get_filter(self) -> Tuple[str, list]:
        """Filters out listings with certain words"""
        # define filtered words
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
        words.extend(i.strip('-').lower() for i in self.original_term.split() if i.startswith('-'))
        # remove duplicates
        words = list(set(words))
        # collect words that were added to the filter and search term with boolean operators removed
        filtered_words, filtered_search_term = ([i for i in self.original_term if i.startswith('-')], [i.lower() for i in self.original_term if not i.startswith('-')])
        # remove words in search from filter
        for word in words:
            if word in filtered_search_term:
                words.remove(word)
                if word in filtered_words:
                    filtered_words.remove(word)
        # remove words from filter if searching for certain things
        for key, case_words in edge_cases.items():
            for word in case_words:
                if word in filtered_search_term and key in words:
                    words.remove(key)
        return ' '.join(filtered_search_term), words


class SearchStatistics:
    def __init__(self, search: EbaySearch):
        self.search = search
        self.quartiles = self.find_quartiles()
        self.box_plot = [i.price for i in self.search.filtered_listings if self.quartiles[0] <= i.price <= self.quartiles[2]]
        self.average = sum(self.box_plot) / len(self.box_plot)
        self.variance = self.determine_variance(self.box_plot)
        self.embed = self.make_summary_embed()

    def determine_variance(self, price_range: List[float]) -> float:
        """Get the variance of a price range"""
        mean = sum(price_range) / len(price_range) # Get the mean price
        price_range.sort()
        variance = (price_range[-1] - price_range[0]) / mean * 100 # Range over mean as a percentage
        return round(variance, 2)

    def make_summary_embed(self) -> discord.Embed:
        """Generate the summary embed"""
        def as_price(num: Union[float, int]):
            """Formats a number as a price"""
            return '%.2f' % num if round(num, 2) == int(num) or num < 1 else int(num)

        filtered_words = '\n'.join(i.strip('-') for i in self.search.original_term.split() if i.startswith('-') and i.strip('-').lower() in self.search.filtered_words)
        embed = discord.Embed(title=f"Results for {self.search.filtered_term}", colour=self.get_colour())
        embed.add_field(name='Range', value=f"£{as_price(self.quartiles[0])} - £{as_price(self.quartiles[2])}", inline=True)
        embed.add_field(name='Median', value=f"£{as_price(self.quartiles[1])}", inline=True)
        embed.add_field(name='Average', value=f"£{as_price(self.average)}", inline=True)
        embed.add_field(name='Variance', value=f"{self.variance}%", inline=True)
        embed.add_field(name='Number of items', value=len(self.box_plot), inline=True)
        if self.search.filtered_words:
            embed.add_field(name="Filtered words", value=filtered_words, inline=False)
        return embed

    def get_colour(self) -> int:
        """Determines embed colour based on variance amount"""
        if 0 <= self.variance < 16.6:
            return 0x78B159 # green
        elif 16.6 <= self.variance < 33.3:
            return 0xFFAC33 # yellow
        elif 33.3 <= self.variance:
            return 0xDD2E44 # red

    def find_quartiles(self) -> Tuple[float]:
        """Find quartile positions from a list of prices"""
        prices = [i.price for i in self.search.filtered_listings]
        if not len(prices):
            quartiles = [0,0,0]
        else:
            sorted_array = sorted(prices)
            lower_pos, median_pos, upper_pos = self.find_quartile_postions(len(prices))
            # If position is an integer, the quartile is the elem at position
            # else the quartile is the mean of the elem & the elem one position above
            lower_quartile = (
                sorted_array[lower_pos]
                if (lower_pos % 1 == 0)
                else (sorted_array[lower_pos] + sorted_array[lower_pos + 1]) / 2
            )
            median = (
                sorted_array[median_pos]
                if (median_pos % 1 == 0)
                else (sorted_array[median_pos] + sorted_array[median_pos + 1]) / 2
            )
            upper_quartile = (
                sorted_array[upper_pos]
                if (upper_pos % 1 == 0)
                else (sorted_array[upper_pos] + sorted_array[upper_pos + 1]) / 2
            )
            quartiles = [round(i, 2) for i in [lower_quartile, median, upper_quartile]]
        return quartiles

    def find_quartile_postions(self, size: int) -> Tuple[float]:
        """Determines quartile positions from the length of a list of prices"""
        if size == 1:
            # All quartiles are the first (only) element
            return 0, 0, 0
        elif size == 2:
            # Lower quartile is first element, Upper quartile is second element, Median is average
            return 0, 0.5, 1
        else:
            # Lower quartile is element at 1/4th position, median at 1/2th, upper at 3/4
            # Quartiles can be between positions if size + 1 is not divisible by 4
            return tuple([math.floor(i) for i in ((size + 1) / 4 - 1, (size + 1) / 2 - 1, 3 * (size + 1) / 4 - 1)])


class Ebay(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.command(aliases=['check', 'pc', 'chk', 'price', 'pricecheck'])
    async def ebay(self, ctx, *, search_term):
        """Gets the average price of an item from Ebay
        
        Usage example:
        !check dell xps 15 -dead -broken -scratched
        words beginning with `-` are added to the list of words to be filtered out"""
        search_term = search_term.lower()
        # If the searchterm with boolean operators removed is less than 6 characters
        if len(' '.join(i for i in search_term.split(' ') if not i.startswith('-'))) < 6:
            embed = self.error_embed('length')
            await ctx.send(embed=embed)
            return

        async with ctx.channel.typing():
            search = EbaySearch(search_term)
            await search.get_listings()
            if not search.filtered_listings: # If no listings pass filter
                await self.no_results(ctx, search_term)
                return
            await self.send_search_statistics(ctx, search)

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

    # Menu functions

    async def refilter_menu(self, ctx: commands.Context, message: discord.Message, search: EbaySearch,  position: int):
        """Refilter menu loop"""
        emojis = ['⬅', '🗑', '➡', '✅']
        def reaction_info_check(reaction, user):
            return reaction.message.id == message.id and reaction.emoji in emojis and user == ctx.author

        try: # Wait for a reaction
            reaction, _ = await self.client.wait_for('reaction_add', timeout=180.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            return
        else:
            # User has reacted with an emoji, let's find out what it is
            await message.remove_reaction(reaction.emoji, ctx.author)
            if reaction.emoji == '⬅':
                position = (position - 1) % (len(search.filtered_listings) - 1)
                search.filtered_listings[position].embed.set_footer(text=f"{position + 1} of {len(search.filtered_listings)}")
                await message.edit(embed=search.filtered_listings[position].embed)
                await self.refilter_menu(ctx, message, search, position)
            elif reaction.emoji == '➡':
                position = (position + 1) % (len(search.filtered_listings) - 1)
                search.filtered_listings[position].embed.set_footer(text=f"{position + 1} of {len(search.filtered_listings)}")
                await message.edit(embed=search.filtered_listings[position].embed)
                await self.refilter_menu(ctx, message, search, position)
            elif reaction.emoji == '🗑':
                search.filtered_listings.remove(search.filtered_listings[position].embed)
                position = position % (len(search.filtered_listings) - 1)
                search.filtered_listings[position].embed.set_footer(text=f"{position + 1} of {len(search.filtered_listings)}")
                await message.edit(embed=search.filtered_listings[position].embed)
                await self.refilter_menu(ctx, message, search, position)
            elif reaction.emoji == '✅':
                await message.delete()
                await self.send_search_statistics(ctx, search)

    async def send_search_statistics(self, ctx: commands.Context, search: EbaySearch):
        """Initialise the search statistics and send the statistics embed"""
        # Calculate the statistics
        search.get_statistics()
        message = await ctx.send(embed=search.statistics.embed)
        emojis = ['🔍']
        for emoji in emojis:
            await message.add_reaction(emoji)

        def reaction_info_check(reaction, user):
            return user == ctx.author and reaction.message.id == message.id and reaction.emoji in emojis

        try: # Wait for a reaction
            reaction, _ = await self.client.wait_for('reaction_add', timeout=180.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            return
        else:
            # User has reacted with 🔍
            message = await ctx.send(embed=search.filtered_listings[0].embed)
            emojis = ['⬅', '🗑', '➡', '✅']
            for emoji in emojis:
                await message.add_reaction(emoji)
            await self.refilter_menu(ctx, message, search, 0)

def setup(client):
    client.add_cog(Ebay(client))
