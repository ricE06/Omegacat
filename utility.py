import discord
from discord.ext import commands
from helper import strip, admin
import time
import datetime
import math
import random
import asyncio
import requests
from table2ascii import table2ascii as t2a, PresetStyle
from table2ascii import Alignment
import sqlite3
import json


# Connect to the database
con = sqlite3.connect("courses.db")
cur = con.cursor()
# CREATE TABLE courseloads (id INTEGER PRIMARY KEY, name TEXT DEFAULT "");
# New columns are added for each valid course. There is a command to wipe the database for the new semester.




class Utility(commands.Cog):
	def __init__(self, client):
		self.client = client
		self.time_periods = ("offered_fall", "offered_IAP", "offered_spring", "offered_summer")
		self.format_tags = {"-d": lambda a: f'```Description: {a.get("description", "No description available")}\nInstructor(s): {", ".join(a.get("instructors", ["No instructors available"]))}```', \
							"-l": lambda a: f'Link: <{a.get("url", "No link available")}>\n', \
							"-u": lambda a: f'```{a.get("total_units", "")} total units ({a.get("lecture_units", "")}|{a.get("preparation_units", "")}|{a.get("lab_units", "")}|{a.get("design_units", "")}) (lec|prep|lab|design)```', \
							"-s": lambda a: '```' + "\n".join(" ".join(a.get("schedule", "No schedule available").split(",")).split(";")) + '```', \
							"-a": lambda a: f'```Available: {", ".join([key.removeprefix("offered_") for key in self.time_periods if a.get(key, False)])}```', \
							"-p": lambda a: f'```Prerequisites: {a.get("prerequisites", "none")}```'}
		# self.format_tags = {}

	def check_blacklist(self, user_id):
		with open('blacklist.txt', 'r') as f:
			for line in f:
				if str(user_id) in line:
					f.close()
					return True
			f.close()
		return False


	def lookup_course(self, search):
		"""Gets the full JSON of a course from Fireroad. 
		Returns an empty dictionary if none exists (404 error), and returns the status code if there is a different error."""
		url = f"https://fireroad.mit.edu/courses/lookup/{search}?full=true"
		response = requests.get(url)
		if response.status_code == 200:
			return response.json()
		elif response.status_code == 404:
			return {}
		return response.status_code

	def search_course(self, search):
		"""Gets a list of subject IDs and course titles associated with a search query.
		Returns an empty list if none exists (404 error), and returns the status code if there is a different error."""
		url = f"https://fireroad.mit.edu/courses/search/{search}?full=true"
		response = requests.get(url)
		if response.status_code == 404:
			return []
		elif response.status_code != 200:
			return response.status_code
		full_data = response.json()
		return [(course["subject_id"], course["title"]) for course in full_data]

	def format_course_data(self, course_data, tags=None):
		"""Returns an embed using the course_data (one dictionary) according to the tags."""
		subject_id = course_data["subject_id"]
		title = course_data["title"]
		if tags:
			output = f"Showing information for **{subject_id} ({title})**:\n"
		else:
			output = f"{subject_id}: {title}"
		for tag in tags:
			output = output + self.format_tags.get(tag, lambda a: "")(course_data)
		return output

	def format_search_results(self, search, search_results):
		"""Returns an embed with formatted search results. 
		Assumes search_results is a list of tuples (subject_id, title) with at least one entry."""
		length = len(search_results)
		courses_header = ("ID", "Title")
		table = t2a(header=courses_header, body=search_results[:10], alignments=Alignment.LEFT)
		output = f"Returning {length} results for `{search}`: \n```{table}"
		if length > 10:
			output = output + "\n" + "Warning: your search was too general and only the first ten results are shown."
		output = output + "```"
		return output

	def add_class_to_table(self, class_num):
		"""Adds a new column for the course number in courseloads table. Columns are the exact number of the class, decimal included."""
		cur.execute(f"ALTER TABLE courseloads ADD '{class_num}' TEXT DEFAULT 'x'")
		con.commit()

	def get_column_names(self):
		"""Returns the column names in the courseloads table. Used to check if courses already exist in the table."""
		res = cur.execute("SELECT name FROM PRAGMA_TABLE_INFO('courseloads')")
		output = [i[0] for i in res.fetchall()]
		print(output)
		return output

	def edit_entry(self, user_id, class_num, entry):
		"""Sets the entry for the associated user_id and class_num to entry. Internal use only, assumes all rows and columns exist."""
		cur.execute(f"UPDATE courseloads SET '{class_num}' = '{entry}' WHERE id = {user_id}")
		con.commit()

	def modify_courseload(self, user_id, class_tags, name = None):
		"""Changes the classes associated with a user id, and creates a new row if one does not exist already. 
		Class tags are a nested tuple, where the first entry is the class is the course id and the second entry is the data entry.
		The class number should be used to indicate someone is taking the class, and 'x' if not. Extra text can be used to provide more information (e.g. first or second quarter)."""
		if name is None:
			name = "unknown"
		cur.execute(f"INSERT OR IGNORE INTO courseloads(id, name) VALUES ({user_id}, '{name}')")
		con.commit()
		existing_classes = self.get_column_names()
		for class_num, entry in class_tags:
			if class_num not in existing_classes:
				self.add_class_to_table(class_num)
			self.edit_entry(user_id, class_num, entry)

	def get_classes_taken(self, user_id):
		"""Returns a list of the internal name followed by all the classes that the user is taking (i.e. nondefault entries)."""
		res = cur.execute(f"SELECT * FROM courseloads WHERE id = {user_id}")
		raw = res.fetchone()
		if raw is None:
			return ["Not a valid ID!"]
		output = [raw[1]]
		for entry in raw[2:]:
			if entry != "x":
				output.append(entry)
		return output

	def get_taking_class(self, class_num):
		"""Returns a list of tuples (user_id, name) taking a certain class (i.e. nondefault entries). Returns the empty list if no class exists."""
		if class_num not in self.get_column_names():
			return []
		res = cur.execute(f"SELECT id, name, `{class_num}` FROM courseloads")
		raw = res.fetchall()
		print(raw)
		output = []
		for entry in raw:
			print(entry)
			if len(str(entry[2])) > 1:
				output.append(entry[1:])
		return output

	def sanitize_name(self, path):
		path = path[0:30]
		length = len(path)
		SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890.|/ "
		safepath = ""
		for i in range(length):
			if path[i] in SAFE:
				safepath = safepath + path[i]
		return safepath

	def process_tags(self, tags):
		"""Returns a list of class_tags suitable for modify_courseload(). Input should be a list of strings. Only considers ones beginning with + or -."""
		output = []
		mapping = {"+": lambda a: a, "-": lambda a: "x"}
		all_add = True
		for tag in tags:
			if tag[0] == "+" or tag[0] == "-":
				all_add = False
				break
		for tag in tags:
			if tag[0] == "+" or tag[0] == "-" or all_add:
				if all_add:
					operator = "+"
				else:
					operator = tag[0]
					tag = tag[1:]
				search_result = self.lookup_course(tag)
				if type(search_result) is not int and len(search_result) > 0:
					class_num = search_result.get("subject_id")
					output.append((class_num, mapping[operator](class_num)))
		return output

	@commands.command(name="lookup", aliases=["search", "find", "course"])
	async def lookup(self, ctx, search, *args):
		"""Looks up an MIT course by its ID. If one is not found, it will search for possible courses instead.
		TAGS (input separated by spaces after search term, multiple okay): 
		-a: Returns which terms the course is available.
		-d: Returns the description and instructor(s).
		-l: Returns a link to the course catalog for the course.
		-s: Returns the schedule of the course, with some minimal formatting.
		-u: Returns the number of units the course is worth, with subdivision."""
		# First attempts to find the exact course
		direct_lookup = self.lookup_course(search)
		if type(direct_lookup) is int:
			await ctx.send(f"Error: {direct_lookup}")
			return
		if args is None:
			args = []
		if len(direct_lookup) > 0:
			await ctx.send(self.format_course_data(direct_lookup, args))
			return
		# Attempts to search for courses
		search_words = [search]
		search_words.extend([word for word in args if word[0] != "-"])
		search = " ".join(search_words)
		search_lookup = self.search_course(search)
		if type(search_lookup) is int:
			await ctx.send(f"Error: {direct_lookup}")
			return
		if len(search_lookup) == 0:
			await ctx.send(f"No searches found for `{search}`.")
			return
		if len(search_lookup) == 1:
			await ctx.send(self.format_course_data(self.lookup_course(search_lookup[0][0]), args))
			return
		await ctx.send(self.format_search_results(search, search_lookup))

	@commands.command(name="add_courseload", aliases=["add_courses", "addc"])
	async def add_courseload(self, ctx, *args):
		"""Command to add courses to the lookup table. Begin each class with either '+' or '-' to add or remove a class, followed by the class number.
		Separate classes by spaces."""
		if self.check_blacklist(ctx.author.id):
			return
		if args is None:
			await ctx.send("You must input at least one class!")
			return
		tags = self.process_tags(args)
		self.modify_courseload(ctx.author.id, tags, self.sanitize_name(ctx.author.display_name))
		await ctx.send(f"{len(tags)} classes successfully updated.")

	@commands.command(name="see_courseload", aliases=["see_courses", "seec"])
	async def see_courseload(self, ctx, search = None):
		"""View who is taking your class, or which classes one is taking. Without parameters, returns the classes you are taking. If you input a user id or ping 
		another user, it returns the class they are taking. If you input a course number, it returns everyone who has indicated they are taking the class.""" 
		if self.check_blacklist(ctx.author.id):
			return
		if search is None:
			search = ctx.author.id 
		if strip(str(search)) != -1:
			user_id = strip(str(search))
			await ctx.send(" ".join(self.get_classes_taken(user_id)))
			return
		taking = self.get_taking_class(search)
		if len(taking) == 0:
			await ctx.send("No one is taking that class!")
		else:
			await ctx.send(", ".join([name for name, entry in taking]))

	@commands.command(name="editname", aliases=["setname"])
	async def edit_name(self, ctx, new_name):
		"""Changes the name in the database and creates a new row if one does not exist."""
		self.modify_courseload(ctx.author.id, ())
		cur.execute(f"UPDATE courseloads SET name = '{new_name}' WHERE id={ctx.author.id}")
		con.commit()
		await ctx.send("Name successfully added.")

	@commands.command(name="blacklist")
	@admin
	async def blacklist(self, ctx, target):
		"""Adds a user to the blacklist."""
		with open('blacklist.txt', 'a') as f:
			f.write(str(strip(target)) + "\n")
			f.close()
		cur.execute(f"DELETE FROM courseloadsk WHERE id = {strip(target)}")
		con.commit()
		await ctx.send("User added to blacklist and entries deleted.")

	@commands.command(name="compilepolldata")
	@admin
	async def compilepolldata(self, ctx):
		"""Creates a .JSON file listing all messages in #polls, with an array of all reactions and user reactors"""
		await ctx.send("Gathering all messages in polls channel, this may take a while...")
		pollsDict = {'messages':[]}
		pollschannel=self.client.get_channel(1283421562514706476)
		async for message in pollschannel.history():
			content = message.content
			if "\"" in content[0] or "“" in content[0] and "(open)" not in content: # make sure it is probably a poll message
				if len(message.reactions) > 1:
					reactions = {}
					for reaction in message.reactions:
						reactions[str(reaction.emoji)] = []
						users = [user async for user in reaction.users()]
						for user in users:
							reactions[str(reaction.emoji)].append(user.name)
					msg = {'messageid':message.id,'reactions':reactions}
					pollsDict['messages'].append(msg)

		with open('temp.json', 'w') as f:
			json.dump(pollsDict, f)
		await ctx.send("Finished scraping polls channel, here is the resulting file:")
		await ctx.send(file=discord.File("temp.json"))


async def setup(client):
	await client.add_cog(Utility(client))
	print("Utility loaded within file.")


