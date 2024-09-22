import discord
from discord.ext import commands
from helper import strip, admin
import time
import datetime
import math
import random
import asyncio
import sqlite3
from yahoo_fin import stock_info

import table2ascii
from table2ascii import table2ascii as t2a, PresetStyle, Alignment

# Connect to the database
con = sqlite3.connect("stocks.db")
cur = con.cursor()

#cur.execute(f"CREATE TABLE meta (user_id int default 0, equity int default 0)")
#con.commit()

class StockMarket(commands.Cog):
	def __init__(self, client):
		self.client = client

	def check_valid_amount(self, user_id, bet_amount):
		Economy = self.client.get_cog("Economy")
		return (bet_amount <= Economy.get_balance(user_id)) and (bet_amount > 0) and (Economy.get_balance(user_id) > 0)

	def get_from_portfolio(self, user_id, ticker, attribute="shares"):
		"""Returns any attribute from a users portfolio in its own table. If it does not exist, returns None."""
		res = cur.execute(f"SELECT {attribute} FROM u{user_id} WHERE ticker='{ticker}'")
		output = res.fetchone()
		if output:
			return output[0]
		return

	def set_to_portfolio(self, user_id, ticker, value, attribute="shares"):
		"""Sets any attribute in the users portfolio table to the value. Assumes the game has been made."""
		cur.execute(f"UPDATE u{user_id} SET {attribute} = {value} WHERE ticker = '{ticker}'")
		con.commit()

	def set_to_meta(self, user_id, value, attribute="active"):
		"""Sets any attribute in the meta table to the value. Assumes the game has been made."""
		cur.execute(f"UPDATE meta SET {attribute} = {value} WHERE user_id = {user_id}")
		con.commit()

	#def get_bets_from_user(self, user_id, bet_option=0):
	#	"""Returns any attribute from a user in the game table. If it does not exist, returns None."""
	#	res = cur.execute(f"SELECT user_id, bet_option, bet_amount FROM game_{user_id} WHERE user_id = {user_id} AND bet_option = {bet_option}")
	#	return res.fetchall()

	def get_stock_price(self, ticker):
		try:
			return stock_info.get_live_price(ticker)
		except:
			return None

	def get_from_meta(self, user_id, attribute="user_id"):
		"""Returns any attribute from a game in the meta table. If it does not exist, returns None."""
		res = cur.execute(f"SELECT {attribute} FROM meta WHERE user_id = {user_id}")
		output = res.fetchone()
		if output:
			return output[0]
		return

	def get_sorted_games(self):
		"""Returns a tuple of tuples of all games, sorted from highest pot to lowest pot."""
		res = cur.execute(f"SELECT game_id, title, description, user_id, active, options, server, total_pot, status, type FROM meta ORDER BY total_pot DESC")
		return res.fetchall()

	def create_user_table(self, user_id):
		"""Creates a table for the corresponding user. Does NOT commit - used in conjunction with create_game."""
		name = str(user_id)
		cur.execute(f"CREATE TABLE u{name} (ticker text, shares int default 0, average_cost real default 0)")
		# con.commit()

	def create_user(self, user_id):
		"""Enters a meta entry for the user, activates it, and creates a table for it."""
		self.create_user_table(user_id)
		cur.execute(f"INSERT INTO meta (user_id) \
			VALUES ({user_id})")
		con.commit()
	
	def get_stocks(self, user_id):
		"""Returns a tuple of tuples of all user stock positions."""
		res = cur.execute(f"SELECT ticker, shares, average_cost FROM u{user_id} ORDER BY shares DESC")
		return res.fetchall()

	def truncateStr(self, data, chars):
		return (data[:chars-1] + '…') if len(data) > chars else data

	async def get_username(self, user_id):
		"""Helper function to do the process of getting User object and username in one step."""
		user = await self.client.fetch_user(user_id)
		return user.name

	@commands.command(name="sellstock")
	async def selltock(self, ctx, ticker = None, amount=None):
		"""Sells shares of a stock. Format: `$sellstock [ticker] [amount_of_shares]`"""
		user_id = ctx.author.id

		if self.get_from_meta(user_id) == None:
			self.create_user(user_id)

		if ticker is None:
			await ctx.send(f"Format: `$sellstock [ticker] [amount_of_shares]`")
			return
		
		try:
			if int(amount) < 1:
				await ctx.send("Amount must be positive integer!")
				return
			amount = int(amount)
		except (TypeError, ValueError):
			await ctx.send("Amount must be positive integer!")
			return

		# Fetch quote of current price per share
		pricePerShare = 100000000
		try:
			pricePerShare = self.get_stock_price(ticker)
			if pricePerShare == None:
				await ctx.send("Ticker could not be parsed!")
				return
			pricePerShare = int(pricePerShare)
		except ValueError:
			await ctx.send("Ticker could not be parsed!")
			return

		# Get important info
		Economy = self.client.get_cog("Economy") # allows us to use Economy methods
		
		# Checks that the user has enough of this stock
		# do they have any history?
		if self.get_from_portfolio(user_id, ticker) == None:
			await ctx.send(f"You don't have {amount} shares!")
			return
		else: #if yes, edit row
			shares = self.get_from_portfolio(user_id, ticker, "shares")
			average_cost = self.get_from_portfolio(user_id, ticker, "average_cost")
			if shares < amount:
				await ctx.send(f"You don't have {amount} shares!")
				return
			self.set_to_portfolio(user_id, ticker, shares-amount, "shares")
		shares = self.get_from_portfolio(user_id, ticker, "shares")
		con.commit()

		Economy.add_balance(user_id, pricePerShare*amount)
		
		await ctx.send(f"You successfully sold {amount} shares of `{ticker.upper()}`, valued at ${amount*pricePerShare}!\nYou now have {shares} shares of `{ticker.upper()}`, and a total equity of ${shares*pricePerShare}")


	@commands.command(name="buystock")
	async def buystock(self, ctx, ticker = None, amount=None):
		"""Buys shares of a stock. Format: `$buystock [ticker] [amount_of_shares]`"""
		user_id = ctx.author.id

		if self.get_from_meta(user_id) == None:
			self.create_user(user_id)

		if ticker is None:
			await ctx.send(f"Format: `$buystock [ticker] [amount_of_shares]`")
			return
		
		try:
			if int(amount) < 1:
				await ctx.send("Amount must be positive integer!")
				return
			amount = int(amount)
		except (TypeError, ValueError):
			await ctx.send("Amount must be positive integer!")
			return

		# Fetch quote of current price per share
		pricePerShare = 100000000
		try:
			pricePerShare = self.get_stock_price(ticker)
			if pricePerShare == None:
				await ctx.send("Ticker could not be parsed!")
				return
			pricePerShare = int(pricePerShare)
		except ValueError:
			await ctx.send("Ticker could not be parsed!")
			return

		# Get important info
		Economy = self.client.get_cog("Economy") # allows us to use Economy methods
		
		# Checks that the user has enough money
		if self.check_valid_amount(user_id, pricePerShare*amount) == False:
			if Economy.available_daily(user_id):
				await ctx.send(f"You don't have enough O-bucks to buy ${pricePerShare*amount} worth of {ticker}! However, you can collect some with `$daily`.")
			else:
				await ctx.send(f"You don't have enough O-bucks to buy ${pricePerShare*amount} worth of {ticker}!")
			return 
		else:
			Economy.add_balance(user_id, -pricePerShare*amount)



		# Creates row in table if it doesnt exit
		if self.get_from_portfolio(user_id, ticker) == None:
			cur.execute(f"INSERT INTO u{user_id} (ticker, shares, average_cost) values ('{ticker}', {amount}, {pricePerShare})")
		else: #otherwise, just edit row
			shares = self.get_from_portfolio(user_id, ticker, "shares")
			average_cost = self.get_from_portfolio(user_id, ticker, "average_cost")
			self.set_to_portfolio(user_id, ticker, shares+amount, "shares")
			self.set_to_portfolio(user_id, ticker, (average_cost*shares+pricePerShare*amount)/(shares+amount), "average_cost")
		shares = self.get_from_portfolio(user_id, ticker, "shares")
		#self.set_to_meta(game_id, total_pot+bet_amount, "equity")
		con.commit()
		
		await ctx.send(f"You successfully bought {amount} shares of `{ticker.upper()}`, valued at ${amount*pricePerShare}!\nYou now have {shares} shares of `{ticker.upper()}`, and a total equity of ${shares*pricePerShare}")


	@commands.command(name="mypositions", aliases=["myportfolio"])
	async def mypositions(self, ctx):
		"""Returns a list of all stock positions you have and their prices"""

		user_id = ctx.author.id
		userName = await self.get_username(user_id)
		stockPositions = self.get_stocks(user_id)
		list_formatted = []
		totalPL = 0;
		for stock in stockPositions:
			ticker = stock[0]
			shares = stock[1]
			average_cost = stock[2]

			pricePerShare = int(self.get_stock_price(ticker))

			if shares > 0:
				list_formatted.append((ticker.upper(),shares,"$" + str(pricePerShare),"$" + str(int(average_cost)),"$" + str(int(pricePerShare*shares)),"$" + str(int(average_cost*shares-pricePerShare*shares))))
				totalPL += int(average_cost*shares-pricePerShare*shares)
		
		list_header = ("Ticker", "Shares", "Price", "Avg Cost", "Equity", "P/L")

		outputStr = t2a(header=list_header, body=list_formatted, first_col_heading=False, alignments=Alignment.RIGHT)
		await ctx.send(f"Listing all positions for user: <@{user_id}>:\n```\n{outputStr}\n\nTotal P/L: ${totalPL}\n```")






async def setup(client):
	await client.add_cog(StockMarket(client))
	print("StockMarket loaded within file.")
