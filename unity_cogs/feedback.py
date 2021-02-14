import asyncio
import logging

import discord
from discord.ext import commands

from unity_util import bot_config


class Feedback(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Feedback cog online")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == bot_config.REACTION_CHANNEL_ID and message.author.id != self.client.user.id:
            await message.add_reaction("👍")
            await message.add_reaction("👎")

            def check(reaction, user):
                for r in reaction.message.reactions:
                    if r.emoji == "👍" and r.count - 1 >= bot_config.REACTION_THRESHOLD:
                        return True
                return False

            try:
                await self.client.wait_for("reaction_add", timeout=86400.0, check=check)
                await self.send_feedback_embed(message)
            except asyncio.TimeoutError:
                return

    async def send_feedback_embed(self, message):
        if message.author.id == self.client.user.id:
            return

        channel = self.client.get_channel(bot_config.MOD_CHANNEL_ID)

        if not channel:
            logging.warning("WARNING: Tried to send an embed to a nonexistent channel.")
            return

        link = f"https://discordapp.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        embed = discord.Embed(
            description=f"_You were notified about this feedback because it received at least {bot_config.REACTION_THRESHOLD} upvotes._",
            color=discord.Colour.green(),
        )
        embed.set_author(name="New feedback received", url=link)
        embed.add_field(name="Feedback", value=message.content)

        await channel.send(embed=embed)


def setup(client):
    client.add_cog(Feedback(client))
