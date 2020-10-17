import discord
from discord.ext import commands
import datetime
import config

class Limiter(commands.Cog):
    def __init__(self, client):
        self.client = client

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
        content = message.content # Save this
        time_limit = datetime.datetime.now() - datetime.timedelta(seconds=config.BUY_SELL_LIMIT_SECONDS)
        messages = await message.channel.history(after=time_limit).flatten()

        for past_message in messages:
            if past_message.author == author and past_message.id != message.id:
                deletion_success = False
                try:
                    await message.delete()
                    deletion_success = True
                except discord.Forbidden:
                    print("Did not have permission to delete message {} from {}!".format(message.id, author))
                except discord.NotFound:
                    print("Message {} from {} was already deleted".format(message.id, author))
                except discord.HTTPException as e:
                    print("Failed to delete message {} from {} : {}".format(message.id, author, e))

                if deletion_success:
                    self.send_info_message(author, message.channel.name, content)

    async def make_embed(self, author: discord.Member, deleted_content: str):
        user = await self.client.fetch_user(author.id)
        embed = discord.Embed(description=deleted_content, colour=author.colour)
        if author.avatar is None:
            embed.set_author(name=author.nick, icon_url = f"https://cdn.discord.com/embed/avatars/{user.discriminator}.png?size=128")
        else:
            embed.set_author(name=author.nick, icon_url = f"https://cdn.discord.com/avatars/{author.id}/{author.avatar}?size=128")
        return embed

    async def send_info_message(self, author: discord.Member, channel_id: str, deleted_content: str):
        if author.dm_channel is None:
            await author.create_dm()
        dm_channel = author.dm_channel
        content = f"Your post in <#{channel_id}> has been removed due to being within {str(datetime.timedelta(seconds=config.BUY_SELL_LIMIT_SECONDS))} of your last post."
        content += "\nThe message has been saved for you"
        embed = await self.make_embed(author, deleted_content)
        try:
            await dm_channel.send('\n'.join(content), embed=embed)
        except: # If we can't DM the user
            backup_channel = self.client.get_channel(config.BUY_SELL_BACKUP_DM_CHANNEL_ID)
            content = f"<@{author.id}> {content}"
            await backup_channel.send(content=content, embed=embed)

def setup(client):
    client.add_cog(Limiter(client))
