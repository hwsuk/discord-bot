import discord
from discord.ext import commands
import aiohttp
import bs4
from bs4 import BeautifulSoup as soup
import datetime
import re
import urllib.parse
import math

headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}

class Ebay(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.command(aliases=['pc','chk','price','pricecheck'])
    async def check(self, ctx, *, searchTerm):
        """Gets the average price of an item from Ebay"""
        if len(' '.join([i for i in searchTerm.split(' ') if not i.startswith('-')])) < 6:
            embed = await self.error_embed('length')
            await ctx.send(embed=embed)
            return
        async with ctx.channel.typing():
            filteredTerm, filteredWords = await self.get_filter(searchTerm)
            page = await self.make_soup(filteredTerm)
            productList = page.find('ul', {'class': 'srp-results'}).find_all('li', {'class':'s-item'})
            products = []
            for i in productList:
                p = await self.get_product_info(i)
                products.append(p)

            def filtered_out(title: str, filteredWords: list):
                for word in title.split(' '):
                    if word.lower() in filteredWords:
                        return True
                return False

            filteredListings = [i for i in products if filtered_out(i['title'], filteredWords) is False]
            if len(filteredListings) == 0:
                embed = discord.Embed(title='No results found', colour=0xE53238, description=f"No results found for {filteredTerm}")
                fW = [i.split('-') for i in searchTerm.split(' ') if i.startswith('-')]
                embed.add_field(name="Filtered words", value='\n'.join(fW), inline=True)
                await ctx.send(embed=embed)
                return
            quartiles = await self.find_quartiles([i['price'] for i in filteredListings])
            # from 25th to 75th percentile
            boxPlot = [i['price'] for i in filteredListings if quartiles[0] <= i['price'] <= quartiles [2]]
            average = sum(boxPlot) / len(boxPlot)
            variance = await self.determine_variance(boxPlot)
            embedDetails = {"title": f"Results for {filteredTerm}",
                            "range": f"£{quartiles[0]} - £{quartiles[2]}",
                            "median": f"£{quartiles[1]}",
                            "average": f"£{average}",
                            "variance": f"{variance}%",
                            "numOfItems": str(len(boxPlot)),
                            "filteredWords": [i for i in searchTerm if i.startswith('-')]}
            embed = await self.make_embed(embedDetails)
            await ctx.send(embed=embed)

    async def make_embed(self, data:dict):
        colour = await self.get_colour(data)
        embed = discord.Embed(title=data['title'], colour=colour)
        embed.add_field(name='Range', value=data['range'], inline=True)
        embed.add_field(name='Median', value=data['median'], inline=True)
        embed.add_field(name='Average', value=round(data['average'], 2), inline=True)
        embed.add_field(name='variance', value=f"{data['variance']}%", inline=True)
        embed.add_field(name='Number of items', value=data['numOfItems'], inline=True)
        if data['filteredWords'] != []:
            embed.add_field(name="Filtered words", value='\n'.join(data['filteredWords']), inline=False)
        return embed

    async def make_soup(self, searchTerm):
        cleanSearchTerm = urllib.parse.quote(searchTerm) # clean up the search term for the url
        url = f"https://www.ebay.co.uk/sch/i.html?_from=R40&_nkw={searchTerm}&_sacat=0&rt=nc&LH_Sold=1&LH_Complete=1&_ipg=200"
        async with aiohttp.ClientSession() as session:
            data = await session.get(url, headers=headers)
            pageText = await data.text()
            await session.close()
        return soup(pageText, 'html.parser')

    async def get_filter(self, searchTerm):
        """Filters out listings with certain words"""
        # define filtered words
        searchTerm = searchTerm.split(' ')
        edgeCases = {'max': ['amd', 'intel'],
                     'pc': ['case'],
                     'cooler': ['aio', 'air', 'liquid']}
        words = ['pro', 'plus', 'max', 'super', 'bundle', 'combo', 'faulty',
                 'ti', 'xt', 'spare', 'spares', 'repair', 'repairs', 'cooler',
                 'pc', 'damaged', 'broken', 'with', 'for', 'dell', 'hp',
                 'gigabyte', 'acer', 'lenovo', 'asus', 'alienware', 'parts',
                 'charger', 'dock', 'case', 'replicator', 'keyboard', 'mini',
                 'lite', 'crack', 'cracked', '5g']
        words.extend([i.strip('-').lower() for i in searchTerm if i.startswith('-')])
        # remove duplicates
        words = list(dict.fromkeys(words))
        # collect words that were added to the filter
        filteredWords = [i for i in searchTerm if i.startswith('-')]
        # search term with boolean operators removed
        filteredSearchTerm = [i for i in searchTerm if not i.startswith('-')]
        # remove words in search from filter
        for word in words:
            if word in filteredSearchTerm:
                words.remove(word)
                if word in filteredWords:
                    filteredWords.remove(word)
        # remove words from filter if searching for certain things
        for key in edgeCases.keys():
            for word in edgeCases[key]:
                if word in filteredSearchTerm and key in words:
                    words.remove(key)
        return ' '.join(filteredSearchTerm), words

    async def get_product_info(self, product):
        d = {}
        d['title'] = product.find('h3', {'class': 's-item__title'}).contents[0]
        d['url'] = product.find('a')['href']
        d['image'] = product.find('img')['src']
        d['price'] = await self. parse_price(product)
        d['ended_date'] = await self.parse_date(product)
        d['id'] = d['url'].split('/')[-1].split('?')[0]
        return d

    async def parse_price(self, product):
        logreg = re.compile('\+\s£(\d+\.\d+).*')
        basePrice = float(product.find('span', {'class': 's-item__price'}).contents[0].contents[0].strip('£').replace(',',''))
        if product.find('span', {'class': 's-item__logisticsCost'}) is None:
            return basePrice
        logistics = product.find('span', {'class': 's-item__logisticsCost'}).contents[0]
        if type(logistics) is bs4.element.NavigableString:
            if logistics.lower() in ['free postage', 'postage not specified']:
                postage = 0
            else:
                postage = float(logreg.match(logistics).group(1))
        else:
            logistics = logistics.contents[0]
            if logreg.match(logistics):
                postage = float(logreg.match(logistics).group(1))
        return basePrice + postage

    async def parse_date(self, product):
        base = product.find('span', {'class': 's-item__ended-date'}).contents[0]
        day = int(base.split('-')[0])
        months = {datetime.date(2020, i, 1).strftime('%B')[:3]: i for i in range(1,13)}
        month = months[base.split('-')[1].split(' ')[0]]
        time = base.split(' ')[1]
        return {'day': day, 'month': month, 'time': time}

    async def find_quartile_postions(self, size: int):
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

    async def find_quartiles(self, num_array: list):
        size = len(num_array)
        if size == 0:
            quartiles = [0,0,0]
        else:
            sorted_array = sorted(num_array)
            lower_pos, median_pos, upper_pos = await self.find_quartile_postions(size)
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

    async def determine_variance(self, priceRange):
        mean = sum(priceRange) / len(priceRange)
        priceRange.sort()
        variance = (priceRange[-1] - priceRange[0]) / mean * 100
        return round(variance, 2)

    async def get_colour(self, data):
        if 0 <= data['variance'] < 16.6:
            return 0x78B159 # green
        elif 16.6 <= data['variance'] < 33.3:
            return 0xFFAC33 # yellow
        elif 33.3 <= data['variance']:
            return 0xDD2E44 # red

    async def error_embed(self, error):
        errors = {'length': 'Your search must be more than 6 characters',
                  'timeout': 'The server failed to fetch a result'}
        return discord.Embed(title='Error', description=errors[error], colour=0xDD2E44)

def setup(client):
    client.add_cog(Ebay(client))
