import discord
from discord.ext import commands
import config
import logging
import sys
import random

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{config.LOGGING_FILENAME}')
])

IMAGE_LINKS = [
    "https://cdn.discordapp.com/attachments/292035708779102208/800403298096119848/eae418cc13c3a477777624169021de320caca7a2827e2dfaf2af21d00f8b1780_1.png",
    "https://tenor.com/view/who-tf-asked-nasas-radar-dish-who-asked-nobody-asked-gif-17675657",
    "https://tenor.com/view/nobody-cares-nobody-asked-who-asked-find-who-asked-searching-gif-19968984",
    "https://tenor.com/view/among-us-who-asked-gif-18850795"
]


class RenderMeme(commands.Cog):
    def __init__(self, client):
        self.client = client

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        print('Renderdistance meme cog online')

    @commands.command(name="rd", aliases=["wa"])
    async def _rd(self, ctx):
        await ctx.send(content=random.choice(IMAGE_LINKS))
        return


def setup(client):
    client.add_cog(RenderMeme(client))
