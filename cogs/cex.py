import asyncio
import json
import aiohttp
import discord
from discord.ext import commands
import time
import urllib.parse
from urllib import parse
import re

cexRed = 0xff0000
cexLogo = 'https://uk.webuy.com/_nuxt/74714aa39f40304c8fac8e7520cc0a35.png'
cexEmoji = '<:cex:292749632025657354>'
# Search item aliases
D = {
    'bI'    :   'boxId',
    'bN'    :   'boxName',
    'iMB'   :   'isMasterBox',
    'cI'    :   'categoryId',
    'cN'    :   'categoryName',
    'cFN'   :   'categoryFriendlyName',
    'sCI'   :   'superCatId',
    'sCN'   :   'superCatName',
    'sCFN'  :   'superCatFriendlyName',
    'cB'    :   'cannotBuy',
    'iNB'   :   'isNewBox',
    'sP'    :   'sellPrice',
    'cP'    :   'cashPrice',
    'eP'    :   'exchangePrice',
    'bR'    :   'boxRating',
    'oOS'   :   'outOfStock',
    'oOES'  :   'outOfEcomStock',
    'eQOH'  :   'ecomQuantityOnHand'
}

class Cex(commands.Cog):

    def __init__(self, client):
        self.client = client

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        print('Cex search cog online')

    @commands.Cog.listener()
    async def on_message(self, message):
        # we do not want the bot to reply to itself or other bots
        if message.author.bot == True or message.author.id == self.client.user.id:
            return

        if 'https://uk.webuy.com/' in message.content.lower():
            for word in message.content.lower().split(' '):
                if not word.startswith('https://uk.webuy.com/'):
                    continue
                if parse.parse_qs(parse.urlsplit(word).query)['id'] == {}:
                    continue
                try:
                    productId = parse.parse_qs(parse.urlsplit(word).query)['id'][0]
                except KeyError:
                    continue
                cexSearch = await self.cex_search(productId)
                if cexSearch is None:
                    continue
                cexSearch = cexSearch['boxes'][0]
                newEmbed = await self.make_cex_embed(cexSearch)
                await message.edit(suppress=True)
                await message.channel.send(embed=newEmbed)

        if 'cex' in message.content.lower():
            await message.add_reaction(cexEmoji)

    # Search command
    @commands.command()
    async def search(self, ctx, *arg):
        """Searches the CeX website"""
        # Prepare and sanitise the search arguments
        index = {}
        indexReg = re.compile("r=([0-9]+)")
        # Check for an index modifier argument ([p]search product r=3)
        if indexReg.match(arg[-1]):
            match = indexReg.match(arg[-1])
            index['current'] = int(match.group(1)) - 1
            arg = arg[:-1]
        else:
            index['current'] = 0
        arg = " ".join(arg)
        # Fetch search results
        cexSearch = await self.cex_search(arg)
        if cexSearch is None: # If no results for that search term
            await self.no_results(ctx, arg)
            return
        else:
            cexSearch = cexSearch['boxes']
        if len(cexSearch) == 1: # If only one result
            index = {'min':0,'current':0,'max':0}
            cexEmbed = await self.make_cex_embed(cexSearch[index['current']],index)
            await ctx.send(embed=cexEmbed)
            return
        # Check that the current index, if modified, is within range
        try:
            cexSearch[index['current']]
        except IndexError:
            index['current'] = len(cexSearch) - 1
        index = {'min':0,
                'current':index['current'],
                'max':len(cexSearch)-1}
        cexEmbed = await self.make_cex_embed(cexSearch[index['current']], index)
        messageObject = await ctx.send(content=f"<https://uk.webuy.com/search/index.php?stext={urllib.parse.quote(arg)}&categoryID=&is=0>", embed=cexEmbed) # send a result
        allowedEmojis = await self.add_buttons(messageObject, index) # add buttons and get allowedEmojis

        def reaction_info_check(reaction, user):
            return user == ctx.author and reaction.message.id == messageObject.id

        # Wait for a reaction
        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=120.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            # User has reacted with an emoji, find out which one
            if reaction.emoji in allowedEmojis:
                if reaction.emoji == '▶':
                    index['current'] = index['current'] + 1
                    messageObject = await messageObject.channel.fetch_message(messageObject.id)
                    await messageObject.remove_reaction(reaction.emoji,ctx.author)
                    await self.edit_result(ctx, cexSearch, index, messageObject, arg)
                if reaction.emoji == '◀':
                    index['current'] = index['current'] - 1
                    messageObject = await messageObject.channel.fetch_message(messageObject.id)
                    await messageObject.remove_reaction(reaction.emoji,ctx.author)
                    await self.edit_result(ctx, cexSearch, index, messageObject, arg)
        return

    # Helper functions

    # Retrieve search data
    async def cex_search(self, searchTerm):
        headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'}
        cleanSearchTerm = urllib.parse.quote(searchTerm) # clean up the search term for the url
        async with aiohttp.ClientSession() as session:
            data = await session.get(f'https://wss2.cex.uk.webuy.io/v3/boxes?q={cleanSearchTerm}&firstRecord=1&count=50&sortOrder=desc',headers=headers)
            products = await data.json()
            await session.close()
        products = products['response']['data']

        return products

    # Make embed from search data
    async def make_cex_embed(self, searchObject, index=None):
        # Format prices as currency
        weSell = "£{:,.2f}".format(float(searchObject[D['sP']]))
        weBuyV = "£{:,.2f}".format(float(searchObject[D['eP']]))
        weBuyC = "£{:,.2f}".format(float(searchObject[D['cP']]))
        embed = discord.Embed(colour=discord.Colour(cexRed), url="https://uk.webuy.com/product-detail/?id="+searchObject[D['bI']])
        embed.set_author(name=searchObject[D['bN']], url="https://uk.webuy.com/product-detail?id="+searchObject[D['bI']], icon_url=cexLogo)
        embed.set_thumbnail(url=searchObject['imageUrls']['large'].replace(" ", "%20")) # cleans up the URL
        embed.add_field(name="WeSell for", value=weSell, inline=True)
        embed.add_field(name="WeBuy for Voucher", value=weBuyV, inline=True)
        embed.add_field(name="WeBuy for Cash", value=weBuyC, inline=True)
        if searchObject[D['oOES']] == 1: # if it's out of stock
            embed.add_field(name="In Stock", value=False, inline=True)
        else:
            embed.add_field(name="Stock", value=searchObject[D['eQOH']], inline=True)
        if searchObject[D['bR']] == None:
            embed.add_field(name="Rating",value='None',inline=True)
        else:
            embed.add_field(name="Rating",value=searchObject[D['bR']],inline=True)
        embed.add_field(name="Category", value=searchObject[D['cFN']], inline=True)
        if index != None:
            embed.set_footer(text=f"{index['current']+1} of {index['max']+1}")
        return embed

    async def edit_result(self, ctx, cexSearch, index, messageObject, searchTerm):
        cexEmbed = await self.make_cex_embed(cexSearch[index['current']], index)
        await messageObject.edit(content=f"<https://uk.webuy.com/search/index.php?stext={urllib.parse.quote(searchTerm)}&categoryID=&is=0>", embed=cexEmbed)
        allowedEmojis = await self.add_buttons(messageObject, index) # add buttons and get allowedEmojis

        def reaction_info_check(reaction, user):
            return user == ctx.author and reaction.message.id == messageObject.id

        # Wait for a reaction
        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=120.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            # User has reacted with an emoji, find out which one
            if reaction.emoji in allowedEmojis:
                if reaction.emoji == '▶':
                    index['current'] = index['current'] + 1
                    messageObject = await messageObject.channel.fetch_message(messageObject.id)
                    await messageObject.remove_reaction(reaction.emoji,ctx.author)
                    await self.edit_result(ctx, cexSearch, index, messageObject, searchTerm)
                if reaction.emoji == '◀':
                    index['current'] = index['current'] - 1
                    messageObject = await messageObject.channel.fetch_message(messageObject.id)
                    await messageObject.remove_reaction(reaction.emoji,ctx.author)
                    await self.edit_result(ctx, cexSearch, index, messageObject, searchTerm)

    async def no_results(self, ctx, arg):
        embed = discord.Embed(colour=cexRed, description="No products found for `{}`".format(arg.replace('`','``')))
        embed.set_author(name="No results 🙁", icon_url=cexLogo)
        await ctx.send(embed=embed)
        return

    async def add_buttons(self, messageObject, index):
        messageObject = await messageObject.channel.fetch_message(messageObject.id)
        oldReacts = []
        for reaction in messageObject.reactions:
            if reaction.me:
                oldReacts.append(reaction.emoji)
        if index['current'] == index['min']: # first result, no back arrow required
            allowedEmojis = ['▶']
        if index['current'] == index['max']: # last result, no forward arrow required
            allowedEmojis = ['◀']
        if index['min'] < index['current'] < index['max']: # a middle result, both arrows required
            allowedEmojis = ['◀','▶']
        if oldReacts == allowedEmojis:
            for reaction in messageObject.reactions:
                if reaction.me:
                    continue
                await messageObject.remove_reaction(reaction.emoji,ctx.author)
        else:
            await messageObject.clear_reactions()
            for emoji in allowedEmojis:
                await messageObject.add_reaction(emoji)
        return allowedEmojis

def setup(client):
    client.add_cog(Cex(client))
