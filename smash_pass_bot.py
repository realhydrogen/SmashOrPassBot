# smash_pass_bot.py
import discord
import random
import aiohttp
import asyncio
import os
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
from PIL import Image
from io import BytesIO

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

    # Download both images
    async with aiohttp.ClientSession() as session:
        async with session.get(celeb1["image"]) as r1:
            img1_bytes = await r1.read()
        async with session.get(celeb2["image"]) as r2:
            img2_bytes = await r2.read()

    img1 = Image.open(BytesIO(img1_bytes)).resize((300, 450))
    img2 = Image.open(BytesIO(img2_bytes)).resize((300, 450))

    # Combine side by side
    combined = Image.new("RGB", (600, 450))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (300, 0))

    buffer = BytesIO()
    combined.save(buffer, format="PNG")
    buffer.seek(0)
    file = discord.File(fp=buffer, filename="combo.png")

    embed = discord.Embed(title="Who would you smash? React below!")
    embed.add_field(name="🅰️ " + celeb1["name"], value="Left", inline=True)
    embed.add_field(name="🅱️ " + celeb2["name"], value="Right", inline=True)
    embed.set_image(url="attachment://combo.png")
    embed.set_footer(text="🅰️ = Left | 🅱️ = Right | 10 seconds to vote")

    msg = await ctx.send(embed=embed, file=file)

    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")

    await asyncio.sleep(10)
    msg = await ctx.channel.fetch_message(msg.id)

    votes = {r.emoji: r.count - 1 for r in msg.reactions}
    a_votes = votes.get("🅰️", 0)
    b_votes = votes.get("🅱️", 0)

    if a_votes > b_votes:
        winner = celeb1["name"]
    elif b_votes > a_votes:
        winner = celeb2["name"]
    else:
        winner = "It's a tie!"

    await ctx.send(f"""
🅰️ {celeb1['name']}: {a_votes} votes  
🅱️ {celeb2['name']}: {b_votes} votes  
🏆 **Winner: {winner}**
""")

bot.run(TOKEN)
