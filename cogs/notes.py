import discord
import asyncio
import sys
import logging
from discord.ext import commands
from discord.ext.commands import has_permissions
import config
import motor.motor_asyncio
import time
from datetime import datetime as dt
import random
import string
from typing import Tuple
from redbot.core.utils.menus import menu, prev_page, next_page

CUSTOM_CONTROLS = {"⬅️": prev_page, "➡️": next_page}

mongo = motor.motor_asyncio.AsyncIOMotorClient(host=config.MONGODB_HOST, port=int(
    config.MONGODB_PORT), replicaSet="rs01", username=config.MONGODB_USERNAME, password=config.MONGODB_PASSWORD, authSource=config.MONGODB_DATABASE, authMechanism='SCRAM-SHA-1')
db = mongo[config.MONGODB_DATABASE]

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{config.LOGGING_FILENAME}')
])

def to_lower(word: str):
    return word.lower()

class Notes(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Feedback cog online')

# Commands

    @commands.group()
    @has_permissions(manage_roles=True)
    async def notes(self, ctx):
        """View moderator notes about users"""
        if ctx.invoked_subcommand is None:
            pass

    @notes.command()
    @has_permissions(manage_roles=True)
    async def view(self, ctx, user:discord.Member):
        """View notes for a user"""
        notes = await self.get_notes(str(user.id))

        if not notes:
            await self.no_results(ctx)
            return
        elif len(notes) == 1:
            embed = self.make_note_embed(note=notes[0], colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return

        embeds = [self.make_note_embed(notes[i], {'current': i, 'max': len(notes) - 1}, ctx.guild.me.colour) for i in range(len(notes))]
        await menu(ctx, pages=embeds, controls=CUSTOM_CONTROLS, message=None, page=0, timeout=180)

    @notes.command()
    @has_permissions(manage_roles=True)
    async def find(self, ctx, note_hash: to_lower):
        """Find user note by hash"""
        if len(note_hash) != 7:
            embed = discord.Embed(title="❌ That doesn't look like a valid note hash", colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return
        data = await db.notes.find_one({'hash': note_hash})
        if data is None:
            await ctx.send(embed=discord.Embed(title='No note found with this hash', colour=ctx.guild.me.colour))
            return
        embed = self.make_note_embed(note=[data], colour=ctx.guild.me.colour)
        await ctx.send(embed=embed)

    @notes.command(aliases=['remove'])
    @has_permissions(manage_roles=True)
    async def delete(self, ctx, note_hash: to_lower):
        """Delete a user note"""
        if len(note_hash) != 7:
            embed = discord.Embed(description="❌ That doesn't look like a valid note hash", colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return
        note = await db.notes.find_one({"hash": note_hash})
        if not note:
            embed = discord.Embed(description="❌ No note found with this hash", colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return
        embed = self.make_note_embed(note=note, colour=ctx.guild.me.colour)
        await ctx.send(embed=embed)
        messageObject = await ctx.send('Are you sure you want to remove this note from the database?')
        emojis = ['✅', '❌']
        for i in emojis:
            await messageObject.add_reaction(i)

        def reaction_check(reaction, user):
            return user == ctx.author and reaction.message.id == messageObject.id and reaction.emoji in emojis

        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=180.0, check=reaction_check)
        except asyncio.TimeoutError:
            try:
                await messageObject.clear_reactions()
            except:
                pass
            return
        else:
            # The user has reacted with an emoji in the list, let's find out which one
            if reaction.emoji == '❌':
                await messageObject.clear_reactions()
                return
            if reaction.emoji == '✅':  # Execute order 66
                try:
                    await messageObject.clear_reactions()
                    await db.notes.delete_one({"hash": note_hash})
                    logging.info(f"Removed user note {note_hash} from the database")
                    embed = discord.Embed(description=f"User note with hash `{note_hash}` removed from the database successfully 🤠", colour=ctx.guild.me.colour)
                    await ctx.send(embed=embed)
                except Exception as err:
                    logging.error(f"ERROR REMOVING NOTE: {err}")
                    await ctx.send("Couldn't remove the note from the database for some reason. Please consult the logs for more details")

    @notes.command(aliases=['add', 'new'])
    @has_permissions(manage_roles=True)
    async def create(self, ctx, user: discord.Member, *, note_content: str = ''):
        """Create a note about a user"""
        await ctx.send(embed=discord.Embed(colour=ctx.guild.me.colour, description=f"Please enter a note for {user.mention}"))

        if not note_content:
            def check(m):
                return m.channel == ctx.channel and m.author == ctx.author

            msg = await self.client.wait_for('message', check=check)
            note_content = msg.content

        note = {'user': str(user.id),
        'content': note_content,
        'added_by': str(ctx.author.id),
        'hash': await self.gen_hash(),
        'date_added': int(time.time())}
        try:
            await db.notes.insert_one(note)
            logging.info(f"Added user note {note['note_hash']} to the database")
            embed = self.make_note_embed(notes=note, colour=ctx.guild.me.colour)
            await ctx.send(content="Saved note successfully 🤠", embed=embed)
        except Exception as err:
            logging.error(f"ERROR ADDING NOTE: {err}")
            await ctx.send("Couldn't add the note to the database for some reason. Please consult the logs for more details")

# Helper functions

    def make_note_embed(self, note: dict, index: dict, colour: discord.Colour = 0) -> discord.Embed:
        """Construct embed from note"""
        content = f"**Notes for <@{note['user']}>**\n{note['content']}"
        embed = discord.Embed(description=content, colour=colour)
        date = dt.fromtimestamp(note['date_added'])
        embed.add_field(name='Date Added', value=f"{date.day}/{date.month}/{date.year}", inline=True)
        embed.add_field(name='Added by', value=f"<@{note['added_by']}>", inline=True)
        embed.add_field(name='Hash', value=f"`{note['hash']}`", inline=True)
        if index:
            embed.set_footer(text=f"{index['current'] + 1} of {index['max'] + 1}")
        return embed

    async def get_notes(self, user_id: str) -> Tuple[dict]:
        """Retrieve notes from DB by user ID"""
        n = await db.notes.count_documents({"user": user_id})
        if n == 0:
            return ()
        data = db.notes.find({"user": user_id})
        notes = []
        data.limit(n)
        async for note in data:
            notes.append(note)
        return tuple(notes)

    # Used in create command
    async def gen_hash(self) -> str:
        """Generate unique hash for a note"""
        unique = False
        while not unique:
            note_hash = ''.join(random.choice(string.ascii_lowercase+string.digits) for i in range(7))
            data = await db.notes.find_one({'hash': note_hash})
            if not data:
                return note_hash

    async def no_results(self, ctx):
        embed = discord.Embed(description="❌ No notes found for this user", colour=ctx.guild.me.colour)
        await ctx.send(embed=embed)

def setup(client):
    client.add_cog(Notes(client))