import discord
from discord.ext import commands
import os 
import datetime
from datetime import datetime
import random
import time
import asyncio
import inflect
import math
import sqlite3

p = inflect.engine()




# COUNT_CHANNEL = 1061769683428192296
COUNT_CHANNEL = 1223498821527670825


skip = 0
best = 0
last_id = 0

active_rules = []

rule_count = 1

double_counting = True

intents = discord.Intents.default()
intents.message_content = True

# the token is private and stored locally
token_file = open("token.txt", "r")
token = token_file.read()
token_file.close()

lives = 3

print("a")

cogs = ("economy", "reaper", "gambling", "stockmarket", "utility", "upgrades")
#cogs = ("utility", "upgrades")
async def setup(client):
    for cog in cogs:
        await client.load_extension(cog)
        print(f"Cog {cog} loaded.")




client = commands.Bot(intents=intents, command_prefix = "$")

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await setup(client)
    print("Cogs have been loaded")
    # counting
   

@client.command(name="alive")
async def alive(ctx: commands.Context):
    await ctx.send('I am always alive. I am omnipotent. I am watching you. I shall never die.')




async def show_active(channel):
    output_str = "Showing active rules..."
    for rule in active_rules:
        output_str += "\n" + rule.to_string()
    if len(active_rules) == 0:
        output_str = "There are no extra rules to follow!"
    await channel.send(output_str)



# this part of the code is a mess we uh don't talk about this :)
@client.event
async def on_message(message):
    if message.channel.id != COUNT_CHANNEL or message.author.id == 1180364917417721957 or message.content[0] == ".":
        if sanitize(message.content) == "active":
           await show_active(message.channel)
        await client.process_commands(message)
        return
    contents = sanitize(message.content)

    f = open("count.txt", "r")
    current = int(f.readline())
    f.close()

    print(f"{datetime.now()}: user {str(message.author.global_name)} counted {contents} ({str(current)})")

    global last_id
    if message.author.id == last_id and double_counting:
        await lose(message.channel, current, [(0, "No double counting!")], message)
        return
    last_id = message.author.id

    passed = True
    override = False
    passed_overrides = True
    satisfied = [(1, True)]
    for rule in active_rules:
        checked = rule.check_pass(contents, current, message)
        if not checked:
            passed = False
            if rule.override:
                passed_overrides = False
        satisfied.append((rule, checked))

        if not override and rule.override:
            override = rule.override

    print(str(override))

    # win: override is activated and all overriding rules are passed
    if override and passed_overrides:
        override = False
        await next_count(message.channel, current, message)
        return

    # lose: overall not passed
    if not passed:
        await lose(message.channel, current, satisfied, message)
        return

    try:
        contents = eval(contents)
        number = int(contents)
    except:
        await lose(message.channel, current, [(0, "Formatting could not be parsed!")], message)
        return

    if abs(number - contents) >= 0.00001:
        await lose(message.channel, current, [(0, "Not a whole number!")], message)
        return


    if number == current:
        await next_count(message.channel, current, message)
        return
    else:
        await lose(message.channel, current, [(0, "Incorrect number!")], message)
        return
    
    




current = 0



async def lose(channel, cur, satisfied, message):

    global lives
    lives -= 1
    lose_string = f"You lost a life! **{lives}** live(s) remaining..."
    if satisfied[0][0] == 0:
        lose_string += "\n" + "Reason for loss: " + satisfied[0][1]
    else:
        for i in satisfied:
            if not i[1]:
                lose_string += "\n" + i[0].lose_message()

    await channel.send(lose_string)
    
    if lives <= 0:

        await true_lose(channel, cur, satisfied)
    else:
        await next_count(channel, cur, message)


async def true_lose(channel, cur, satisfied):
    f = open("count.txt", "w")
    f.write("1")
    f.close()
    lose_string = "You lost at " + str(cur) + "! Resetting count to 1..."

    # default loss
    

    new_best = False
    global best 
    if cur > best:
        best = cur
        new_best = True
        lose_string += "\n" + "New best!"
    else:
        lose_string += "\n" + "Your best is **" + str(best) + "**."


    for meta_rule in rule_list:
        meta_rule.track = []

    await channel.send(lose_string)
    global current
    current = 1
    global active_rules 
    active_rules = []
    global rule_count
    rule_count = 1
    global last_id 
    last_id = 0
    Fizzbuzz.skip = 0
    global lives
    lives = 3





