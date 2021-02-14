import logging
import random
import string
import time
from datetime import datetime as dt
from typing import Tuple, Union

import discord
from discord.ext import commands
from discord.ext.commands import has_permissions

from unity_util.bot_config import db
from unity_util.embed_helper import error_message, success_message
from unity_util.menu import DEFAULT_CONTROLS, get_user_reply, menu, yes_or_no


def to_lower(word: str) -> str:
    return word.lower()


class Notes(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        logging.info("Notes cog online")

    # Commands

    @commands.group()
    @has_permissions(manage_roles=True)
    async def notes(self, ctx):
        """View moderator notes about users"""
        if ctx.invoked_subcommand is None:
            pass

    @notes.command()
    @has_permissions(manage_roles=True)
    async def view(self, ctx, user: discord.Member):
        """View notes for a user"""
        notes = await self.get_notes(str(user.id))

        if not notes:
            await error_message(ctx, "No notes found for this user", cmd_error=False)
            return
        elif len(notes) == 1:
            embed = self.make_note_embed(
                note=notes[0], colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return

        embeds = [
            self.make_note_embed(
                notes[i], {"current": i, "max": len(notes) - 1}, ctx.guild.me.colour)
            for i in range(len(notes))
        ]
        embeds.reverse()  # Sort newest first
        await menu(
            ctx,
            pages=embeds,
            controls=DEFAULT_CONTROLS,
            message=None,
            page=0,
            timeout=180,
        )

    @notes.command()
    @has_permissions(manage_roles=True)
    async def find(self, ctx, note_hash: to_lower):
        """Find user note by hash"""
        if len(note_hash) != 7:
            embed = discord.Embed(
                title="❌ That doesn't look like a valid note hash",
                colour=ctx.guild.me.colour,
            )
            await ctx.send(embed=embed)
            return
        data = await db.notes.find_one({"hash": note_hash})
        if data:
            await ctx.send(embed=discord.Embed(title="No note found with this hash", colour=ctx.guild.me.colour))
            return
        embed = self.make_note_embed(note=data, colour=ctx.guild.me.colour)
        await ctx.send(embed=embed)

    @notes.command(aliases=["remove"])
    @has_permissions(manage_roles=True)
    async def delete(self, ctx, note_hash: to_lower):
        """Delete a user note"""
        if len(note_hash) != 7:
            embed = discord.Embed(
                description="❌ That doesn't look like a valid note hash",
                colour=ctx.guild.me.colour,
            )
            await ctx.send(embed=embed)
            return
        note = await db.notes.find_one({"hash": note_hash})
        if not note:
            embed = discord.Embed(
                description="❌ No note found with this hash", colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return
        embed = self.make_note_embed(note=note, colour=ctx.guild.me.colour)
        message = await ctx.send("Are you sure you want to remove this note from the database?", embed=embed)
        confirmation = await yes_or_no(ctx, message)
        if not confirmation:  # None or False
            await message.clear_reactions()
            return
        try:
            await message.clear_reactions()
            await db.notes.delete_one({"hash": note_hash})
            logging.info(f"Removed user note {note_hash} from the database")
            await success_message(
                ctx,
                f"Note `{note_hash}` removed from the database successfully 🤠",
            )
        except Exception as err:
            logging.error(f"ERROR REMOVING NOTE: {err}")
            await error_message(ctx, err)

    @notes.command(aliases=["add", "new", "create"])
    @has_permissions(manage_roles=True)
    async def create(self, ctx, user: discord.Member, *, note_content: str = ""):
        """Create a note about a user"""
        if not note_content:
            await ctx.send(
                embed=discord.Embed(
                    colour=ctx.guild.me.colour,
                    description=f"Please enter a note for {user.mention}",
                )
            )

        note_content = await get_user_reply(ctx, timeout=300.0)
        if not note_content:
            return

        note = {
            "user": str(user.id),
            "content": note_content,
            "added_by": str(ctx.author.id),
            "hash": await self.gen_hash(),
            "date_added": int(time.time()),
        }
        try:
            await db.notes.insert_one(note)
            logging.info(f"Added user note {note['hash']} to the database")
            embed = self.make_note_embed(note=note, colour=ctx.guild.me.colour)
            await ctx.send("Saved note successfully 🤠", embed=embed)
        except Exception as err:
            logging.error(f"ERROR ADDING NOTE: {err}")
            await error_message(ctx, err)

    # Helper functions

    def make_note_embed(self, note: dict, index: dict = None, colour: discord.Colour = 0) -> discord.Embed:
        """Construct embed from note"""
        content = f"**Notes for <@{note['user']}>**\n{note['content']}"
        embed = discord.Embed(description=content, colour=colour)
        date = dt.fromtimestamp(note["date_added"])
        embed.add_field(
            name="Date Added", value=f"{date.day}/{date.month}/{date.year}", inline=True)
        embed.add_field(name="Added by",
                        value=f"<@{note['added_by']}>", inline=True)
        embed.add_field(name="Hash", value=f"`{note['hash']}`", inline=True)
        if index:
            embed.set_footer(
                text=f"{index['current'] + 1} of {index['max'] + 1}")
        return embed

    async def get_notes(self, user_id: str) -> Union[Tuple[dict], None]:
        """Retrieve notes from DB by user ID"""
        notes = await db.notes.find({"user": user_id}).to_list()
        return tuple(notes) if notes else None

    # Used in create command
    async def gen_hash(self) -> str:
        """Generate unique hash for a note"""
        unique = False
        while not unique:
            note_hash = "".join(random.choice(
                string.ascii_lowercase + string.digits) for i in range(7))
            data = await db.notes.find_one({"hash": note_hash})
            if not data:
                return note_hash


def setup(client):
    client.add_cog(Notes(client))
