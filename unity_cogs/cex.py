import logging
import urllib.parse
from typing import Tuple
from urllib import parse

import discord
import httpx
from discord.ext import commands

from unity_util.menu import DEFAULT_CONTROLS, menu

CEX_RED = 0xFF0000
CEX_LOGO = "https://uk.webuy.com/_nuxt/74714aa39f40304c8fac8e7520cc0a35.png"


# Search item aliases
D = {
    "bI": "boxId",
    "bN": "boxName",
    "iMB": "isMasterBox",
    "cI": "categoryId",
    "cN": "categoryName",
    "cFN": "categoryFriendlyName",
    "sCI": "superCatId",
    "sCN": "superCatName",
    "sCFN": "superCatFriendlyName",
    "cB": "cannotBuy",
    "iNB": "isNewBox",
    "sP": "sellPrice",
    "cP": "cashPrice",
    "eP": "exchangePrice",
    "bR": "boxRating",
    "oOS": "outOfStock",
    "oOES": "outOfEcomStock",
    "eQOH": "ecomQuantityOnHand",
}


class Cex(commands.Cog):
    def __init__(self, client):
        self.client = client

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Cex search cog online")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # we do not want the bot to reply to itself or other bots
        if message.author.bot or message.author.id == self.client.user.id:
            return

        if "https://uk.webuy.com/" in message.content.lower():
            for word in message.content.lower().split(" "):
                if not word.startswith("https://uk.webuy.com/"):
                    continue
                if not parse.parse_qs(parse.urlsplit(word).query)["id"]:
                    continue
                try:
                    product_id = parse.parse_qs(parse.urlsplit(word).query)["id"][0]
                except KeyError:
                    continue
                cex_search = await self.cex_search(product_id)
                if not cex_search:  # If no results
                    continue
                new_embed = self.make_cex_embed(cex_search[0])
                await message.edit(suppress=True)
                await message.channel.send(embed=new_embed)

    # Commands

    @commands.command()
    async def search(self, ctx, *, search_term: str):
        """Search the CeX website"""
        # Prepare and sanitise the search arguments
        cex_search = await self.cex_search(search_term)  # Get products

        if not cex_search:  # If no results for that search term
            await self.no_results(ctx, search_term)
            return

        if len(cex_search) == 1:  # If only one result
            cex_embed = self.make_cex_embed(cex_search[0], {"current": 0, "max": 0})
            await ctx.send(embed=cex_embed)
            return

        cex_embeds = [self.make_cex_embed(item, f"{i + 1} of {len(cex_search)}") for i, item in enumerate(cex_search)]
        await menu(ctx, pages=cex_embeds, controls=DEFAULT_CONTROLS, timeout=180.0)

    # Helper functions

    async def cex_search(self, search_term: str) -> Tuple[dict]:
        """Retrieve search data"""
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36"
        }
        clean_search_term = urllib.parse.quote(search_term)  # Clean up the search term for the url
        url = f"https://wss2.cex.uk.webuy.io/v3/boxes?q={clean_search_term}&firstRecord=1&count=50&sortOrder=desc"

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers)

        if r.status_code != 200:
            return

        products = r.json()

        if products["response"]["data"]:
            return tuple(products["response"]["data"]["boxes"])
        else:
            return

    def make_cex_embed(self, search_object: dict, footer: str = "") -> discord.Embed:
        """Make embed from search data"""
        # Format prices as currency
        we_sell = "£{:,.2f}".format(float(search_object[D["sP"]]))
        we_buy_voucher = "£{:,.2f}".format(float(search_object[D["eP"]]))
        we_buy_cash = "£{:,.2f}".format(float(search_object[D["cP"]]))
        # Construct embed
        embed = discord.Embed(
            colour=discord.Colour(CEX_RED),
            url="https://uk.webuy.com/product-detail/?id=" + search_object[D["bI"]],
        )
        embed.set_author(
            name=search_object[D["bN"]],
            url="https://uk.webuy.com/product-detail?id=" + search_object[D["bI"]],
            icon_url=CEX_LOGO,
        )
        embed.set_thumbnail(url=search_object["imageUrls"]["large"].replace(" ", "%20"))  # cleans up the URL
        embed.add_field(name="WeSell for", value=we_sell, inline=True)
        embed.add_field(name="WeBuy for Voucher", value=we_buy_voucher, inline=True)
        embed.add_field(name="WeBuy for Cash", value=we_buy_cash, inline=True)

        if search_object[D["oOES"]] == 1:  # If it's out of stock
            embed.add_field(name="In Stock", value=False, inline=True)
        else:
            embed.add_field(name="Stock", value=search_object[D["eQOH"]], inline=True)

        if not search_object[D["bR"]]:
            embed.add_field(name="Rating", value="None", inline=True)
        else:
            embed.add_field(name="Rating", value=search_object[D["bR"]], inline=True)

        embed.add_field(name="Category", value=search_object[D["cFN"]], inline=True)

        if footer:
            embed.set_footer(text=footer)

        return embed

    async def no_results(self, ctx, search_term: str):
        embed = discord.Embed(
            colour=CEX_RED,
            description=f"No products found for `{search_term.replace('`', '``')}`",
        )
        embed.set_author(name="No results 🙁", icon_url=CEX_LOGO)
        await ctx.send(embed=embed)


def setup(client):
    client.add_cog(Cex(client))