async def next_count(channel, current, message):
    f = open("count.txt", "w")
    f.write(str(current+1))
    f.close()
    

    output_str = ""


    global rule_list
    for meta_rule in rule_list:
        for rule in meta_rule.meta_tick(current, message):
            active_rules.remove(rule)
            output_str += "Rule " + str(rule.key) + " cleared!" + "\n"


    
    for meta_rule in rule_list:
        new_rule = meta_rule.try_activate(current)
        if new_rule is not None:
            output_str += new_rule.to_string() + "\n"
            active_rules.append(new_rule)

    if len(output_str) > 0:
        await channel.send(output_str)



    







# Parent class for all rules
class Rule():

    # Universal variables
    unlock = 10000
    freq = 10000
    scale = 10000
    low = 0
    high = 0
    track = []
    

    def __init__(self, key, lifetime, *args):
        self.lifetime = lifetime
        #self.string = self.gen_string()
        self.key = key
        self.override = False
        

    def check_pass(self, contents, cur, msg):
        """Checks if the user input passes the rule."""
        if self.lifetime == 0:
            return True
        return self.check_valid(contents, cur, msg)

    def check_valid(self, contents, cur, msg):
        """Checks if the user input conforms to the rule. Should be overridden."""
        return True

    def gen_string(self):
        """Generates string upon initiation."""
        return "this is a rule."


    def tick(self):
        """Activated each time a number is successfully sent."""
        if self.lifetime > 0:
            self.lifetime -= 1
        if self.lifetime == 0:
            type(self).track.remove(self)
        return self.lifetime == 0

    @classmethod
    def meta_tick(c, cur, msg):
        ended = []
        for rule in c.track:
            if rule.tick():
                ended.append(rule)
        c.meta_tick_extras(cur, msg)
        return ended

    @classmethod
    def can_activate(c, cur):
        print("reached " + str(len(c.track)))
        return cur >= c.unlock and len(c.track) == 0


    @classmethod
    def try_activate(c, cur):
        """Attempts to activate the rule."""
        if not c.can_activate(cur):
            return 
        if random.randint(0, c.freq) == 0:
            lifetime = random.randrange(int(cur/c.scale + c.low), int(cur/c.scale + c.high))
            global rule_count
            new_rule = c(rule_count, lifetime)
            new_rule.set_params()
            c.track.append(new_rule)
            rule_count += 1
            return new_rule
        return 

    def set_params(self):
        """Initializes other parts of the rule (not just lifetime). May be overridden."""
        return

    @classmethod
    def meta_tick_extras(c, cur, msg):
        """Other things to do during a meta tick. May be overridden."""
        return

    def to_string(self):
        """Converts the rule to a string for export. Should be overridden."""
        return "Rule " + str(self.key) + ": " + "for the next **" + str(self.lifetime) + "** numbers, " + self.gen_string()

    def lose_message(self):
        """Printed if the count fails to this rule."""
        return "You failed rule " + str(self.key) + ": " + self.gen_string() 

class Prime(Rule):
    unlock = 10
    freq = 20
    scale = 12
    low = 1
    high = 8
    track = []
    
    def __init__(self, key, lifetime):
        """All prime numbers must be replaced with the word 'prime'"""
        super().__init__(key, lifetime)

    def check_valid(self, contents, cur, msg):
        if Prime.prime_check(cur):
            self.override = True
            return contents == "prime"
        else:
            self.override = False
            return True

    @staticmethod
    def prime_check(cur):
        """Rule 1: All prime numbers must be replaced with the word 'prime'"""
        if cur <= 1:
            return False
        for i in range(2, cur):
            if cur % i == 0:
                return False # not a prime, automatic skip
        return True



    def gen_string(self):
        return "all prime numbers must be replaced with the word `prime`."

