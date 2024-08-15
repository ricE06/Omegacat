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

class Utility(commands.Cog):
	def __init__(self, client):
		self.client = client
		self.time_periods = ("offered_fall", "offered_IAP", "offered_spring", "offered_summer")
		self.format_tags = {"-d": lambda a: f"```Description: {a.get("description", "No description available")}\nInstructor(s): {", ".join(a.get("instructors", ["No instructors available"]))}```", \
							"-l": lambda a: f"Link: <{a.get("url", "No link available")}>\n", \
							"-u": lambda a: f"```{a.get("total_units", "")} total units ({a.get("lecture_units", "")}|{a.get("preparation_units", "")}|{a.get("lab_units", "")}|{a.get("design_units", "")}) (lec|prep|lab|design)```", \
							"-s": lambda a: f"```{"\n".join(" ".join(a.get("schedule", "No schedule available").split(",")).split(";"))}```", \
							"-a": lambda a: f"```Available: {", ".join([key.removeprefix("offered_") for key in self.time_periods if a.get(key, False)])}```", \
							"-p": lambda a: f"```Prerequisites: {a.get("prerequisites", "none")}```"}

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



async def setup(client):
	await client.add_cog(Utility(client))
	print("Utility loaded within file.")


