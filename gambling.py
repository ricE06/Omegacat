import discord
from discord.ext import commands
from helper import strip, admin
import time
import datetime
import math
import random
import asyncio




class Gambling(commands.Cog):
	def __init__(self, client):
		self.client = client
		self.roulette_aliases = {"red": ("r", "red"), "black": ("b", "black"), "street": ("street", "str", "row"), 1: ("1st", "first", "112"), 2: ("2nd", "second", "212"), 3: ("3rd", "third", "312")}


	def check_valid_bet(self, user_id, bet_amount):
		Economy = self.client.get_cog("Economy")
		return bet_amount <= Economy.get_balance(user_id)

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