import sys
import motor
import logging
import discord
import datetime

from discord.ext import commands
from unity_util import bot_config


mongo = motor.motor_asyncio.AsyncIOMotorClient(host=bot_config.MONGODB_HOST, port=int(
    bot_config.MONGODB_PORT), replicaSet="rs01", username=bot_config.MONGODB_USERNAME, password=bot_config.MONGODB_PASSWORD, authSource=bot_config.MONGODB_DATABASE, authMechanism='SCRAM-SHA-1')
db = mongo[bot_config.MONGODB_DATABASE]

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{bot_config.LOGGING_FILENAME}')
])


class ReactReport(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Reaction report cog online.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.emoji.name != "⚠️":
            return

        # Get the message content (annoying)
        guild = self.client.get_guild(payload.guild_id)

        if not guild:
            logging.warning(f"React Report: failed to fetch guild with ID {payload.guild_id}")
            return

        channel = guild.get_channel(payload.channel_id)

        if not channel:
            logging.warning(f"React Report: failed to fetch channel with ID {payload.channel_id}")
            return

        message = await channel.fetch_message(payload.message_id)

        if not message:
            logging.warning(f"React Report: failed to fetch message with ID {payload.message_id}")
            return

        report_channel = guild.get_channel(bot_config.REPORT_CHANNEL_ID)

        if not report_channel:
            logging.warning(f"React Report: failed to fetch report output channel with ID {bot_config.REPORT_CHANNEL_ID}")
            return

        cur_time = datetime.datetime.now()
        timestamp = cur_time.strftime("%d/%m/%Y %H:%M:%S")

        data = {
            "message_id": payload.message_id,
            "reporter_id": payload.user_id,
            "channel_id": payload.channel_id,
            "message_content": message.clean_content,
            "report_timestamp": cur_time.utcfromtimestamp(0)
        }

        logging.info(f"Saving report data, message ID: {payload.message_id}")

        save_success = await self.save_report_data(data)

        if save_success:
            await report_channel.send(embed=self.create_new_report_embed(message, payload, timestamp))

    # Save report data to mongo
    async def save_report_data(self, data: dict):
        # Check if this message has been reported already.
        # If so, then do nothing.
        count = await db.reports.count_documents({"message_id": data["message_id"]})
        if count > 0:
            return False

        await db.reports.insert_one(data)
        return True

    def create_new_report_embed(self, message: discord.Message, payload: discord.RawReactionActionEvent, timestamp: str):
        # Fetch the user who reported the message.
        member = message.guild.get_member(payload.user_id)

        embed = discord.Embed(title="New report created", colour=discord.Colour.orange())
        embed.description = message.clean_content
        embed.add_field(name="Reporter", value=member.mention)
        embed.add_field(name="Timestamp", value=timestamp)

        return embed


def setup(client):
    client.add_cog(ReactReport(client))
