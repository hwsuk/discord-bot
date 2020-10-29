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
        """Gets the average price of an item from Ebay
        
        Usage example:
        !check dell xps 15 -dead -broken -scratched
        words beginning with `-` are added to the list of words to be filtered out"""
        # If the searchterm with boolean operators removed is less than 6 characters
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
                if p is not None:
                    products.append(p)

            def filtered_out(title: str, filteredWords: list):
                """Checks whether any words from the filter are in the listing title"""
                for word in title.split(' '):
                    if word.lower() in filteredWords:
                        return True
                return False

            # Removes listings that don't pass the filter
            filteredListings = [i for i in products if filtered_out(i['title'], filteredWords) is False]
            if not filteredListings: # If no listings pass filter
                desc = [f"No results found for `{filteredTerm}`"]
                desc.append("Make sure to include manufacturer for best results")
                desc.append("If you feel this is in error, message one of the bot developers")
                embed = discord.Embed(title='No results found', colour=0xE53238, description='\n'.join(desc))
                fW = [i[1:] for i in searchTerm.split(' ') if i.startswith('-')]
                if fW:
                    embed.add_field(name="Filtered words", value='\n'.join(fW), inline=True)
                await ctx.send(embed=embed)
                return

            # If there are listings that passed the filter
            # Get the 25th, 50th and 75th percentiles of the price range
            quartiles = await self.find_quartiles([i['price'] for i in filteredListings])
            boxPlot = [i['price'] for i in filteredListings if quartiles[0] <= i['price'] <= quartiles [2]]
            average = sum(boxPlot) / len(boxPlot)
            # Get variance
            variance = await self.determine_variance(boxPlot)
            # Make and send the embed
            embedDetails = {"title": f"Results for {filteredTerm}",
                            "range": [quartiles[0], quartiles[2]],
                            "median": quartiles[1],
                            "average": average,
                            "variance": variance,
                            "numOfItems": len(boxPlot),
                            "filteredWords": [i.strip('-') for i in searchTerm.split(' ') if i.startswith('-')]}
            embed = await self.make_embed(embedDetails)
            await ctx.send(embed=embed)

    async def make_embed(self, data:dict):
        """Generate an embed object"""
        colour = await self.get_colour(data)

        def price(num):
            """Formats a number as a price"""
            return '%.2f' % num if round(num, 2) == int(num) or num < 1 else int(num)

        embed = discord.Embed(title=data['title'], colour=colour)
        embed.add_field(name='Range', value=f"£{price(data['range'][0])} - £{price(data['range'][1])}", inline=True)
        embed.add_field(name='Median', value=f"£{price(data['median'])}", inline=True)
        embed.add_field(name='Average', value=f"£{price(data['average'])}", inline=True)
        embed.add_field(name='Variance', value=f"{data['variance']}%", inline=True)
        embed.add_field(name='Number of items', value=data['numOfItems'], inline=True)
        if data['filteredWords']:
            embed.add_field(name="Filtered words", value='\n'.join(data['filteredWords']), inline=False)
        return embed

    async def make_soup(self, searchTerm):
        """Returns a BeautifulSoup object from an ebay search"""
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
        """Fetches the product info from a product listing as a dict"""
        try:
            d = {}
            d['title'] = product.find('h3', {'class': 's-item__title'}).contents[-1]
            d['url'] = product.find('a')['href']
            d['image'] = product.find('img')['src']
            d['price'] = await self.parse_price(product)
            d['ended_date'] = await self.parse_date(product)
            d['id'] = d['url'].split('/')[-1].split('?')[0]
            # Type enforcement on dictionary object
            return {'title': str(d['title']), 'url': str(d['url']), 'image': str(d['image']), 'price': d['price'], 'ended_date': d['ended_date'], 'id': str(d['id'])}
        except:
            return None

    async def parse_price(self, product):
        """Retrieves the full price from a product listing"""
        logReg = re.compile('\+\s£(\d+\.\d+).*')
        basePrice = float(product.find('span', {'class': 's-item__price'}).contents[0].contents[0].strip('£').replace(',','')) # Find the listing price
        if not product.find('span', {'class': 's-item__logisticsCost'}): # If there is no postage price return the listing price
            return basePrice
        logistics = product.find('span', {'class': 's-item__logisticsCost'}).contents[0]
        if type(logistics) is bs4.element.NavigableString:
            if logistics.lower() in ['free postage', 'postage not specified']: # Ignore common strings
                postage = 0
            elif logReg.match(logistics): # Find the price if there's a regex match
                postage = float(logReg.match(logistics).group(1))
        else: # If type is not NavigableString (most likely to be Tag)
            logistics = logistics.contents[-1]
            if logReg.match(logistics): # Apply regex
                postage = float(logReg.match(logistics).group(1))
            else: # Account for edge cases
                postage = 0
        return basePrice + postage

    async def parse_date(self, product):
        """Retrieves the ended date from a product listing"""
        # Fetch the date string
        base = product.find('span', {'class': 's-item__ended-date'}).contents[0]
        # Retrieve the individual parts of the date
        day = int(base.split('-')[0])
        months = {datetime.date(2020, i, 1).strftime('%B')[:3]: i for i in range(1,13)}
        month = months[base.split('-')[1].split(' ')[0]]
        time = base.split(' ')[1]
        hour = int(time.split(':')[0])
        minute = int(time.split(':')[1])
        # Convert to a datetime object
        return datetime.datetime(year=datetime.datetime.now().year, month=month, day=day, hour=hour, minute=minute)

    async def find_quartiles(self, numArray: list):
        """Find quartile positions from a list of prices"""
        size = len(numArray)
        if size == 0:
            quartiles = [0,0,0]
        else:
            sortedArray = sorted(numArray)
            lowerPos, medianPos, upperPos = await self.find_quartile_postions(size)
            # Floor so can work in arrays
            flooredLowerPos = math.floor(lowerPos)
            flooredMedianPos = math.floor(medianPos)
            flooredUpperPos = math.floor(upperPos)
            # If position is an integer, the quartile is the elem at position
            # else the quartile is the mean of the elem & the elem one position above
            lowerQuartile = sortedArray[flooredLowerPos] if (lowerPos % 1 == 0) else (sortedArray[flooredLowerPos] + sortedArray[flooredLowerPos + 1]) / 2
            median = sortedArray[flooredMedianPos] if (medianPos % 1 == 0) else (sortedArray[flooredMedianPos] + sortedArray[flooredMedianPos + 1]) / 2
            upperQuartile = sortedArray[flooredUpperPos] if (upperPos % 1 == 0) else (sortedArray[flooredUpperPos] + sortedArray[flooredUpperPos + 1]) / 2
            quartiles = [round(i, 2) for i in [lowerQuartile, median, upperQuartile]]
        return quartiles

    async def find_quartile_postions(self, size: int):
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

    async def determine_variance(self, priceRange):
        """Get the variance of a price range"""
        mean = sum(priceRange) / len(priceRange) # Get the mean price
        priceRange.sort()
        variance = (priceRange[-1] - priceRange[0]) / mean * 100 # Range over mean as a percentage
        return round(variance, 2)

    async def get_colour(self, data):
        """Determines embed colour based on variance amount"""
        if 0 <= data['variance'] < 16.6:
            return 0x78B159 # green
        elif 16.6 <= data['variance'] < 33.3:
            return 0xFFAC33 # yellow
        elif 33.3 <= data['variance']:
            return 0xDD2E44 # red

    async def error_embed(self, error):
        """Generates an error embed"""
        errors = {'length': 'Your search must be more than 6 characters',
                  'timeout': 'The server failed to fetch a result'}
        return discord.Embed(title='Error', description=errors[error], colour=0xDD2E44)

def setup(client):
    client.add_cog(Ebay(client))