class No_n_in_expression(Rule):
    unlock = 25
    freq = 18
    scale = 7
    low = 7
    high = 15
    track = []
    
    def __init__(self, key, lifetime):
        """Expressions may not contain a certain number"""
        self.avoid = random.randint(1, 9) 
        super().__init__(key, lifetime)

    def check_valid(self, contents, cur, msg):
        return str(self.avoid) not in contents

    @classmethod
    def can_activate(c, cur):
        return cur >= c.unlock and len(c.track) <= 2

    def gen_string(self):
        return "expressions may not contain the number **" + str(self.avoid) + "**."

class No_reused_digits(Rule):
    unlock = 40
    freq = 15
    scale = 25
    low = 2
    high = 7
    track = []
    avoid = []

    def __init__(self, key, lifetime):
        """Expressions may not use digits in the previous expression"""
        super().__init__(key, lifetime)

    def check_valid(self, contents, cur, msg):
        for excluded in self.__class__.avoid:
            if excluded in contents:
                return False
        return True

    @classmethod
    def meta_tick_extras(c, cur, msg):
        to_avoid = []
        c.avoid = []
        contents = sanitize(msg.content)
        for i in contents:
            if i in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
                to_avoid.append(i)
        if len(to_avoid) != 0:
            for i in to_avoid:
                c.avoid.append(i)

    def gen_string(self):
        return "expressions may not contain any digits used by the previous count."

class No_repeat_digits(Rule):
    unlock = 50
    freq = 20
    scale = 10
    low = 1
    high = 5
    track = []

    def __init__(self, key, lifetime):
        """Expressions may not contain digits that are used multiple times"""
        super().__init__(key, lifetime)

    def check_valid(self, contents, cur, msg):
        so_far = []
        for char in contents:
            if char in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9"):
                if char in so_far:
                    return False
                so_far.append(char)
        return True

    def gen_string(self):
        return "expressions may not contain digits that are used multiple times."    

class Fizzbuzz(Rule):
    unlock = 50
    freq = 14
    scale = 7
    low = 2
    high = 6
    track = []
    skip = 0

    def __init__(self, key, lifetime):
        """Expressions may not contain a certain number"""
        self.multiple = 1000
        self.trigger = "placeholder"
        self.skip = False
        super().__init__(key, lifetime)

    def check_valid(self, contents, cur, msg):
        if (cur % self.multiple == 0) and self.skip:
            # set number to be skipped
            self.__class__.skip = cur + 3


        activated = False
        fb = ""
        for rule in self.__class__.track:
            if cur % rule.multiple == 0:
                # check that number obeys
                activated = True
                fb = fb + rule.trigger

        self.override = activated
        if activated:
            print(fb)
            return contents == fb 

        return True
        

    def set_params(self):
        existing = []
        for rule in self.__class__.track:
            existing.append(rule.multiple)
        if 3 in existing:
            if 4 in existing:
                self.multiple = random.randrange(5, 13, 2)
                self.trigger = "jazz"
                self.skip = True
            else:
                self.multiple = 4
                self.trigger = "buzz"
        else:
            self.multiple = 3
            self.trigger = "fizz"
            

    @classmethod
    def meta_tick_extras(c, cur, msg):
        """Skips the number 3 after jazz is triggered."""
        if cur==(c.skip-1):
            f = open("count.txt", "w")
            f.write(str(cur+2))
            f.close()
            print(str(cur+2))

    @classmethod
    def can_activate(c, cur):
        print("fizzbuzz reached")
        return cur >= c.unlock and len(c.track) <= 2

    def gen_string(self):
        output = f"multiples of **{str(self.multiple)}** must be replaced with `{str(self.trigger)}`. If multiple of this rule exist, all phrases are appended in increasing order of multiplicity."
        if self.skip:
            output += f" In addition, if `x` is a multiple of {str(self.multiple)}, the number `x+3` will be skipped."
        return output



def sanitize(path):
    """Helper function to clean a path name."""
    path = path[0:30]
    length = len(path)
    SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890+-*/()"

    safepath = ""

    for i in range(length):
        if path[i] in SAFE:
            safepath = safepath + path[i]

    if "()" in safepath:
        return ""
    return safepath.lower()



def multiple_check(cur, multiple):
    return cur % (multiple) == 0


rule_list = [Prime, No_n_in_expression, No_reused_digits, No_repeat_digits, Fizzbuzz]

if __name__ == "__main__":
    client.run(token)
