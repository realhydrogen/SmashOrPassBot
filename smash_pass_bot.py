# smash_pass_bot.py
import discord
import random
import aiohttp
import asyncio
import os
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")  # You'll need this from TMDb

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- TMDb Celebrity Image Fetch ---
async def get_random_celeb(gender="female"):
    gender_code = 1 if gender == "female" else 2
    async with aiohttp.ClientSession() as session:
        page = random.randint(1, 20)
        url = f"https://api.themoviedb.org/3/person/popular?api_key={TMDB_API_KEY}&language=en-US&page={page}"
        async with session.get(url) as resp:
            data = await resp.json()
            people = [p for p in data['results'] if p['gender'] == gender_code and p.get('profile_path')]
            celeb = random.choice(people)
            return {
                "name": celeb["name"],
                "image": f"https://image.tmdb.org/t/p/w500{celeb['profile_path']}"
            }

# --- Smash or Pass Command ---
@bot.command()
async def smash(ctx, gender="female"):
    celeb1 = await get_random_celeb(gender)
    celeb2 = await get_random_celeb(gender)

    embed1 = discord.Embed(title=celeb1["name"])
    embed1.set_image(url=celeb1["image"])
    embed2 = discord.Embed(title=celeb2["name"])
    embed2.set_image(url=celeb2["image"])

    msg1 = await ctx.send("Smash or Pass? 🔥/❌", embed=embed1)
    msg2 = await ctx.send("Smash or Pass? 🔥/❌", embed=embed2)

    for emoji in ["🔥", "❌"]:
        await msg1.add_reaction(emoji)
        await msg2.add_reaction(emoji)

    await asyncio.sleep(10)

    msg1 = await ctx.channel.fetch_message(msg1.id)
    msg2 = await ctx.channel.fetch_message(msg2.id)

    def count_votes(msg):
        votes = {r.emoji: r.count - 1 for r in msg.reactions}
        return votes.get("🔥", 0)

    score1 = count_votes(msg1)
    score2 = count_votes(msg2)

    winner = celeb1["name"] if score1 > score2 else celeb2["name"]
    await ctx.send(f"🔥 {celeb1['name']}: {score1} votes\n🔥 {celeb2['name']}: {score2} votes\n🏆 Winner: **{winner}**")

bot.run(TOKEN)
