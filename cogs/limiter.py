import discord
from discord.ext import commands
from discord.ext.commands import has_permissions
import datetime
import config
import logging
import asyncio
import sys

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{config.LOGGING_FILENAME}')
])

class Limiter(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.whitelisted_users = []

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        print('Buy-sell-trade post limiter cog online')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # we do not want the bot to reply to itself or other bots
        if message.author.bot == True or message.author.id == self.client.user.id:
            return

        # Only read messages in the right channel
        if message.channel.id != config.BUY_SELL_CHANNEL_ID:
            return

        author = message.author
        if author.id in self.whitelisted_users:
            return
        content = message.content # Save this
        time_limit = datetime.datetime.now() - datetime.timedelta(seconds=config.BUY_SELL_LIMIT_SECONDS)
        messages = await message.channel.history(after=time_limit).flatten()
        for past_message in messages:
            if past_message.author == author and past_message.id != message.id:
                deletion_success = False
                try:
                    logging.info(f"Deleting message {message.id} from {author.id}")
                    await message.delete()
                    deletion_success = True
                except discord.Forbidden:
                    logging.warning(f"Did not have permission to delete message {message.id} from {author}!")
                except discord.NotFound:
                    logging.info(f"Message {message.id} from {author.id} was already deleted")
                except discord.HTTPException as e:
                    logging.error(f"Failed to delete message {message.id} from {author.id} : {e}")

                if deletion_success:
                    await self.send_info_message(author, message.channel.id, content)

    @commands.group()
    @has_permissions(manage_roles=True)
    async def limiter(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @limiter.command()
    async def whitelist(self, ctx, member: discord.Member, seconds: int):
        """Allows a user to post in the buy-sell-trade channel within the slowmode time"""
        desc = f"{member.mention} you can now post in <#{config.BUY_SELL_CHANNEL_ID}> for {str(datetime.timedelta(seconds=int(seconds)))}"
        embed = discord.Embed(title=f"Whitelisted user", description=desc, colour=member.colour)
        await ctx.send(embed=embed)
        self.whitelisted_users.append(member.id)
        await asyncio.sleep(seconds)
        try:
            self.whitelisted_users.remove(member.id)
        except ValueError:
            logging.warning(f"User {member.id} already removed from whitelist")

    async def make_embed(self, author: discord.Member, deleted_content: str) -> discord.Embed:
        user = await self.client.fetch_user(author.id)
        embed = discord.Embed(description=deleted_content, colour=author.colour)
        if author.avatar is None:
            embed.set_author(name=author.display_name, icon_url = f"https://cdn.discordapp.com/embed/avatars/{user.discriminator}.png")
        else:
            embed.set_author(name=author.display_name, icon_url = f"https://cdn.discordapp.com/avatars/{author.id}/{author.avatar}.png")
        return embed

    async def send_info_message(self, author: discord.Member, channel_id: int, deleted_content: str):
        if author.dm_channel is None:
            await author.create_dm()
        dm_channel = author.dm_channel
        content = f"Your post in <#{channel_id}> has been removed due to being within {str(datetime.timedelta(seconds=config.BUY_SELL_LIMIT_SECONDS))} of your last post."
        content += "\nThe message has been saved for you"
        embed = await self.make_embed(author, deleted_content)
        try:
            await dm_channel.send(content, embed=embed)
        except: # If the bot can't DM the user
            backup_channel = self.client.get_channel(config.BUY_SELL_BACKUP_DM_CHANNEL_ID)
            content = f"<@{author.id}> {content}"
            await backup_channel.send(content=content, embed=embed)

def setup(client):
    client.add_cog(Limiter(client))
