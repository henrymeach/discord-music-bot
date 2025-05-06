"""
Credit goes to Danny from the discord.py community


// Gets rid of the "Error 404: Forbidden" issue
youtube-dl --rm-cache-dir
"""

import discord
from discord.ext import commands, tasks
import youtube_dl
import random
import requests
# from aiohttp import request
from youtubesearchpython import *
# for converting song durations into hh:mm:ss format
import datetime

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.duration = data.get('duration')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.audio_queue = []
        self.has_run = False
        self.current_player = None
        
        self.loop = False


    @commands.command(aliases = ['p'])
    async def play(self, ctx, *, url):
        """Plays from a url (almost anything youtube_dl supports)"""

        if ctx.voice_client is None:
            if ctx.author.voice is not None:
                await ctx.author.voice.channel.connect()
            else:
                return await ctx.send("Yarrrrr... not in a voice channel, drunkard.")
        elif ctx.voice_client.channel != ctx.author.voice.channel:
            return await ctx.send("The bot be already in a voice channel, ye scallywag.")

        if not self.check_queue.is_running():
            self.check_queue.start(ctx)


        if "https://www.youtube.com/playlist?list=" in url:
            # plays youtube playlist
            playlist_videos = Playlist.getVideos(url)
            playlist_videos = playlist_videos["videos"]

            await ctx.send(f"Queuin' up **{len(playlist_videos)}** shanties, 'twill take a while!")

            for playlist_index in range(len(playlist_videos)):
                player = await YTDLSource.from_url(playlist_videos[playlist_index]["link"], loop=self.bot.loop)
                self.audio_queue.append(player)

        else:
            # plays single song
            async with ctx.typing():
                player = await YTDLSource.from_url(url, loop=self.bot.loop)
                self.audio_queue.append(player)
            
            if not ctx.voice_client.is_playing():
                pass
            else:
                await ctx.send(f'Queued: **{player.title}**')

    # sometimes, in the middle of manually skipping (>skip), this may run and cause the bot to skip the song twice
    @tasks.loop(seconds = 3)
    async def check_queue(self, ctx):
        if len(self.audio_queue) > 0 and not ctx.voice_client.is_playing():
            async with ctx.typing():
                player = self.audio_queue.pop(0)
                self.current_player = player
                ctx.voice_client.play(player)
            await ctx.send(f'Now playin\': **{player.title}**')

    
    @commands.command()
    async def insult(self, ctx, *name):
        insult_url = "https://pirate.monkeyness.com/api/insult"
        name_mentioned = ""
        response = requests.get(insult_url)
        response = response.text

        for word in name:
            name_mentioned = name_mentioned + word + " "

        response = name_mentioned + response
        
        await ctx.message.delete()
        await ctx.send(response)

    @commands.command()
    async def say(self, ctx, *phrase: str):
        translate_url = "https://pirate.monkeyness.com/api/translate?english="
        for word in phrase:
            translate_url += word + " "
        response = requests.get(translate_url)
        await ctx.message.delete()
        await ctx.send(response.text)
    
    """
    @commands.command()
    async def loop(self, ctx):
        self.loop = not self.loop

        
        if len(self.audio_queue) > 0:
            self.audio_queue.insert(0, self.current_player)
        else:
            self.audio_queue.insert()
    """

    @commands.command(aliases = ["s"])
    async def skip(self, ctx):
        ctx.voice_client.stop()
        if len(self.audio_queue) > 0:
            async with ctx.typing():
                player = self.audio_queue.pop(0)
                self.current_player = player
                ctx.voice_client.play(player)
            await ctx.send(f'Now playin\': **{player.title}**')

    @commands.command()
    async def shuffle(self, ctx):
        if len(self.audio_queue) > 1:
            random.shuffle(self.audio_queue)
            await ctx.send("Shuffled yer filthy queue.")
        else:
            await ctx.send("Yer queue be too wee to shuffle.")

    @commands.command()
    async def clear(self, ctx):
        self.audio_queue = []
        await ctx.send("The queue has walked the plank!")

    @commands.command(aliases = ["m"])
    async def move(self, ctx, old_index, new_index):
        if len(self.audio_queue) < 1:
            return await ctx.send("Thar ain't enough shanties t' move.")

        if old_index.lower() in ["start", "front", "first", "beginning"]:
            old_index = 1
        elif old_index.lower() in ["end", "back", "last"]:
            old_index = len(self.audio_queue)
        else:
            try:
                old_index = int(old_index)
            except:
                return await ctx.send("Scurvy got yer tongue? Remember, the command be `>move [from] [to]`.")

        new_index_str = f"position {new_index}"

        if new_index.lower() in ["start", "front", "first", "beginning"]:
            new_index = 1
            new_index_str = "front"
        elif new_index.lower() in ["end", "back", "last"]:
            new_index = len(self.audio_queue)
            new_index_str = "back"
        else:
            try:
                new_index = int(new_index)
            except:
                return await ctx.send("Scurvy got yer tongue? Remember, the command be `>move [from] [to]`.")

        self.audio_queue.insert(new_index - 1, self.audio_queue.pop(old_index - 1))

        await ctx.send(f"Moved **{self.audio_queue[new_index - 1].title}** t\' " + new_index_str + ".")

    @commands.command(aliases = ["r"])
    async def remove(self, ctx, position: int):
        if position > len(self.audio_queue) + 1 or position == 0:
            await ctx.send("Thar be no such number; queue be too wee.")
        else:
            await ctx.send(f"Got rid o\': **{self.audio_queue[position - 1].title}**")
            self.audio_queue.pop(position - 1)


    @commands.command(aliases = ["h", "commands", "command", "cmds", "cmd", "info", "information"])
    async def help(self, ctx):
        embedVar = discord.Embed(title = "Looks like ye need a hand!", color = 0xe1d7a1)
        embedVar.add_field(name="Shanty Bot Commands", value="`play [song/playlist]`, `skip`, `queue`, `pause`, `resume`, `move [from] [to]`, `remove [position]`, `shuffle`, `clear`, `leave`", inline=False)
        embedVar.add_field(name="Miscellaneous Commands", value="`insult [name]`, `say [phrase]`, `help`", inline=False)
        embedVar.add_field(name="Credits", value="`Danny (Rapptz)`, `jokii`, `Dhilfluka`", inline=False)
        await ctx.send(embed=embedVar)
    
    
    @commands.command(aliases = ["q"])
    async def queue(self, ctx):

        end_of_shant = "ies"
        if len(self.audio_queue) == 1:
            end_of_shant = "y"

        read_queue = "```" + "Yer swashbucklin' queue: " + str(len(self.audio_queue)) + " shant" + end_of_shant + "\n"
        read_queue += "═══════════════════════════════════════════════════════════════════\n"

        if ctx.voice_client.is_playing():
            current_player_info = f"({datetime.timedelta(seconds = self.current_player.duration)}) {self.current_player.title}\n\n"
        else:
            current_player_info = "Nothing, landlubber\n\n"

        read_queue += "Currently playin': " + current_player_info

        for position in range(len(self.audio_queue)):
            read_queue += str(position + 1) + ". (" + str(datetime.timedelta(seconds = self.audio_queue[position].duration)) + ") " + str(self.audio_queue[position].title) + "\n\n"
        read_queue += "```"

        await ctx.send(read_queue)


    @commands.command(aliases = ["pause","resume"])
    async def pp(self, ctx):
        if ctx.voice_client.channel == ctx.author.voice.channel:
            if ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                await ctx.send("Paused yer shanty.")
            else:
                ctx.voice_client.resume()
                await ctx.send("Resumed yer shanty.")
        else:
            await ctx.send("The bot be in another voice channel, ye scallywag.")


    @commands.command(aliases = ["disconnect", "dc"])
    async def leave(self, ctx):
        """Stops and disconnects the bot from voice"""
        self.audio_queue = []
        await ctx.voice_client.disconnect()


activity = discord.Activity(type = discord.ActivityType.listening, name = "the salty sea")

bot = commands.Bot(command_prefix = ">", activity = activity, status = discord.Status.idle)

# removes default help command and replaces it with new, hip, cooler help command
bot.remove_command('help')


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

bot.add_cog(Music(bot))

# runs the god damn thing using secret
bot.run(ENV_SECRET)
