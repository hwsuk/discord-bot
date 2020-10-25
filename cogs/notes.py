import discord
import asyncio
import sys
import logging
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions, CheckFailure
import config
import re
import motor.motor_asyncio
import time
from datetime import datetime as dt
import random
import string

mongo = motor.motor_asyncio.AsyncIOMotorClient(host=config.MONGODB_HOST, port=int(
    config.MONGODB_PORT), replicaSet="rs01", username=config.MONGODB_USERNAME, password=config.MONGODB_PASSWORD, authSource=config.MONGODB_DATABASE, authMechanism='SCRAM-SHA-1')
db = mongo[config.MONGODB_DATABASE]

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
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

    @commands.group()
    @has_permissions(manage_roles=True)
    async def notes(self, ctx):
        if ctx.invoked_subcommand is None:
            pass

    @notes.command()
    @has_permissions(manage_roles=True)
    async def view(self, ctx, user:discord.Member):
        """View notes for a user"""
        user = str(user.id)
        notes = await self.get_notes(user)
        if notes == None:
            await ctx.send(embed=discord.Embed(title='No notes found for this user', colour=ctx.guild.me.colour))
            return
        elif len(notes) == 1:
            embed = await self.make_note_embed(notes=notes, colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return

        index = {'min': 0, 'current': 0, 'max': len(notes) - 1}
        embed = await self.make_note_embed(notes=notes, index=index, colour=ctx.guild.me.colour)
        messageObject = await ctx.send(embed=embed)
        allowedEmojis = await self.add_buttons(ctx, messageObject, index)

        def reaction_info_check(reaction, userObject):
            return userObject == ctx.author and reaction.message.id == messageObject.id and reaction.emoji in allowedEmojis

        # Wait for a reaction
        try:
            reaction, userObject = await self.client.wait_for('reaction_add', timeout=180.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            index['current'] += 1
            messageObject = await messageObject.channel.fetch_message(messageObject.id)
            await messageObject.remove_reaction(reaction.emoji, ctx.author)
            await self.edit_result(ctx, notes, index, messageObject)

    @notes.command()
    @has_permissions(manage_roles=True)
    async def find(self, ctx, hash: to_lower):
        """Find user note by hash"""
        if len(hash) != 7:
            embed = discord.Embed(title="❌ That doesn't look like a valid note hash", colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return
        data = await db.notes.find_one({'hash': hash})
        if data is None:
            await ctx.send(embed=discord.Embed(title='No note found with this hash', colour=ctx.guild.me.colour))
            return
        embed = await self.make_note_embed(notes=[data], colour=ctx.guild.me.colour)
        await ctx.send(embed=embed)

    @notes.command(aliases=['remove'])
    @has_permissions(manage_roles=True)
    async def delete(self, ctx, hash: to_lower):
        """Delete a user note"""
        if len(hash) != 7:
            embed = discord.Embed(description="❌ That doesn't look like a valid note hash", colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return
        data = await db.notes.find_one({'hash': hash})
        if data is None:
            await ctx.send(embed=discord.Embed(title='No note found with this hash', colour=ctx.guild.me.colour))
            return
        embed = await self.make_note_embed(notes=[note], colour=ctx.guild.me.colour)
        await ctx.send(embed=embed)
        messageObject = await ctx.send('Are you sure you want to remove this user from the database?')
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
                    await db.notes.delete_one({"hash": hash})
                    logging.info(f"Removed user note {hash} from the database")
                    embed = discord.Embed(description=f"User note with hash `{hash}` removed from the database successfully 🤠", colour=ctx.guild.me.colour)
                    await ctx.send(embed=embed)
                except Exception as err:
                    logging.error(f"ERROR REMOVING NOTE: {err}")
                    await ctx.send("Couldn't remove the note from the database for some reason. Please consult the logs for more details")

    @notes.command(aliases=['add'])
    @has_permissions(manage_roles=True)
    async def create(self, ctx, user:discord.Member):
        await ctx.send(embed=discord.Embed(colour=ctx.guild.me.colour, description=f"Please enter a note for {user.mention}"))

        def check(m):
            return m.channel == ctx.channel and m.author == ctx.author

        msg = await self.client.wait_for('message', check=check)
        note = {'user': str(user.id),
        'content': msg.content,
        'added_by': str(ctx.author.id),
        'hash': await self.gen_hash(),
        'date_added': int(time.time())}
        try:
            await db.notes.insert_one(note)
            logging.info(f"Added user note {hash} to the database")
            embed = await self.make_note_embed(notes=[note], colour=ctx.guild.me.colour)
            await ctx.send(content="Saved note successfully 🤠", embed=embed)
        except Exception as err:
            logging.error(f"ERROR ADDING NOTE: {err}")
            await ctx.send("Couldn't add the note to the database for some reason. Please consult the logs for more details")

    async def edit_result(self, ctx, notes, index, messageObject):
        embed = await self.make_note_embed(notes=notes, index=index, colour=ctx.guild.me.colour)
        await messageObject.edit(embed=embed)
        allowedEmojis = await self.add_buttons(ctx, messageObject, index) # add buttons and get allowedEmojis

        def reaction_info_check(reaction, userObject):
            return userObject == ctx.author and reaction.message.id == messageObject.id and reaction.emoji in allowedEmojis

        # Wait for a reaction
        try:
            reaction, userObject = await self.client.wait_for('reaction_add', timeout=180.0, check=reaction_info_check)
        except asyncio.TimeoutError:
            await messageObject.clear_reactions()
            return
        else:
            # User has reacted with an emoji, find out which one
            if reaction.emoji == '▶':
                index['current'] += 1
                messageObject = await messageObject.channel.fetch_message(messageObject.id)
                await messageObject.remove_reaction(reaction.emoji, ctx.author)
                await self.edit_result(ctx, notes, index, messageObject)
            if reaction.emoji == '◀':
                index['current'] -= 1
                messageObject = await messageObject.channel.fetch_message(messageObject.id)
                await messageObject.remove_reaction(reaction.emoji, ctx.author)
                await self.edit_result(ctx, notes, index, messageObject)

    async def make_note_embed(self, notes:list=[], index:dict=None, colour:int=0):
        note = notes[index['current']] if index != None else notes[0]
        content = f"**Notes for <@{note['user']}>**\n{note['content']}"
        embed = discord.Embed(description=content, colour=colour)
        date = dt.fromtimestamp(note['date_added'])
        embed.add_field(name='Date Added', value=f"{date.day}/{date.month}/{date.year}", inline=True)
        embed.add_field(name='Added by', value=f"<@{note['added_by']}>", inline=True)
        embed.add_field(name='Hash', value=f"`{note['hash']}`", inline=True)
        if index != None:
            embed.set_footer(text=f"{index['current'] + 1} of {index['max'] + 1}")
        return embed

    async def add_buttons(self, ctx, messageObject, index):
        messageObject = await messageObject.channel.fetch_message(messageObject.id)
        oldReacts = []
        for reaction in messageObject.reactions:
            if reaction.me:
                oldReacts.append(reaction.emoji)
        if index['current'] == index['min']: # first result, no back arrow required
            allowedEmojis = ['▶']
        if index['current'] == index['max']: # last result, no forward arrow required
            allowedEmojis = ['◀']
        if index['min'] < index['current'] < index['max']: # a middle result, both arrows required
            allowedEmojis = ['◀','▶']
        if oldReacts == allowedEmojis:
            for reaction in messageObject.reactions:
                if reaction.me:
                    continue
                await messageObject.remove_reaction(reaction.emoji, ctx.author)
        else:
            await messageObject.clear_reactions()
            for emoji in allowedEmojis:
                await messageObject.add_reaction(emoji)
        return allowedEmojis

    async def get_notes(self, user):
        n = await db.notes.count_documents({"user": str(user)})
        if n == 0:
            return None
        data = db.notes.find({"user": str(user)})

        notes = []
        data.limit(n)
        async for note in data:
            notes.append(note)
        return notes

    async def gen_hash(self):
        unique = False
        while unique is False:
            hash = ''.join(random.choice(string.ascii_lowercase+string.digits) for i in range(7))
            data = await db.notes.find_one({'hash': hash})
            if data is None:
                unique = True
        return hash

def setup(client):
    client.add_cog(Notes(client))