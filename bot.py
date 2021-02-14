import json
import logging
import sys

import discord
from discord.ext import commands

from unity_util import bot_config


logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]\t %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"./logs/{bot_config.LOGGING_FILENAME}"),
    ],
)

intents = discord.Intents(
    guilds=True,
    members=True,
    bans=True,
    emojis=True,
    messages=True,
    guild_messages=True,
    dm_messages=True,
    reactions=True,
    guild_reactions=True,
    dm_reactions=True,
)
client = commands.Bot(command_prefix=bot_config.DISCORD_PREFIX, intents=intents)


@client.event
async def on_ready():
    logging.info(f"Logged in as {client.user.name}, {client.user.id}")
    logging.info("-----------------------------------------")
    await client.change_presence(activity=discord.Game("Verifying 👀"))


@client.command()
@commands.is_owner()
async def load(ctx, extension: str):
    client.load_extension(f"unity_cogs.{extension}")
    await ctx.send(f"{extension} loaded")
    logging.info(f"{extension} loaded")


@client.command()
@commands.is_owner()
async def unload(ctx, extension: str):
    client.unload_extension(f"unity_cogs.{extension}")
    await ctx.send(f"{extension} unloaded")
    logging.info(f"{extension} unloaded")


@client.command()
@commands.is_owner()
async def reload(ctx, extension: str):
    client.reload_extension(f"unity_cogs.{extension}")
    await ctx.send(f"{extension} reloaded")
    logging.info(f"{extension} reloaded")


with open("cogs.json", "r") as f:
    cogs = json.loads(f.read())
    for cog in cogs:
        client.load_extension(f"unity_cogs.{cog}")

client.run(bot_config.DISCORD_TOKEN)
