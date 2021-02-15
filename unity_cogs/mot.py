import logging

import discord
from discord.ext import commands

from unity_services import mot
from unity_util.menu import DEFAULT_CONTROLS, menu


class MOT(commands.Cog):
    def __init__(self, client):
        self.client = client

    # Events

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("MOT search cog online")

    # Commands

    @commands.command(name="mot")
    async def _mot(self, ctx, registration: str, year: int = 0):
        vehicle = await mot.get_vehicle(registration)

        if not vehicle:
            error_embed = self.make_error_embed(ctx, "noVehicleFound")
            await ctx.send(embed=error_embed)
            return

        if year:
            mot_tests = [vehicle.tests.index(i) for i in vehicle.tests if i.completed_date.year == year]

            if not mot_tests:
                error_embed = self.make_error_embed(ctx, "noTestsFound")
                await ctx.send(embed=error_embed)
                return

            mot_embeds = [vehicle.make_embed(i) for i in mot_tests]

            if len(mot_embeds) == 1:
                await ctx.send(embed=mot_embeds[0])
                return

            await menu(
                ctx,
                pages=mot_embeds,
                controls=DEFAULT_CONTROLS,
                message=None,
                page=0,
                timeout=180,
            )

        else:

            if len(vehicle.embeds) == 1:
                await ctx.send(embed=vehicle.embeds[0])
                return

            await menu(
                ctx,
                pages=vehicle.embeds,
                controls=DEFAULT_CONTROLS,
                message=None,
                page=0,
                timeout=120,
            )

    def make_error_embed(self, ctx, error_type: str) -> discord.Embed:
        error_codes = {
            "noVehicleFound": "No vehicle found matching that registration",
            "noTestsFound": "No MOT tests exist for that year",
        }
        return discord.Embed(
            description=error_codes[error_type],
            colour=ctx.guild.me.colour if ctx.guild else None,
        )


def setup(client):
    client.add_cog(MOT(client))
