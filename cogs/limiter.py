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
        messages = await message.channel.history(after=time_limit)

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

    async def send_info_message(self, author: discord.Member, channel_name: str, deleted_content: str):
        if author.dm_channel is None:
            await author.create_dm()
        dm_channel = author.dm_channel
        content = "Your post in {} has been removed due to being within {} of your last post.\n".format(channel_name, str(datetime.timedelta(seconds=config.BUY_SELL_LIMIT_SECONDS)))
        content += "The message has been saved for you:\n"
        content += "```\n"
        content += deleted_content + "\n"
        content += "```"
        try:
            await dm_channel.send(content)
        except discord.Forbidden:
            print("Failed to message user {} due to missing permissions".format(author))
        except discord.HTTPException as e:
            print("Failed to message user {} : {}".format(author, e))

def setup(client):
    client.add_cog(Limiter(client))
