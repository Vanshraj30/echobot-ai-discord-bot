

import discord
import random
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
import os
import json
import aiohttp
import google.generativeai as genai
import whisper
from PIL import Image
import requests
import subprocess
import sqlite3
model_whisper = whisper.load_model("base")
queues={} 

funny_emojis = [
    "😂", "🤣", "😜", "😎", "🤡", "🐸", "💀", "👀",
    "🔥", "😏", "🥴", "🤯", "😹", "🫠", "😈"
]

# Load environment variables
load_dotenv()

# Enable intents
intents = discord.Intents.default()
intents.message_content = True  # IMPORTANT


bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.command()
async def hello(ctx):
    await ctx.send("Hello! ")


@bot.command()
async def ping(ctx):
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')


async def process_voice(message):
    attachment=message.attachments[0]
    file_path="voice.org"
    wav_path="voice.wav"
    await attachment.save(file_path)
    subprocess.run(["ffmpeg","-i",file_path,wav_path])

    result=model_whisper.transcribe(wav_path)
    text=result["text"].lower()

    os.remove(file_path)
    os.remove(wav_path)

    return text


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Simple greeting
    if message.content.lower() == "hi":
        await message.channel.send("Hey there!")

    # Voice message processing
    if message.attachments:
        attachment = message.attachments[0]

        if attachment.filename.lower().endswith(
            ('.wav', '.mp3', '.ogg', '.m4a')
        ):
            await message.channel.send(
                "🎤 Processing your voice message..."
            )

            try:
                text = await process_voice(message)

                await message.channel.send(
                    f"Heard: {text}"
                )

                await handle_voice_command(
                    message,
                    text
                )

            except Exception as e:
                await message.channel.send(
                    "❌ Error processing voice"
                )
                print(e)

    triggered = False

    import re

    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]",
        flags=re.UNICODE
    )

    # Emoji reaction
    if emoji_pattern.search(message.content):
        await message.channel.send(
            random.choice(funny_emojis)
        )
        triggered = True

    # GIF reaction
    if "gif" in message.content.lower() and not triggered:
        await message.channel.send(
            random.choice(funny_emojis)
        )
        triggered = True

    # Screenshot Analyzer
    if message.attachments and not triggered:

        attachment = message.attachments[0]

        if attachment.filename.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp")
        ):

            try:

                await message.channel.send(
                    "🔍 Analyzing screenshot..."
                )

                image_path = "temp_image.png"

                response = requests.get(attachment.url)

                with open(image_path, "wb") as f:
                    f.write(response.content)

                with Image.open(image_path) as img:

                    analysis = model.generate_content([
                        """
                        Analyze this screenshot.

                        If it contains:
                        - coding errors
                        - terminal output
                        - websites
                        - resumes
                        - UI designs
                        - documents

                        Explain what you see and provide suggestions.
                        """,
                        img
                    ])

                await message.channel.send(
                    analysis.text[:1900]
                )

                if os.path.exists(image_path):
                    os.remove(image_path)

                triggered = True

            except Exception as e:

                print(
                    "Screenshot Error:",
                    e
                )

                await message.channel.send(
                    "❌ Failed to analyze screenshot."
                )

    await bot.process_commands(message)


@bot.command()
async def roll (ctx):
    await ctx.send(f'You Rolled a {random.randint(1, 6)}')  

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("Join a voice channel first!")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel")
    else:
        await ctx.send("I'm not in a voice channel!") 

@bot.command()
async def play(ctx, *, query):
    if not ctx.author.voice:
        await ctx.send("Join a voice channel first!")
        return

    vc = ctx.voice_client

    if not vc:
        vc = await ctx.author.voice.channel.connect()

    import yt_dlp

    ydl_opts = {
        'format': 'bestaudio',
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)

        if 'entries' in info:
            info = info['entries'][0]

        url = info['url']
        title = info['title']

    guild_id = ctx.guild.id

    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].append((url, title))

    # If nothing is playing → start playing
    if not vc.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"Added to queue: **{title}**")


async def play_next(ctx):
    guild_id = ctx.guild.id
    vc = ctx.voice_client

    if guild_id in queues and queues[guild_id]:
        url, title = queues[guild_id].pop(0)

        source = await discord.FFmpegOpusAudio.from_probe(url, options='-vn')

        vc.play(source, after=lambda e: bot.loop.create_task(play_next(ctx)))

        await ctx.send(f"Now playing: **{title}**")
    else:
        await vc.disconnect()
        queues.pop(guild_id, None)

