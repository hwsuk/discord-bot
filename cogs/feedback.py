import discord
import asyncio
import sys
import logging
from discord.ext import commands, tasks
import config

green = 0x00ff00

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{config.LOGGING_FILENAME}')
])

class Feedback(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Feedback cog online')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.id == config.REACTION_CHANNEL_ID and message.author.id != self.client.user.id:
            await message.add_reaction('👍')
            await message.add_reaction('👎')

            def check(reaction, user):
                for r in reaction.message.reactions:
                    if r.emoji == '👍' and r.count - 1 >= config.REACTION_THRESHOLD:
                        return True
                return False

            try:
                await self.client.wait_for('reaction_add', timeout=86400.0, check=check)
                await self.send_feedback_embed(message)
            except asyncio.TimeoutError:
                return

    async def send_feedback_embed(self, message):
        if message.author.id == self.client.user.id:
            return

        channel = self.client.get_channel(config.MOD_CHANNEL_ID)

        if not channel:
            logging.warning("WARNING: Tried to send an embed to a nonexistent channel.")
            return

        link = f"https://discordapp.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        embed = discord.Embed(description=f"_You were notified about this feedback because it received at least {config.REACTION_THRESHOLD} upvotes._",
                            color=green)
        embed.set_author(name="New feedback received", url=link)
        embed.add_field(name="Feedback", value=message.content)

        await channel.send(embed=embed)

def setup(client):
    client.add_cog(Feedback(client))
