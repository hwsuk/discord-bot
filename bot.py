import discord
from discord.ext import commands, tasks
import os
import json
import logging
import config
import sys

with open('config.json', 'r') as f:
    conf = json.load(f)

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{config.LOGGING_FILENAME}')
])

client = commands.Bot(command_prefix = config.DISCORD_PREFIX)

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user.name}, {client.user.id}')
    logging.info('-----------------------------------------')
    await client.change_presence(activity=discord.Game("Verifying 👀"))

@client.command()
@commands.is_owner()
async def load(ctx, extension):
    client.load_extension(f'cogs.{extension}')
    await ctx.send(f'{extension} loaded')
    logging.info(f'{extension} loaded')

@client.command()
@commands.is_owner()
async def unload(ctx, extension):
    client.unload_extension(f'cogs.{extension}')
    await ctx.send(f'{extension} unloaded')
    logging.info(f'{extension} unloaded')

@client.command()
@commands.is_owner()
async def reload(ctx, extension):
    client.reload_extension(f'cogs.{extension}')
    await ctx.send('{} reloaded'.format(extension))
    logging.info(f'{extension} reloaded')

for cog in conf['preloaded']:
    client.load_extension(f'cogs.{cog}')

client.run(config.DISCORD_TOKEN)