import discord
from discord.ext import commands
from unity_util import bot_config
import logging
import sys
import random

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{bot_config.LOGGING_FILENAME}')
])


class EmbedRemover(commands.Cog):
    def __init__(self, client):
        self.client = client

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        logging.info('Embed remover cog online')

    @commands.Cog.listener()
    async def on_message(self, message: discord.message):
        if message.channel.id == bot_config.EMBED_REMOVER_CHANNEL_ID:
            try:
                await message.edit(suppress=True)
            except discord.Forbidden:
                logging.warning(f"Did not have permission to remove embeds from {message.id} from {message.author}!")


def setup(client):
    client.add_cog(EmbedRemover(client))