@bot.command()
async def skip(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("Skipped!")
    else:
        await ctx.send("Nothing to skip!")

@bot.command()
async def pause(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("Paused ⏸️")
    else:
        await ctx.send("Nothing is playing!")


@bot.command()
async def resume(ctx):
    vc = ctx.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("Resumed ▶")
    else:
        await ctx.send("Nothing is paused!") 

@bot.command(name="queue")
async def show_queue(ctx):
    guild_id = ctx.guild.id

    # If no queue exists
    if guild_id not in queues or not queues[guild_id]:
        await ctx.send("📭 Queue is empty!")
        return

    msg = ""

    for i, (url, title) in enumerate(queues[guild_id], start=1):
        msg += f"{i}. {title}\n"

    await ctx.send(f"🎶 **Current Queue:**\n{msg}")   


leaderboard_file = "leaderboard.json"
def load_leaderboard():
    try:
        with open(leaderboard_file,"r") as f:
            return json.load(f)
    except:
        return {}     
def save_leaderboard(leaderboard):
    with open(leaderboard_file,"w") as f:
        json.dump(leaderboard,f,indent=4)

leaderboard=load_leaderboard()                                              
    

@bot.command()
async def rps(ctx, user_choice):
    choices = ['rock', 'paper', 'scissors']
    choice = user_choice.lower()
    if choice not in choices:
        await ctx.send("choose rock,paper or scissors!")
        return

    bot_choice = random.choice(choices)
    result = ""

    if choice == bot_choice:
        result = "it is a draw!"
    elif (choice == 'rock' and bot_choice == 'scissors') or \
         (choice == 'paper' and bot_choice == 'rock') or \
         (choice == 'scissors' and bot_choice == 'paper'):
        result = "You win!"
        leaderboard[str(ctx.author.id)] = leaderboard.get(str(ctx.author.id), 0) + 1
    else:
        result = "You lose!"
    save_leaderboard(leaderboard)

    await ctx.send(
        f"You chose **{choice}**\n" 
        f"Bot chose **{bot_choice}**\n"
        f"{result}"
    )
    

@bot.command() 
async def leaderboard_cmd(ctx):
    if not leaderboard:
        await ctx.send("No games played yet!")
        return

    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    msg = "**RPS Leaderboard:**\n"

    for i,(user_id,score) in enumerate(sorted_leaderboard[:10],start=1):
        user = await bot.fetch_user(int(user_id))
        msg += f"{i}. {user.name} - {score} wins\n"

    await ctx.send(msg)    

@bot.command()
async def resetscore(ctx):
    user_id = str(ctx.author.id)

    if user_id in leaderboard:
        leaderboard[user_id] = 0
        save_leaderboard(leaderboard)
        await ctx.send("Your score has been reset to 0 ")
    else:
        await ctx.send("You don’t have a score yet!")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetleaderboard(ctx):
    leaderboard.clear()
    save_leaderboard(leaderboard)
    await ctx.send("Leaderboard has been completely cleared")        


@bot.command()
async def weather(ctx, *, city):
    api_key = os.getenv("Weather_API_Key")
    if not api_key:
        await ctx.send("Weather API key not found!")
        return
    url=f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data=await resp.json()
            if data.get("cod")!=200:
                await ctx.send(f"City {city} not found!")
                return
            temp=data["main"]["temp"]
            desc=data["weather"][0]["description"]
            feels=data["main"]["feels_like"]
            humidity=data["main"]["humidity"]
            await ctx.send(
                f"Weather in **{city.title()}**:\n"
                f"Temperature: {temp}°C\n"
                f"Feels like: {feels}°C\n"
                f"Condition: {desc.title()}\n"
                f"Humidity: {humidity}%"
            )


genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-flash-latest")

@bot.command()
async def ask(ctx, *, question):
    try:

        conn = sqlite3.connect("memory.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT memory FROM memories WHERE user_id=?",
            (str(ctx.author.id),)
        )

        rows = cursor.fetchall()
        conn.close()

        memory_text = "\n".join(
            row[0] for row in rows
        )

        prompt = f"""
        User Memories:
        {memory_text}

        Question:
        {question}

        Answer using the memories if relevant.
        """

        response = model.generate_content(prompt)

        answer = response.text

        if len(answer) > 1900:
            answer = answer[:1900] + "..."

        await ctx.send(answer)

    except Exception as e:
        await ctx.send("Error talking to AI")
        print(e)

@bot.command(name="help")
async def help_cmd(ctx):
    embed = discord.Embed(
        title="Bot Commands",
        description="Here are the available commands:",
        color=discord.Color.blue()
    )

    #music
    embed.add_field(
        name="Music",
        value=(
            "`!play <song name or URL>` - Play a song in your voice channel\n"
            "`!skip` - Skip the current song\n"
            "`!pause` - Pause the music\n"
            "`!resume` - Resume the music\n"
            "`!queue` - Show the current music queue\n"
            "`!leave` - Bot leaves the voice channel"
        ),
        inline=False
    )

    #games
    embed.add_field(
        name="Games",
        value=(
            "`!rps <rock/paper/scissors>` - Play Rock-Paper-Scissors\n"
            "`!leaderboard` - Show RPS leaderboard\n"
            "`!resetscore` - Reset your RPS score\n"
            "`!resetleaderboard` - Clear the entire RPS leaderboard (Admin only)"
        ),
        inline=False
    )

    #utility
    embed.add_field(
        name="Utility",
        value=(
            "`!ping` - check bot latency\n"
            "`!roll` - Roll a dice\n"
            "`!clear <number>` - Clear messages\n"
        ),
        inline=False
    )
    # AI Memory
    embed.add_field(
    name="🧠 AI Memory",
    value=(
        "`!remember <text>` - Store information permanently\n"
        "`!recall` - View your saved memories\n"
        "`!ask <question>` - Ask AI using your stored memories"
    ),
    inline=False
)

    #APIs
    embed.add_field(
        name="APIs",
        value=(
            "`!weather <city>` - Get current weather for a city\n"
            "`!ask <question>` - Ask the AI a question"
        ),
        inline=False
    )

    embed.add_field(
    name="🤖 AI Features",
    value=(
        "`!ask <question>` - Ask the AI a question\n"
        "`!remember <text>` - Save information to memory\n"
        "`!recall` - View saved memories\n"
        "`Upload a screenshot` - AI analyzes coding errors, websites, documents, resumes, and UI designs automatically"
    ),
    inline=False
)

    embed.set_footer(text="Made by Vansh")
    await ctx.send(embed=embed)



async def handle_voice_command(message, text):
    ctx = await bot.get_context(message)

    text = text.lower().strip()

    
    if any(word in text for word in ["play", "pley", "plai", "lead", "start"]):
        
        
        for cmd in ["play", "pley", "plai", "lead", "start", "song", "music"]:
            text = text.replace(cmd, "")

        song = text.strip()

        if song:
            await ctx.invoke(bot.get_command("play"), query=song)
        else:
            await message.channel.send(" Tell me which song to play!")

   
    elif any(word in text for word in ["skip", "next"]):
        await ctx.invoke(bot.get_command("skip"))

  
    elif "pause" in text or "stop" in text:
        await ctx.invoke(bot.get_command("pause"))

  
    elif any(word in text for word in ["resume", "continue"]):
        await ctx.invoke(bot.get_command("resume"))

  
    elif any(word in text for word in ["leave", "disconnect", "exit"]):
        await ctx.invoke(bot.get_command("leave"))

    else:
        await message.channel.send(" I didn't understand the command.")


@bot.command()
async def remember(ctx, *, text):

    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO memories (user_id, memory) VALUES (?, ?)",
        (str(ctx.author.id), text)
    )

    conn.commit()
    conn.close()

    await ctx.send("Memory stored!")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int):

    if amount <= 0:
        await ctx.send("Please enter a number greater than 0.")
        return

    deleted = await ctx.channel.purge(limit=amount + 1)

    msg = await ctx.send(
        f"🗑️ Deleted {len(deleted)-1} messages."
    )

    await asyncio.sleep(3)

    await msg.delete()

@bot.command()
async def recall(ctx):

    conn = sqlite3.connect("memory.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT memory FROM memories WHERE user_id=?",
        (str(ctx.author.id),)
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:
        await ctx.send("No memories found.")
        return

    msg = "\n".join(
        f"• {row[0]}"
        for row in rows[-10:]
    )

    await ctx.send(
        f"🧠 Your Memories:\n{msg}"
    )

conn = sqlite3.connect("memory.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    memory TEXT
)
""")

conn.commit()
conn.close()



# Run bot
bot.run(os.getenv("TOKEN"))

