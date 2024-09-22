import discord
from discord.ext import commands
import sqlite3
from helper import strip, admin
import time
import datetime
# admin = asyncio.run(admin)

# Connect to the database
con = sqlite3.connect("economy.db")
cur = con.cursor()
# economy.db has the following tables:
# table - wallet
#	 col1 - id (int) - KEY
#	 col2 - balance (int) - default 0
#	 col3 - last_daily (int) - default 0

# admin wrapper
# def admin(func):

#	 async def wrapper(self, ctx, *args, **kwargs):
#		 ADMINS = (732415222706339840,)
#		 if ctx.author.id not in ADMINS:
#			 await ctx.send("Unfortunately, you are too weak and pathetic to comprehend this power. Sit down.")
#			 return

#		 await func(self, ctx, *args, **kwargs)

#	 return wrapper


class Economy(commands.Cog):
	def __init__(self, client):
		self.client = client
		self.bot_id = 1180364917417721957

	def get_balance(self, user_id):
		"""Returns the current balance of a user. (int)
		user_id: id of the user (int)"""
		res = cur.execute(f"SELECT balance FROM wallet WHERE id={user_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return 0

	def set_balance(self, user_id, new_balance):
		"""Sets the balance of a user to new_balance. If the user does not exist in the wallet table, a new row is created.
		user_id: id of the user (int)
		new_balance: balance to set the user to (int)"""
		cur.execute(f"INSERT INTO wallet(id, balance) VALUES({user_id}, {new_balance}) \
			ON CONFLICT(id) DO UPDATE SET(balance) = {new_balance}")
		con.commit()

	def add_balance(self, user_id, change):
		"""Changes the balance of a user by change. If the user does not exist, a new row is created.
		user_id: id of the user (int)
		change: change of their balance, can be positive or negative (int)"""
		new_bal = int(change + self.get_balance(user_id))
		self.set_balance(user_id, new_bal)

	def get_last_daily(self, user_id):
		"""Returns the Unix timestamp of the last time a user collected their daily. (int)
		user_id: id of the user (int)"""
		res = cur.execute(f"SELECT last_daily FROM wallet WHERE id={user_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return 0

	def set_last_daily(self, user_id, last_daily):
		"""Sets the last daily time of a user_id to last_daily. The user must exist by the time this function is called.
		user_id: id of the user (int)
		last_daily: UNIX timestamp to set the last daily time to (int)"""
		cur.execute(f"UPDATE wallet SET last_daily = {last_daily} WHERE id={user_id}")
		con.commit()
		print(f"Set last daily to {last_daily}")

	def compute_daily(self, user_id):
		"""Based on a variety of factors relating to the user, return the value they should earn from using $daily.
		user_id: id of the user (int)"""
		Upgrades = self.client.get_cog("Upgrades")
		return Upgrades.get_meta_value("base_daily")

	def available_daily(self, user_id, since_last_daily=None):
		"""Checks if the user is able to collect a daily."""
		if since_last_daily is None:
			since_last_daily = int(time.time()) - self.get_last_daily(user_id)
		return since_last_daily >= 86400

	@commands.command(name="wallet", aliases=["balance"])
	async def wallet(self, ctx, user_id = None):
		"""Tells the user their current balance."""
		user_id = strip(user_id, ctx.message.author.id)
		string = f"You currently have {self.get_balance(user_id)} O-bucks!"
		await ctx.send(string)

	@commands.command(name="daily")
	async def daily(self, ctx):
		"""Collect your daily O-bucks."""
		# check that the user is eligible
		user_id = ctx.message.author.id
		now = int(time.time())
		since_last_daily = now - self.get_last_daily(user_id)
		print(f"User {user_id} attempted to collect daily. Time since last collect: {since_last_daily}.")
		available = self.available_daily(user_id, since_last_daily)
		if available:
			amount = self.compute_daily(user_id)
			self.add_balance(user_id, amount)
			new_bal = self.get_balance(user_id)
			self.set_last_daily(user_id, now)
			await ctx.send(f"You have collected {amount} O-bucks! Your new balance is {new_bal} O-bucks.")
			return
		else:
			await ctx.send(f"You've already collected your daily rations, peasant. You must wait {datetime.timedelta(seconds=(86400-since_last_daily))} until you may collect again.")

	@commands.command(name="welfare", aliases=["wf"])
	async def welfare(self, ctx):
		"""Gives you 1 O-buck if your broke ass has no money."""
		user_id = ctx.author.id 
		bal = self.get_balance(user_id)
		if bal > 0:
			await ctx.send("You aren't nearly poor enough for my handouts. Don't be greedy.")
		else:
			self.add_balance(user_id, 1)
			await ctx.send("Omegacat is kind. Worship omegacat. Don't do something stupid with this dollar.")

	@commands.command(name="secret_sacrifice", hidden=True)
	async def secret(self, ctx):
		"""Halves your money."""
		user_id = ctx.author.id 
		cur = self.get_balance(user_id)
		self.set_balance(user_id, int(cur/2))
		await ctx.send("Your money has been halved. Congratulations!")

	@commands.command(name="give")
	async def give(self, ctx, amount = None, user_id = None):
		"""Gives a selected user some O-bucks. Format: `$give [amount] [target_user]`.
		You can either ping the user or copy their ID through developer mode."""
		if amount is None or user_id is None or not amount.isdigit() or strip(user_id, None) is None:
			await ctx.send("Invalid input!")
			return
		amount = int(amount)
		if amount <= 0:
			await ctx.send("You must send a positive value! Giving your entire net worth instead...")
			amount = self.get_balance(ctx.author.id)
		user_id = strip(user_id)
		if ctx.author.id == user_id:
			await ctx.send("You can't give money to yourself!")
			return
		if amount > self.get_balance(ctx.author.id) or amount < 0:
			await ctx.send("You don't have enough money!")
			return


		self.add_balance(ctx.author.id, -amount)
		self.add_balance(user_id, amount)

		# SECRET: if user attempts to give money to Omegacat
		if user_id == self.bot_id and amount > 10:
			Upgrades = self.client.get_cog("Upgrades")
			if Upgrades.roll_raising_daily(amount):
				new_daily = Upgrades.get_meta_value("base_daily")
				level = new_daily - 1000
				reward = 400 + 25*level
				self.add_balance(ctx.author.id, reward)
				await ctx.send("A beam of light shines upon you from the gods...")
				await ctx.send(f"The base daily value has **permanently** increased by 1 O-buck, to a new value of {new_daily} O-bucks. You have also been given a reward of {reward} O-bucks!")
			else:
				total_sacrificed = Upgrades.get_meta_value("give_sacrificed")
				await ctx.send("I appreciate your gift. If you and your kind bring me more, perhaps something will happen...")
				await ctx.send(f"Total amount sacrificed: **{total_sacrificed}** O-bucks.")
			return

		
		await ctx.send(f"Successfully given {amount} O-bucks!")




	@commands.command(name="setbal", hidden=True)
	@admin
	async def admin_set_balance(self, ctx, new_balance, user_id = None):
		"""ADMIN COMMAND
		Sets a user's balance to the specified value. Use caution."""
		user_id = strip(user_id, ctx.message.author.id)
		self.set_balance(user_id, new_balance)
		await ctx.send(f"User <@{user_id}> successfully set to have {new_balance} O-bucks.")




async def setup(client):
	await client.add_cog(Economy(client))
	print("Economy loaded within file.")
