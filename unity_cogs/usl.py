import logging
import re
import sys

import discord
from discord.ext import commands

from unity_services import universal_scammer_list as usl
from unity_util.embed_helper import error_message


EMBED_BANNED_COLOUR = 0xB00E0E
EMBED_NOT_BANNED_COLOUR = 0x3CB00E


class UniversalScammerList(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Universal Scammer List search cog online")

    @commands.command(name="usl")
    async def query_universal_scammer_list(self, ctx, *, username):
        """
        Queries the Universal Scammer List to get information about a user.
        """

        # Strip the username prefix, if it is present.
        # The USL API request will fail if we pass this in.
        username = username.replace("u/", "")
        username = username.replace("/", "")

        # Check reddit username format.
        regex = re.compile("[A-Za-z0-9_-]+$")

        if not regex.match(username):
            await error_message(
                ctx,
                "Invalid username format. Reddit usernames can consist of alphanumeric characters, hyphens and underscores only.",
                cmd_error=False
            )
            return

        logging.info(f"Received request to check USL for username: {username}")

        try:
            response = await usl.fetch_usl_user_data(username)
            await ctx.send(embed=self.make_embed(response))
        except RuntimeError as error:
            logging.warning(f"Error while querying USL API: {error}")
            await error_message(
                ctx,
                "Something went wrong while querying the USL database. Please try again later, or contact the moderators for assistance."
            )

    def make_embed(self, data: dict) -> discord.Embed:
        embed = discord.Embed(
            title="USL Search Results",
            colour=discord.Colour.red() if data["banned"] else discord.Colour.green(),
        )
        embed.add_field(name="Username", value=f"/u/{data['person']}")
        embed.add_field(name="Banned", value="Yes" if data["banned"] else "No")

        if data["banned"]:
            embed.set_footer(text="⚠️ DO NOT trade with this user! ⚠️")

        return embed


def setup(client):
    client.add_cog(UniversalScammerList(client))
