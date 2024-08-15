import discord
from discord.ext import commands
from helper import strip, admin
import time
import datetime
import math
import random
import asyncio
import sqlite3

import table2ascii
from table2ascii import table2ascii as t2a, PresetStyle

# Connect to the database
con = sqlite3.connect("betting.db")
cur = con.cursor()

#cur.execute(f"CREATE TABLE meta (game_id int primary key, title text, creator_id int default 0, active int default 1, options text,server int default 0, total_pot int default 0)")
#con.commit()
#cur.execute(f"INSERT INTO meta (game_id, title, creator_id, active, server) \
#	VALUES (0, 0, 0, 0, 0)")
#con.commit()

class Gambling(commands.Cog):
	def __init__(self, client):
		self.client = client
		self.roulette_aliases = {"red": ("r", "red"), "black": ("b", "black"), "street": ("street", "str", "row"), 1: ("1st", "first", "112"), 2: ("2nd", "second", "212"), 3: ("3rd", "third", "312")}


	def check_valid_bet(self, creator_id, bet_amount):
		Economy = self.client.get_cog("Economy")
		return bet_amount <= Economy.get_balance(creator_id)

	def roll_roulette(self):
		"Rolls the roulette wheel. Because 0 and 00 are different, this returns a string that can be cast into int."
		raw = random.randint(1, 38)
		print(raw)
		if raw == 37:
			return "0"
		elif raw == 38:
			return "00"
		return str(raw)

	def parse_roulette_input(self, args):
		"""Converts arguments into a list of all the numbers that would result in a win. Assumes len(args)>0."""
		bets = []
		if len(args) == 0:
			return bets
		print(f"Converting {args}...")
		index = 0
		if args[0] in self.roulette_aliases["red"]:
			bets.extend([i for i in range(1, 37, 2)])
			index += 1
		elif args[0] in self.roulette_aliases["black"]:
			bets.extend([i for i in range(2, 38, 2)])
			index += 1
		elif args[0] in self.roulette_aliases["street"]:
			index += 1
			if len(args) > 1:
				try:
					street_num = (int(args[1]) - 1) // 3
				except ValueError:
					street_num = 0
			else:
				street_num = 0
			if street_num > 11 or street_num < 0:
				street_num = 0
			bets.extend([3*street_num + i for i in range(1, 4)])
			index += 1
		else:
			for i in range(1, 4):
				if args[0] in self.roulette_aliases[i]:
					bets.extend(12*(i-1) + j for j in range(1, 13))
					index += 1
					break
		

		while index < len(args):
			try:
				new_bet = int(args[index])
				if new_bet <= 36 and new_bet >= 1 and new_bet not in bets:
					bets.append(new_bet)
			except ValueError:
				pass
			index += 1

		return bets
	

	def get_from_game(self, game_id, row, attribute="bet_amount"):
		"""Returns any attribute from a game in its own table. If it does not exist, returns None."""
		res = cur.execute(f"SELECT {attribute} FROM game_{game_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return

	def set_to_meta(self, game_id, value, attribute="active"):
		"""Sets any attribute in the meta table to the value. Assumes the game has been made."""
		cur.execute(f"UPDATE meta SET {attribute} = {value} WHERE game_id = {game_id}")
		con.commit()

	def get_bets_from_user(self, game_id, user_id, bet_option=0):
		"""Returns any attribute from a user in the game table. If it does not exist, returns None."""
		res = cur.execute(f"SELECT user_id, bet_option, bet_amount FROM game_{game_id} WHERE user_id = {user_id} AND bet_option = {bet_option}")
		return res.fetchall()


	def get_from_meta(self, game_id, attribute="title"):
		"""Returns any attribute from a game in the meta table. If it does not exist, returns None."""
		res = cur.execute(f"SELECT {attribute} FROM meta WHERE game_id = {game_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return

	def get_sorted_games(self):
		"""Returns a tuple of tuples of all games, sorted from highest pot to lowest pot."""
		res = cur.execute(f"SELECT game_id, title, creator_id, active, options, server, total_pot FROM meta ORDER BY total_pot DESC")
		return res.fetchall()

	def get_next_id(self):
		"""Returns the next available game ID for betting."""
		res = cur.execute("SELECT MAX(game_id) FROM meta")
		output = res.fetchone()[0]
		if output:
			return output+1
		return 1

	def create_game_table(self, game_id):
		"""Creates a table for the corresponding game. Does NOT commit - used in conjunction with create_game."""
		name = "game_"+str(game_id)
		cur.execute(f"CREATE TABLE {name} (user_id int default 0, bet_option int default 0, bet_amount int default 0)")
		# con.commit()

	def create_game(self, server_id, game_title, options, creator_id):
		"""Enters a meta entry for the game, activates it, and creates a table for it."""
		game_id = self.get_next_id()
		game_title = ''.join(e for e in game_title if (e.isalnum() or e in [' ', ',', '?']))
		options = ''.join(e for e in options if (e.isalnum() or e in [' ', ',', '?']))
		self.create_game_table(game_id)
		now = int(time.time())
		cur.execute(f"INSERT INTO meta (game_id, title, creator_id, active, options, server) \
			VALUES ({game_id}, '{game_title}', {creator_id}, 1, '{options}',{server_id})")
		con.commit()
	
	def get_game(self, game_id):
		"""Returns a tuple of tuples of all user bets."""
		res = cur.execute(f"SELECT user_id, bet_option, bet_amount FROM game_{game_id} ORDER BY bet_amount DESC")
		return res.fetchall()

	def truncateStr(self, data, chars):
		return (data[:chars-3] + '...') if len(data) > chars else data

	async def get_username(self, user_id):
		"""Helper function to do the process of getting User object and username in one step."""
		user = await self.client.fetch_user(user_id)
		return user.name


	@commands.command(name="bet")
	async def bet(self, ctx, game_id = None, option_id = None, bet_amount = 0):
		"""Places a bet on a topic. Format: `$bet [game_id] [option_id] [bet_amount]` \
You can get the option_id and game_id by using commands $listbets and $listbetoptions"""
		if game_id is None:
			await ctx.send(f"Format: `$bet [game_id] [option_id] [bet_amount]`")
			return
		try:
			game_id = int(game_id)
			if game_id <= 0 or game_id >= self.get_next_id():
				await ctx.send("Game ID could not be parsed!")
				return
		except ValueError:
			await ctx.send("Game ID could not be parsed!")
			return
		try:
			if int(bet_amount) <= 0:
				await ctx.send("Bet amount must be positive integer!")
				return
		except ValueError:
			await ctx.send("Bet amount must be positive integer!")
			return


		# Get important info
		user_id = ctx.author.id
		now = int(time.time())
		Economy = self.client.get_cog("Economy") # allows us to use Economy methods
		topic_title = self.get_from_meta(game_id, "title")
		total_pot = self.get_from_meta(game_id, "total_pot")
		options = self.get_from_meta(game_id, "options").split(",")
		optionsLen = len(options)

		isActive = self.get_from_meta(game_id, "active") == 1
		if isActive == False:
			await ctx.send("You can only affect active betting topics!")
			return

		# Make sure there is enough options for option_id
		try:
			if int(option_id) >= optionsLen:
				await ctx.send("Option ID must be a positive integer less than {optionsLen}!")
				return
		except ValueError:
			await ctx.send("Option ID must be a positive integer less than {optionsLen}!")
			return

		option_title = options[int(option_id)]

		# Checks that the user has enough money
		if Economy.get_balance(user_id) < int(bet_amount):
			if Economy.available_daily(user_id):
				await ctx.send("You don't have enough O-bucks to bet this amount! However, you can collect some with `$daily`.")
			else:
				await ctx.send("You don't have enough O-bucks to bet this amount!")
			return 

		# Creates row in table 
		cur.execute(f"INSERT INTO game_{game_id} (user_id, bet_option, bet_amount) values ({user_id}, {option_id}, {bet_amount})")
		self.set_to_meta(game_id, total_pot+bet_amount, "total_pot")
		con.commit()
		
		await ctx.send(f"You successfully bet {bet_amount} O-bucks on option {option_id}:\"{option_title}\" for the topic \"{topic_title}\"")

		Economy.add_balance(user_id, -int(bet_amount))

	@commands.command(name="listbetoptions", aliases=["lbo"])
	async def listbetoptions(self, ctx, game_id = None):
		"""Returns a list of all options for a bet"""
		if game_id is None:
			await ctx.send(f"You must specify a game id to list the options for!")
			return
		try:
			game_id = int(game_id)
			if game_id <= 0 or game_id >= self.get_next_id():
				await ctx.send("Game ID could not be parsed!")
				return
		except ValueError:
			await ctx.send("Game ID could not be parsed!")
			return

		list_formatted = []
		title = self.get_from_meta(game_id, "title")
		options = self.get_from_meta(game_id, "options").split(",")
		completedText = "***completed***" if self.get_from_meta(game_id, "active") == 0 else "ongoing"
		game_bets = self.get_game(game_id)
		for j,x in enumerate(options):
			option_pot = 0
			for k,b in enumerate(game_bets):
				if b[1] == j:
					option_pot += b[2]
			list_formatted.append((j, x, option_pot))
		list_header = ("Option ID", "Option", "Pot")
		output = t2a(header=list_header, body=list_formatted, first_col_heading=True)
		await ctx.send(f"Listing options for {completedText} betting topic \n**`\"{title}\"`**:```\n{output}\n```")


	@commands.command(name="listbets", aliases=["lb"])
	async def listbets(self, ctx):
		"""Returns a list of all active bets."""
		list_formatted = []
		sorted_meta = self.get_sorted_games()
		for game in sorted_meta:
			isActive = game[3]
			if isActive != 1:
				continue
			game_id = game[0]
			title = game[1]
			creator_id = game[2]
			options = game[4]
			#game_bets = self.get_game(i)
			game_pot = game[6]
			#for j,x in enumerate(game_bets):
			#	game_pot += x[2]
			list_formatted.append((game_id, self.truncateStr(title, 25), await self.get_username(creator_id), self.truncateStr(options, 25), game_pot))
		list_header = ("ID", "Title", "Creator", "Options", "Pot")
		output = t2a(header=list_header, body=list_formatted, first_col_heading=True)
		await ctx.send(f"Listing all active betting topics:```\n{output}\n```")


	@commands.command(name="endbet")
	async def endbet(self, ctx, game_id = None, option_id = None):
		"""End a bet. Format: `$endbet [game_id] [winning_option]`. This will set the winning option, and distribute \
O-bucks to the winners"""
		if game_id is None:
			await ctx.send(f"Format: `$endbet [game_id] [winning_option]`")
			return
		try:
			game_id = int(game_id)
			if game_id <= 0 or game_id >= self.get_next_id():
				await ctx.send("Game ID could not be parsed!")
				return
		except ValueError:
			await ctx.send("Game ID could not be parsed!")
			return
		
		options = self.get_from_meta(game_id, "options").split(",")
		optionsLen = len(options)

		# Make sure there is enough options for option_id
		try:
			if int(option_id) >= optionsLen:
				await ctx.send("Option ID must be a positive integer less than {optionsLen}!")
				return
		except ValueError:
			await ctx.send("Option ID must be a positive integer less than {optionsLen}!")
			return

		# Make sure the user is the one that created the bet
		user_id = ctx.author.id
		creator_id = self.get_from_meta(game_id, "creator_id")
		title = self.get_from_meta(game_id, "title")
		options = self.get_from_meta(game_id, "options").split(",")
		game_bets = self.get_game(game_id)
		
		isActive = self.get_from_meta(game_id, "active") == 1
		if isActive == False:
			await ctx.send("You can only affect active betting topics!")
			return


		if user_id != creator_id:
			await ctx.send("You must be the creator of the bet to end it!")
			return

		Economy = self.client.get_cog("Economy")
		self.set_to_meta(game_id, 0, "active")

		winners = {}

		# Calculate pot sizes
		winning_pot = 0
		losing_pot = 0
		for k,b in enumerate(game_bets):
			if b[1] == int(option_id):
				winning_pot += b[2]
				if b[1] not in winners:
					winners[b[0]] = 0
			else:
				losing_pot += b[2]

		# Calculate winnings per user
		for user in winners:
			winningBets = self.get_bets_from_user(game_id, user, int(option_id))
			playerTotal = 0
			for w in winningBets:
				playerTotal += w[2]
			# Player will recieve what they initially bet, as well as a portion of the losing pot equal to the percent
			# of what they contributed to the winning pot
			factorOfWinnings = playerTotal/winning_pot
			winners[user] = playerTotal + (factorOfWinnings * losing_pot)
			Economy.add_balance(user, winners[user])
		
		await ctx.send("Ended game with topic: \""+title+"\", winning option: **`\""+options[int(option_id)]+"\"`**")
	
		list_formatted = []
		for key in winners:
			list_formatted.append((await self.get_username(key), winners[key]))
		list_header = ("User", "Winnings")
		output = t2a(header=list_header, body=list_formatted, first_col_heading=True)
		await ctx.send(f"Winnings:```\n{output}\n```")

	

	@commands.command(name="createbet")
	async def createbet(self, ctx, *args):
		"""Create a general bet. Format: `$createbet [bet_title],[bet_options]`. Create a betting topic. \
The title should be followed by a comma (,), and each option should also be comma-separated. This allows \
spaces in names and options. \n\n\
Example usage:  $createbet Will horse A win?,Yes it will,No it won't \
\n\
This will create the following: \n\
\n\
Listing options for bet "Will horse A win?":\n\
╔═════════════════════╗\n\
║ ID ║   Option   Pot ║\n\
╟─────────────────────╢\n\
║ 0  ║ Yes it will	0 ║\n\
║ 1  ║ No it wont   0 ║\n\
╚═════════════════════╝\n\
"""
		bet_options = None
		bet_title = None
		argstr = ""
		for a in args:
			argstr += a + " "
		argArray = argstr.split(",")
		print(argArray)
		if len(argArray) > 1:
			bet_title = argArray[0].strip()
			bet_options = argstr[len(bet_title)+1:].strip()
		# Check valid
		if bet_options is None or bet_title is None:
			await ctx.send("You need to specify a title and options!")
			return
		creator_id = ctx.author.id
		#Economy = self.client.get_cog("Economy")
		
		self.create_game(ctx.guild.id, bet_title, bet_options, creator_id)
		await ctx.send("Created new game with topic: '"+bet_title+"' and options: '"+bet_options+"'")
		

	# Roulette
	@commands.command(name="roulette")
	async def roulette(self, ctx, bet_amount="a", *args):
		"""Play roulette. Format: `$roulette [bet_amount] [bet_specifier]`. You can bet on red or black by \
putting it as your first specifier. You can also use 1st, 2nd, or 3rd to bet on the dozens. You can use street \
to bet on a street, and the next number is in the street. If not, you get the first 1-2-3 street. Any other numbers \
will be treated as individual bets."""
		# Check valid
		if args is None:
			await ctx.send("You need to place a bet!")
			return
		try:
			bet_amount = int(bet_amount)
		except ValueError or TypeError:
			await ctx.send("Invalid bet amount!")
			return
		user_id = ctx.author.id
		Economy = self.client.get_cog("Economy")
		if bet_amount <= 0:
			bet_amount = Economy.get_balance(user_id)
			await ctx.send("You must bet a positive value! Going all in instead...")
		if not self.check_valid_bet(user_id, bet_amount):
			await ctx.send("You don't have enough money, and I'm not in the mood for welfare today. Get lost.")
			return
		bet_list = self.parse_roulette_input(args)
		if len(bet_list) == 0:
			await ctx.send("You didn't place any valid bets! Placing all bets on 1 instead.")
			bet_list = [1]

		# Simulates roulette
		multiplier = (36.0 / len(bet_list))-1
		result = self.roll_roulette()
		await ctx.send(f"You betted {bet_amount} O-bucks on {bet_list}, with a multiplier of {int(multiplier*100)/100}. Good luck!")
		await asyncio.sleep(3)

		# Processes output and adds to user balance		
		if result == "0":
			Economy.add_balance(user_id, -bet_amount)
			await ctx.send(f"The wheel spun a 0 and you lost {bet_amount} O-bucks! Better luck next time.")
			return
		elif result == "00":
			cur = Economy.get_balance(user_id)
			lose_amount = min(cur, 2*bet_amount)
			Economy.add_balance(user_id, -lose_amount)
			await ctx.send(f"The wheel spun a 00 and you lost {lose_amount} O-bucks! Womp womp.")
			return
		result = int(result)
		if result in bet_list:
			win_amount = int(multiplier * bet_amount)
			Economy.add_balance(user_id, win_amount)
			await ctx.send(f"The wheel spun a {result} and you won {win_amount} O-bucks! This is your sign to keep gambling.")
			return
		else:
			Economy.add_balance(user_id, -bet_amount)
			await ctx.send(f"The wheel spun a {result} and you lost {bet_amount} O-bucks! Remember, 99% of gamblers quit before they win big.")
			return

	@commands.command(name="cogtest")
	async def cogtest(self, ctx):
		"""Simple tester command to make sure the cog is loaded."""
		await ctx.send("the cog has been loaded")







async def setup(client):
	await client.add_cog(Gambling(client))
	print("Gambling loaded within file.")
