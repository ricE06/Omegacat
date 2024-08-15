import discord
from discord.ext import commands
from helper import strip, admin
import time
import datetime
import math
import random
import asyncio
import sqlite3


# Connect to the database
con = sqlite3.connect("upgrades.db")
cur = con.cursor()
# upgrades.db has one global meta table, one meta table for upgrades and one table to track which upgrades each user has
# table - meta
#    col1 - name (text) - name of tracked value
#    col2 - value (int) - value
# table - upgrades_meta
#    col1 - upgrade_id (int) KEY
#    col2 - name (text) - name of the upgrade (GOES WITH inventory TABLE)
#    col3 - consumable (int) - either 0 or 1, indicates whether to subtract the count by 1 after use
#    col4 - cost (int) - amount of O-bucks it costs in the shop - default 0 - if 0, a custom formula can be implemented
#    col5 - prereqs (text) - upgrade IDs of the other upgrades that must exist, entered as a string of numbers seperated by spaces, default ""
# table - inventory
#    col1 - user_id (int) KEY
#    colN - {upgrade_name} - indicates whether the user has the upgrade and how many if consumable, MUST MATCH col2 and be added in tandem

class Upgrades(commands.Cog):
	def __init__(self, client):
		self.client = client

	def get_meta_value(self, val="base_daily"):
		"""Gets a value from the meta table."""
		res = cur.execute(f'SELECT value FROM meta WHERE name="{val}"')
		output = res.fetchone()
		if output:
			return output[0]
		return 0

	def set_meta_value(self, new_val, col="base_daily"):
		"""Sets a value to the meta table."""
		cur.execute(f'UPDATE meta SET value = {new_val} WHERE name="{col}"')
		con.commit()

	def add_meta_value(self, change, col="base_daily"):
		current = self.get_meta_value(col)
		self.set_meta_value(current+change, col)

	def roll_raising_daily(self, amount):
		"""Attempts to upgrade the base daily value by 1 O-buck. Returns True if successful, False if not."""
		old_storage = self.get_meta_value("give_sacrificed")
		new_storage = old_storage+amount
		self.set_meta_value(new_storage, "give_sacrificed")
		level = self.get_meta_value() - 1000
		d = 0.45 # Parameter (see desmos)
		g = 600 + 40*(level**1.2)
		j = 50+3*level
		if amount > j/2 and random.uniform(0, 1) > 0.5:
			self.add_meta_value(1, "num_sacrifices")
		univ_probability = max(d + (2-2*d)*math.atan(4*((new_storage/g)-1))/math.pi, 0) 
		self_probability = max(0.95*(1-math.e**(-(4*amount-j)/j))+(amount**0.5)/j, 0)
		sacrifices_probability = min(1, (self.get_meta_value("num_sacrifices")-3)/level)
		total_probability = univ_probability*self_probability*sacrifices_probability
		roll = random.uniform(0, 1)
		print(f"Attempted to roll with universal {univ_probability}, self {self_probability}, and total {total_probability}. Roll was {roll}.")
		if roll < total_probability:
			self.set_meta_value(0, "give_sacrificed")
			self.set_meta_value(0, "num_sacrifices")
			self.set_meta_value(1001+level, "base_daily")
			return True
		return False


async def setup(client):
	await client.add_cog(Upgrades(client))
	print("Upgrades loaded within file.")
