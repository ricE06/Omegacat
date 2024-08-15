import discord
from discord.ext import commands
import sqlite3
from helper import strip, admin
import time
import datetime
from economy import Economy
import math
import table2ascii
from table2ascii import table2ascii as t2a, PresetStyle
import random


# Connect to the database
con = sqlite3.connect("reaper.db")
cur = con.cursor()
# reaper.db has one metadata table, and new tables are created for each game
# table - meta
#    col1 - game_id (int) KEY - counts up by 1 each game
#    col2 - target_score (int) - default 100000
#    col3 - base_cost (int) - default 100
#    col4 - growth_rate (real/float) - default 5
#    col5 - reward_pot (int) - default 0
#    col6 - last_reap (int) - default 0
#    col7 - active (int 0/1) - default 0
#    col8 - server
# added tables - named to each game's game_id ("game_{game_id}")
#    col1 - user_id (int) KEY
#    col2 - score (int) - default 0
#    col3 - reap_cost (int) - default meta.base_cost
#    col4 - last_reap (int) - default 0

SERVER_BOOSTERS = (753351321062735902, 391010310280052737, 732415222706339840, 826593346423226380, 322926915336011787, 565247072245121065, 1161831126495678484, 1132455776116559932, 298237075046793217)



class Reaper(commands.Cog):
	def __init__(self, client):
		self.client = client
		self.confirmation_state = False
		self.confirmation_command = ""
		self.temps = []
		self.cutoff_percentiles = ((75.0, 50, 500), (50.0, 200, 400), (25.0, 300, 300), (10.0, 500, 250), (-1.0, 750, 200))
		self.top_ten = {1:0.25, 2: 0.12, 3: 0.10, 4: 0.08, 5: 0.06, 6: 0.05, 7: 0.04, 8: 0.03, 9: 0.02, 10: 0.01}
		self.secret_activated = False

	# Wrapper to make sure a game has begun before the command is used
	def game_active(func):

	    async def wrapper(self, *args, **kwargs):
	        ctx = args[0]
	        game_id = self.get_active_id(ctx.guild.id)
	        if game_id == -1:
	            await ctx.send("There is no active game!")
	            return

	        await func(self, *args, **kwargs)

	    return wrapper

	def reset_confirmation(self):
		self.confirmation_state = False
		self.confirmation_command = ""
		self.temps = []

	def set_confirmation(self, command, temp = []):
		self.confirmation_state = True
		self.confirmation_command = command
		self.temps = temp

	def get_next_id(self):
		"""Returns the next available game ID for reaper."""
		res = cur.execute("SELECT MAX(game_id) FROM meta")
		output = res.fetchone()[0]
		if output:
			return output+1
		return 1

	def get_active_id(self, server_id):
		"""Returns the id for an active game in the server, and -1 if there is none. 
		Assumes that only one game is active per server."""
		res = cur.execute(f"SELECT game_id FROM meta WHERE server = {server_id} AND active = 1")
		output = res.fetchone()
		if output:
			return output[0]
		return -1

	def get_table_name(self, game_id):
		"""Returns the name for the table in reaper.db."""
		return "game_" + str(game_id)

	def get_from_meta(self, game_id, attribute="last_reap"):
		"""Returns any attribute from a game in the meta table. If it does not exist, returns None."""
		res = cur.execute(f"SELECT {attribute} FROM meta WHERE game_id = {game_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return

	def set_to_meta(self, game_id, value, attribute="last_reap"):
		"""Sets any attribute in the meta table to the value. Assumes the game has been made."""
		cur.execute(f"UPDATE meta SET {attribute} = {value} WHERE game_id = {game_id}")
		con.commit()

	def add_to_meta(self, game_id, change, attribute="reward_pot"):
		"""Adds to any attribute in the meta table. NOTE: default is reward_pot instead of last_reap."""
		new_val = self.get_from_meta(game_id, attribute) + change
		self.set_to_meta(game_id, new_val, attribute)

	def create_game_table(self, game_id, base_cost):
		"""Creates a table for the corresponding game. Does NOT commit - used in conjunction with create_game."""
		name = self.get_table_name(game_id)
		cur.execute(f"CREATE TABLE {name} (user_id int primary key, score int default 0, reap_cost int default {base_cost}, last_reap int default 0)")
		# con.commit()

	def create_game(self, server_id, target_score = 100000, base_cost = 100, growth_rate = 5.0):
		"""Enters a meta entry for the game, activates it, and creates a table for it."""
		game_id = self.get_next_id()
		self.create_game_table(game_id, base_cost)
		now = int(time.time())
		cur.execute(f"INSERT INTO meta (game_id, target_score, base_cost, growth_rate, last_reap, active, server) \
			VALUES ({game_id}, {target_score}, {base_cost}, {growth_rate}, {now}, 1, {server_id})")
		con.commit()

	def deactivate_game(self, game_id):
		"""Ends the game."""
		cur.execute(f"UPDATE meta SET active = 0 WHERE game_id = {game_id}")
		con.commit()

	def get_time_since_reap(self, game_id, now = None):
		"""Returns the amount of time, in seconds, since the last reap."""
		if now is None:
			now = int(time.time())
		return now - self.get_from_meta(game_id)

	def get_from_user(self, game_id, user_id, attribute="score"):
		"""Returns any attribute from a user in the game table. If it does not exist, returns None."""
		game_name = self.get_table_name(game_id)
		res = cur.execute(f"SELECT {attribute} FROM {game_name} WHERE user_id = {user_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return

	def set_to_user(self, game_id, user_id, value, attribute="score"):
		"""Sets any attribute from a user in the game table. Assumes a row has been made."""
		game_name = self.get_table_name(game_id)
		cur.execute(f"UPDATE {game_name} SET {attribute} = {value} WHERE user_id = {user_id}")
		con.commit()

	def add_to_user(self, game_id, user_id, change, attribute="score"):
		"""Adds a certain amount to any integer attribute to the user. Assumes a row has been made."""
		new_val = self.get_from_user(game_id, user_id, attribute) + change
		self.set_to_user(game_id, user_id, new_val, attribute)

	def calculate_raw_score(self, time):
		"""Calculates the raw score using the decay formula."""
		decay_time = 4000.0
		decay_factor = 5.0
		return math.ceil((time/decay_factor)+(1-(1/decay_factor))*decay_time*math.atan(time/decay_time))

	async def calculate_score(self, user_id, time):
		"""Calculates the score after multipliers and bonuses."""
		mult = 1
		add = 0
		mult_string = ""
		# Secret adder
		if time % 100 == 66 and time > 100:
			mult_string += "\n" + "Secret? (+66)"
			add += 66
		if random.randint(0, 4) == 0:
			random_mult = self.generate_random_mult()
			mult_string += "\n" + f"You got a lucky multipler! ({random_mult}x)"
			mult *= random_mult
		# Server booster boost
		if user_id in SERVER_BOOSTERS:
			mult_string += "\n" + "Thanks for boosting the server! (1.2x)"
			mult *= 1.2

		return int((self.calculate_raw_score(time)+add)*mult), mult_string

	def generate_random_mult(self):
		mult = 2.0
		while random.randint(0, 1) == 1:
			mult += 0.5
		return mult


	def get_rankings(self, game_id):
		"""Returns a tuple of tuples of all user IDs and scores, sorted from highest score to lowest score."""
		game_name = self.get_table_name(game_id)
		res = cur.execute(f"SELECT user_id, score FROM {game_name} ORDER BY score DESC")
		return res.fetchall()

	async def end_game(self, game_id, rewards = True):
		"""Ends the game and distributes O-bucks rewards."""
		self.deactivate_game(game_id)
		if not rewards:
			return f"Game {game_id} ended."
		rankings = self.get_rankings(game_id)
		total_players = len(rankings)
		pot = self.get_from_meta(game_id, "reward_pot")
		# Iterate over the tuple and attach a rank, zero-indexed:
		rewards = []
		for rank, score_set in enumerate(rankings):
			amount = self.give_rewards(*score_set, rank+1, total_players, pot)
			rewards.append(amount)
		

		# output a final leaderboard with rewards
		rankings_formatted = [(rank+1, await self.get_username(user_id), score, amount) for (rank, (user_id, score)), amount in zip(enumerate(rankings), rewards)]
		rankings_header = ("Rank", "Username", "Points", "Rewards")
		output = t2a(header=rankings_header, body=rankings_formatted, first_col_heading=True)
		full_output = f"Game {game_id} ended. Standings and rewards: ```{output}```"
		return full_output

	def give_rewards(self, user_id, score, rank, total_players, pot):
		"""Distributes O-bucks rewards."""
		amount = self.calculate_rewards(score, rank, total_players, pot)
		Economy = self.client.get_cog("Economy")
		Economy.add_balance(user_id, amount)
		return amount

	def calculate_rewards(self, score, rank, total_players, pot):
		"""Calculates the O-bucks rewards as follows:
		Depending on the percentile range (0-10, 11-25, 26-50, 50-75, 75-100), players will receive rewards.
		The top ten get additional rewards depending on the total amount of O-bucks spent."""
		percentile = (rank / total_players) * 100.0
		for params in self.cutoff_percentiles:
			if percentile > params[0]:
				reward = params[1] + int(score/params[2])
				break
		if rank in self.top_ten.keys():
			reward += pot*self.top_ten[rank]
		return int(reward)

	async def get_username(self, user_id):
		"""Helper function to do the process of getting User object and username in one step."""
		user = await self.client.fetch_user(user_id)
		return user.name

	@commands.command(name="reap")
	@game_active
	async def reap(self, ctx):
		"""Reaps."""
		# Get important info
		game_id = self.get_active_id(ctx.guild.id)
		game_name = self.get_table_name(game_id)
		user_id = ctx.author.id
		now = int(time.time())
		Economy = self.client.get_cog("Economy") # allows us to use Economy methods

		# Creates row in table if it does not exist already
		cur.execute(f"INSERT OR IGNORE INTO {game_name}(user_id) values ({user_id})")
		con.commit()

		# Checks that the user has enough money
		reap_cost = self.get_from_user(game_id, user_id, "reap_cost")
		if Economy.get_balance(user_id) < reap_cost:
			if Economy.available_daily(user_id):
				await ctx.send("You don't have enough O-bucks to reap! However, you can collect some with `$daily`.")
			else:
				await ctx.send("You don't have enough O-bucks to reap!")
			return 

		# Calculates score
		delta_time = self.get_time_since_reap(game_id, now)
		score, mult_string = await self.calculate_score(user_id, delta_time)

		# Other calculations
		growth_rate = self.get_from_meta(game_id, "growth_rate")
		new_reap_cost = math.ceil(reap_cost*(1+growth_rate/100))

		# Updates tables
		self.set_to_meta(game_id, now)
		self.add_to_meta(game_id, reap_cost)
		self.set_to_user(game_id, user_id, now, "last_reap")
		self.add_to_user(game_id, user_id, score)
		self.set_to_user(game_id, user_id, new_reap_cost, "reap_cost")
		Economy.add_balance(user_id, -reap_cost)

		# Output message
		await ctx.send(f"You successfully reaped after {delta_time} seconds, granting you {score} points! {mult_string}")

		# Check for end of game
		target_score = self.get_from_meta(game_id, "target_score")
		if self.get_from_user(game_id, user_id) >= target_score:
			output = await self.end_game(game_id, True)
			await ctx.send(output)
			return

		

		

	@commands.command(name="reap_score", aliases=["score"])
	@game_active
	async def reap_score(self, ctx):
		"""Gets the score of the user in the current game."""
		game_id = self.get_active_id(ctx.guild.id)
		user_id = ctx.author.id 
		score = self.get_from_user(game_id, user_id)
		if score is None:
			score = 0
		await ctx.send(f"You currently have {score} points.")

	@commands.command(name="timer", aliases=["reap_timer"])
	@game_active
	async def timer(self, ctx):
		"""Gets the amount of time, in seconds, since the last reap."""
		game_id = self.get_active_id(ctx.guild.id)
		now = int(time.time())
		delta_time = self.get_time_since_reap(game_id, now)
		await ctx.send(f"The current reap timer is {delta_time} seconds.")

	@commands.command(name="next_reap", aliases=["reap_cost"])
	@game_active
	async def next_reap(self, ctx):
		"""Gets the cost for your next reap."""
		game_id, user_id = self.get_active_id(ctx.guild.id), ctx.author.id
		reap_cost = self.get_from_user(game_id, user_id, "reap_cost")
		await ctx.send(f"Your next reap will cost {reap_cost} O-bucks.")

	@commands.command(name="pot", aliases=["rewards"])
	@game_active
	async def pot(self, ctx):
		"""Shows how much money is in the pot."""
		game_id = self.get_active_id(ctx.guild.id)
		pot = self.get_from_meta(game_id, "reward_pot")
		await ctx.send(f"The current pot is {pot} O-bucks!")

	@commands.command(name="reaperboard", aliases=["rb"])
	async def reaperboard(self, ctx, game_id = None):
		"""Returns the current game leaderboard. If there is no game, it returns the most recent."""
		if game_id is None:
			game_id = self.get_active_id(ctx.guild.id)
			if game_id == -1:
				game_id = self.get_next_id()-1
		else:
			try:
				game_id = int(game_id)
			except ValueError:
				await ctx.send("Game ID could not be parsed!")
				return
			if game_id >= self.get_next_id() or game_id < 1:
				await ctx.send("Game ID out of range!")
				return

		rankings = self.get_rankings(game_id)
		rankings_formatted = [(rank+1, await self.get_username(user_id), score) for rank, (user_id, score) in enumerate(rankings)]
		rankings_header = ("Rank", "Username", "Points")
		if game_id == self.get_active_id(ctx.guild.id):
			rankings_formatted = rankings_formatted[:15]
		output = t2a(header=rankings_header, body=rankings_formatted, first_col_heading=True)
		target_score = self.get_from_meta(game_id, "target_score")
		await ctx.send(f"Displaying leaderboard for game {game_id} with target score {target_score}:```\n{output}\n```")


	@commands.command(name="begin_reaper")
	@admin
	async def begin_reaper(self, ctx, target_score = 100000, base_cost = 100, growth_rate = 5.0):
		"""Starts a new game of reaper."""
		server_id = ctx.guild.id 
		if self.get_active_id(server_id) != -1:
			await ctx.send("You cannot start another game when one is happening in this server!")
			return
		if not self.confirmation_state:
			self.set_confirmation("begin_reaper", [target_score, base_cost, growth_rate])
			await ctx.send(f"You are attempting to create a game with the following parameters: \
target_score = {target_score}, base_cost = {base_cost}, growth_rate = {growth_rate}. Use this command again to confirm, or `$cancel` to cancel.")
			return
		if self.confirmation_command != "begin_reaper":
			await ctx.send("You have another command in progress!")
			return
		else:
			self.create_game(server_id, *self.temps)
			new_id = self.get_active_id(server_id)
			self.reset_confirmation()
			await ctx.send(f"Game {new_id} successfully created.")

	@commands.command(name="end_reaper")
	@admin
	async def end_reaper(self, ctx, reward = 1, game_id = None):
		"""Ends the selected game of reaper. If no ID is provided, it ends the one in the server."""
		if reward == 1:
			reward = True
		else:
			reward = False
		if game_id is None:
			game_id = self.get_active_id(ctx.guild.id)
			if game_id == -1:
				ctx.send("There is no game in this server to end!")
				return
		if not self.confirmation_state:
			self.set_confirmation("end_reaper", [game_id])
			await ctx.send(f"You are attempting to end game {game_id}. Use this command again to confirm, or `$cancel` to cancel.")
			return
		if self.confirmation_command != "end_reaper":
			await ctx.send("You have another command in progress!")
			return
		else:
			self.reset_confirmation()
			output = await self.end_game(game_id, reward)
			await ctx.send(output)

	@commands.command(name="reset_timer")
	@admin
	async def reset_timer(self, ctx):
		game_id = self.get_active_id(ctx.guild.id)
		self.set_to_meta(game_id, int(time.time()))
		await ctx.send("Reaper timer reset.")


	@commands.command(name="cancel")
	@admin
	async def cancel(self, ctx):
		"""Cancels certain admin commands."""
		if self.confirmation_state:
			self.reset_confirmation()
			await ctx.send("Action cancelled.")
		else:
			await ctx.send("No active actions to cancel!")









async def setup(client):
	await client.add_cog(Reaper(client))
	print("Reaper loaded within file.")