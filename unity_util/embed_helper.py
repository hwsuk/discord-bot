import discord
from discord.ext import commands


async def error_message(ctx: commands.Context, error_msg: str, cmd_error: bool = True):
    """Send an error message to the channel"""
    embed = discord.Embed(
        title="Error",
        description=f"Error in command {ctx.command.name}: `{error_msg}`" if cmd_error else error_msg,
        colour=discord.Colour.red(),
    )
    await ctx.send(embed=embed)


async def success_message(ctx: commands.Context, success_msg: str):
    """Send a success message to the channel"""
    embed = discord.Embed(title="Success", description=success_msg, colour=discord.Colour.red())
    await ctx.send(embed=embed)
