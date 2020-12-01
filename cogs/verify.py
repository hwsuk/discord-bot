import json
import time
import discord
from discord.ext import commands, tasks
import asyncio
import motor.motor_asyncio
from datetime import datetime as dt
import logging
import re
import praw
import config
import sys

with open('config.json', 'r') as f:
    conf = json.load(f)

reddit = praw.Reddit(client_id=config.PRAW_CLIENT_ID, client_secret=config.PRAW_CLIENT_SECRET,
                     username=config.PRAW_USERNAME, password=config.PRAW_PASSWORD, user_agent=config.PRAW_USER_AGENT)

mongo = motor.motor_asyncio.AsyncIOMotorClient(host=config.MONGODB_HOST, port=int(
    config.MONGODB_PORT), replicaSet="rs01", username=config.MONGODB_USERNAME, password=config.MONGODB_PASSWORD, authSource=config.MONGODB_DATABASE, authMechanism='SCRAM-SHA-1')
db = mongo[config.MONGODB_DATABASE]

logging.basicConfig(level=logging.INFO, format="[%(levelname)s]\t %(name)s: %(message)s", handlers=[
    logging.StreamHandler(sys.stdout),
    logging.FileHandler(f'./logs/{config.LOGGING_FILENAME}')
])

class Verify(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.monitor_db.start()

    def cog_unload(self):
        self.monitor_db.cancel()

    # Events
    @commands.Cog.listener()
    async def on_ready(self):
        print('Verify cog online')
        #First we check the queue for any old additions if this garbage was down
        backlog = await db.queue.find({}).to_list(None)
        if(backlog):
            logging.debug('Catching up, one sec')
            for item in backlog:
                user = await db.users.find_one({"_id": item["ref"]})
                if user.get("verified"):
                    await self.set_verified(user['discord']['id'])
                else:
                    logging.warning(f'Weird, {item["ref"]} was in the queue but is not verified.')
                await db.queue.find_one_and_delete({"_id": item['_id']})

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = await db.users.find_one({"discord.id": str(member.id)})

        if(data and data.get("verified")):  # Check if user has verified online first
            await self.set_verified(member.id)

    @commands.Cog.listener()
    async def on_member_ban(self, member):
        await db.users.find_one_and_update({"discord.id": member.id}, {"verified": False, "banned": True})
        logging.info(
            f'BANNED {member.name + "#" + member.discriminator} ON {member.server.name}')

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await db.users.find_one_and_update({"discord.id": user.id}, {"banned": False})
        logging.info(
            f'UNBANNED {user.name + "#" + user.discriminator} ON {guild.name}')

    # Commands

    @commands.command(aliases=['verification'])
    async def verify(self, ctx):
        """Instructions on how to verify"""
        embed = discord.Embed(
            title='Verify here!',
            url='https://verify.hardwareswap.uk'
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def whois(self, ctx, user):
        """Search by Discord username, ID, mention or Reddit username for a verified hwsuk user"""
        # Syntax: !whois [username]
        # Examples: !whois issythegurl
        # !whois @issy#4200
        # !whois 377212919068229633
        # !whois u/issythegurl
        if len(ctx.message.mentions) == 1:
            user_data = await self.get_user(ctx.message.mentions[0].id)
        else:
            user_data = await self.get_user(user)
        if not user_data:
            user = user.replace('`', '``')
            embed = discord.Embed(title = "Whois results:", description=f"No results found for {user}")
            await ctx.send(embed=embed)
            return
        else:
            embed = await self.make_whois_embed(user_data)
            await ctx.send(embed=embed)

    @commands.command()
    async def editflair(self, ctx, user, flair):
        """Edit a user's trade role/flair"""
        if int(config.DISCORD_UPDATER_ROLE) not in [i.id for i in ctx.message.author.roles]:
            desc = "Hey, looks like you don't have permission to do this!\nPlease contact a mod if you feel should have this permission"
            embed = discord.Embed(description=desc, colour=ctx.guild.me.colour)
            await ctx.send(embed=embed)
            return

        if len(ctx.message.mentions) == 1:
            user_data = await self.get_user(ctx.message.mentions[0].id)
        else:
            user_data = await self.get_user(user)

        if not user_data:
            user = user.replace('`', '``')
            embed = discord.Embed(description=f"No results found for {user}")
            await ctx.send(embed=embed)
            return

        if flair not in conf['flairs']:
            embed = discord.Embed(
                description=f"Flair {flair} not found 🙁".replace('`', '``'),
                color=ctx.guild.me.colour
            )
            await ctx.send(embed=embed)
            return

        # remove old role
        await self.remove_trades(user_data['discord']['id'])
        # set flair and new role
        if await self.set_trade_flair(user_data, flair) == True:
            desc = [f"✅ Flair set successfully for {user_data['reddit']['name']}"]
        else:
            desc = [
                f"❌ Error setting trade flair for {user_data['reddit']['name']}"]
        # Set the discord role
        if await self.set_trade_role(user_data, flair) == True:
            desc.append(
                f"✅ Role set successfully for <@{user_data['discord']['id']}>")
        else:
            desc.append(
                f"❌ Error setting trade role for <@{user_data['discord']['id']}>")

        embed = discord.Embed(description="\n".join(desc))
        await ctx.send(embed=embed)

    @commands.command()
    async def status(self, ctx):
        """Show your verification status"""
        user_data = await self.get_user(str(ctx.author.id))
        if not user_data:
            embed = discord.Embed(
                description="Looks like you're not verified. Please [verify here!](https://verify.hardwareswap.uk)")
            embed.set_author(name="User not found 🙁")
            await ctx.send(embed=embed)
            return
        embed = discord.Embed(
            title="Verification status"
        )
        embed.add_field(
            name="Discord",
            value=f"<@{user_data['discord']['id']}>",
            inline=True
        )
        embed.add_field(
            name="Reddit",
            value=f"u/{user_data['reddit']['name']}",
            inline=True
        )
        embed.add_field(
            name="Verified",
            value=user_data['verified'],
            inline=True
        )
        days_ago = dt.now() - dt.fromtimestamp(user_data['verified_at'])
        embed.set_footer(text=f"Verified {days_ago.days} days ago")
        await ctx.send(embed=embed)

    @commands.command(name='removeuser', aliases=['remove_user'])
    async def remove_user(self, ctx, user):
        """Removes a user from the verification database"""
        if int(config.DISCORD_UPDATER_ROLE) not in [i.id for i in ctx.message.author.roles]:
            desc = "Hey, looks like you don't have permission to do this!\nPlease contact a mod if you feel should have this permission"
            await ctx.send(embed=discord.Embed(description=desc))
            return
        if len(ctx.message.mentions) == 1:
            user_data = await self.get_user(ctx.message.mentions[0].id)
        else:
            user_data = await self.get_user(user)
        if user_data == None:
            user = user.replace('`', '``')
            embed = discord.Embed(description=f"No results found for `{user}`")
            embed.set_author(name="User not found")
            await ctx.send(embed=embed)
            return
        embed = await self.make_whois_embed(user_data)
        await ctx.send(embed=embed)
        message_object = await ctx.send('Are you sure you want to remove this user from the database?')
        emojis = ['✅', '❌']
        for i in emojis:
            await message_object.add_reaction(i)
        def reaction_check(reaction, user):
            return (user == ctx.author) and (reaction.message.id == message_object.id) and (reaction.emoji in emojis)
        try:
            reaction, user = await self.client.wait_for('reaction_add', timeout=120.0, check=reaction_check)
        except asyncio.TimeoutError:
            try:
                await message_object.clear_reactions()
            except:
                pass
            return
        else:
            # The user has reacted with an emoji in the list, let's find out which one
            if reaction.emoji == '❌':
                await message_object.clear_reactions()
                return
            if reaction.emoji == '✅':  # Execute order 66
                try:
                    await db.users.delete_one({"discord.id": f"{user_data['discord']['id']}"})
                    logging.info(f"Removed user {user_data['discord']['username']} from the database")
                    server = self.client.get_guild(int(config.DISCORD_SERVER_ID))
                    member = server.get_member(int(user_data['discord']['id']))
                    verified_role = server.get_role(int(config.DISCORD_VERIFIED_ROLE))
                    await member.remove_roles(verified_role)
                    embed = discord.Embed(description=f"User <@{user_data['discord']['id']}> removed from the database successfully 🤠")
                    await ctx.send(embed=embed)
                except Exception as err:
                    logging.error(f"ERROR REMOVING USER: {err}")
                    await ctx.send("Couldn't remove the user from the database for some reason. Please consult the logs for more details")

    # Helper functions

    # Useful for verification event
    async def set_verified(self, member_id):
        # Get guild object from ID
        server = self.client.get_guild(int(config.DISCORD_SERVER_ID))
        # Get role object of verified role by ID
        role = server.get_role(int(config.DISCORD_VERIFIED_ROLE))
        # Get member object by discord user ID
        member = server.get_member(int(member_id))

        if member:  # Someone might verify before they join the server
            try:
                await member.add_roles(role)  # Add user as verified
                # Send the verified message
                await member.send("Congratulations! You are now verified!")
                logging.info(
                    f'VERIFIED {member.name}#{member.discriminator} ON {server.name}')

            except Exception as e:
                # Log an error if there was a problem
                logging.error(
                    f'ERROR ADDING ROLE FOR {member.name}#{member.discriminator} IN {server.name}: {e}')

    # Useful for whois and editflair
    async def get_user(self, user: str) -> dict:
        discord_discrim_regex = re.compile("[\w]*#[0-9]{4}")  # eg. issy#4200
        if user.isdigit() and len(user) == 18:  # eg. 377212919068229633
            user_type = 'discord.id'
        # eg. /u/issythegurl or u/issythegurl
        elif user.startswith('u/') or user.startswith('/u/'):
            user = user.split('u/')[1]
            user_type = 'reddit.name'
        elif discord_discrim_regex.match(user) != None:
            user_type = 'discord.name'
        else:
            # Guess if it's a Reddit or Discord user
            for i in ['reddit.name','discord.username']:
                data = await db.users.find_one({f"{i}": {"$regex": f"^{user}$", "$options": "i"}})
                if data:
                    return data
                else:
                    continue
            if not data:
                return {}
        data = await db.users.find_one({f"{user_type}": {"$regex": f"^{user}$", "$options": "i"}})
        if data:
            return data
        return {}

    # Used for the whois commmand
    async def make_whois_embed(self, user_data: dict) -> discord.Embed:
        embed = discord.Embed()
        embed.set_author(name='Whois results:')
        embed.add_field(
            name='Discord', value=f"<@{user_data['discord']['id']}>", inline=True)
        embed.add_field(
            name='Reddit', value=f"[u/{user_data['reddit']['name']}](https://www.reddit.com/user/{user_data['reddit']['name']})", inline=True)
        trades = await self.get_trades(user_data['discord']['id'])
        if trades:
            embed.add_field(name='Trades', value=trades, inline=False)
        days_ago = dt.now() - dt.fromtimestamp(user_data['verified_at'])
        embed.set_footer(text=f"Verified {days_ago.days} days ago")
        return embed

    # Used in for whois and editflair
    async def get_trades(self, discord_id) -> str:
        """Get the trade role of a member"""
        trade_roles = [conf['flairs'][i]['rid'] for i in conf['flairs']]
        guild = self.client.get_guild(int(config.DISCORD_SERVER_ID))
        member = guild.get_member(int(discord_id))
        # returns all roles in member, lowest in hierarchy first
        member_roles = member.roles
        member_roles.reverse()  # get highest trade roles first
        member_trade_roles = [i for i in member_roles if i.id in trade_roles]
        if not member_trade_roles:
            return
        elif len(member_trade_roles) == 1:
            return member_trade_roles[0].name
        else: # If member_trade_roles > 1
            await member.remove_roles(member_trade_roles[1:])
            return member_trade_roles[0].name

    # Used in editflair
    async def remove_trades(self, discord_id: int):
        """Remove all trade roles from a member"""
        # Get guild object from ID
        server = self.client.get_guild(int(config.DISCORD_SERVER_ID))
        # Get member object by discord user ID
        member = server.get_member(int(discord_id))
        trade_roles = [conf['flairs'][i]['rid'] for i in conf['flairs']]
        member_trade_roles = [i for i in member.roles if i.id in trade_roles]
        await member.remove_roles(member_trade_roles)

    # Useful for editflair
    async def set_trade_flair(self, user_data, flair):
        try:
            flair_text = f"{flair} Trades"
            reddit_name = user_data['reddit']['name'].replace(
                "'", "").replace("{", "").replace("}", "")
            reddit.subreddit("hardwareswapuk").flair.set(str({user_data["reddit"]["name"] if user_data else None}).replace(
                "'", "").replace("{", "").replace("}", ""), flair_text, css_class=flair_text.replace("+", ""))
        except Exception as err:
            logging.error(
                f"ERROR SETTING FLAIR FOR {user_data['reddit']['name']}: {err}")
            return False
        return True

    # Useful for editflair
    async def set_trade_role(self, user_data, flair):
        # Get guild object from ID
        server = self.client.get_guild(int(config.DISCORD_SERVER_ID))
        # Get role object of verified role by ID
        role = server.get_role(conf['flairs'][flair]['rid'])
        # Get member object by discord user ID
        member = server.get_member(int(user_data['discord']['id']))
        try:
            await member.add_roles(role)
            return True
        except Exception as err:
            logging.error(
                f"ERROR ADDING ROLE FOR {member.name}#{member.discriminator} IN {server.name}: {err}")
            return False

    # Tasks

    @tasks.loop(seconds=20)
    async def monitor_db(self):
        """Monitor DB for changes"""
        try:
            logging.info("Monitoring DB")
            async for change in db.queue.watch():
                if change["operationType"] == "insert":
                    user = await db.users.find_one({"_id": change["fullDocument"]["ref"]})
                    if user.get("verified"):
                        await self.set_verified(user['discord']['id'])
                        await db.queue.find_one_and_delete({"_id": change["fullDocument"]['_id']})
        except Exception as e:
            logging.error(f'ERROR MONITORING DB: {e}')
            logging.warning('WAITING BEFORE TRYING AGAIN')
            time.sleep(5)

def setup(client):
    client.add_cog(Verify(client))
