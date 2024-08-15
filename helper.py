# A set of general helper functions.

def admin(func):

    async def wrapper(self, *args, **kwargs):
        ADMINS = (732415222706339840,)
        ctx = args[0]
        if ctx.author.id not in ADMINS:
            await ctx.send("Unfortunately, you are too weak and pathetic to comprehend this power. Sit down.")
            return

        await func(self, *args, **kwargs)

    return wrapper

def strip(id_num, default = -1):
    """Function to strip off the fluff when mentioning a channel or role and to just return the ID. If the format is invalid, it returns -1 instead."""
    if id_num is None:
        return default
    try:
        id_num = id_num.translate({ord(i): None for i in '<!@>'})
        id_num = int(id_num)
    except ValueError:
        return default
    return id_num
