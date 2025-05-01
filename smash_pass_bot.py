# smash_pass_bot.py
import discord
import random
import aiohttp
import asyncio
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

spotify = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

async def get_spotify_artist(gender="female"):
    genre_pool = {
        "female": ["pop", "r&b", "k-pop", "latin", "female vocalists"],
        "male": ["rap", "rock", "hip hop", "male vocalists"]
    }

    genre = random.choice(genre_pool[gender])
    results = spotify.search(q=f'genre:"{genre}"', type="artist", limit=20)
    artists = [a for a in results["artists"]["items"] if a.get("images")]

    if not artists:
        return None

    artist = random.choice(artists)
    return {
        "name": artist["name"],
        "image": artist["images"][0]["url"]
    }

# --- TMDb Support ---
async def get_tmdb_celeb(gender="female"):
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

# --- Placeholder until other APIs are added ---
async def get_random_celeb(gender="female"):
    source = random.choice(["tmdb", "spotify"])

    if source == "tmdb":
        return await get_tmdb_celeb(gender)
    else:
        celeb = await get_spotify_artist(gender)
        if celeb:
            return celeb
        return await get_tmdb_celeb(gender)  # fallback

# --- Slash Command ---
@bot.tree.command(name="smash", description="Vote who you would smash")
@app_commands.describe(gender="Choose male or female")
async def smash(interaction: discord.Interaction, gender: str = "female"):
    await interaction.response.defer()

    celeb1 = await get_random_celeb(gender)
    celeb2 = await get_random_celeb(gender)

    # Download images
    async with aiohttp.ClientSession() as session:
        async with session.get(celeb1["image"]) as r1:
            img1_bytes = await r1.read()
        async with session.get(celeb2["image"]) as r2:
            img2_bytes = await r2.read()

    # Combine images with "VS"
    img1 = Image.open(BytesIO(img1_bytes)).resize((300, 450))
    img2 = Image.open(BytesIO(img2_bytes)).resize((300, 450))
    combined = Image.new("RGB", (620, 450), color=(0, 0, 0))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (320, 0))

    draw = ImageDraw.Draw(combined)
    font = ImageFont.load_default()
    text = "VS"
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(((310 - text_width // 2), (225 - text_height // 2)), text, fill=(255, 255, 255), font=font)

    # Send image
    buffer = BytesIO()
    combined.save(buffer, format="PNG")
    buffer.seek(0)
    file = discord.File(fp=buffer, filename="versus.png")

    embed = discord.Embed(title="Who would you smash?")
    embed.add_field(name="🅰️ " + celeb1["name"], value="Left", inline=True)
    embed.add_field(name="🅱️ " + celeb2["name"], value="Right", inline=True)
    embed.set_image(url="attachment://versus.png")
    embed.set_footer(text="Vote with 🅰️ or 🅱️ - 10 seconds!")

    msg = await interaction.followup.send(embed=embed, file=file)
    await msg.add_reaction("🅰️")
    await msg.add_reaction("🅱️")

    await asyncio.sleep(10)

    msg = await interaction.channel.fetch_message(msg.id)
    reactions = {r.emoji: r.count - 1 for r in msg.reactions}
    a_votes = reactions.get("🅰️", 0)
    b_votes = reactions.get("🅱️", 0)

    if a_votes > b_votes:
        winner = celeb1["name"]
    elif b_votes > a_votes:
        winner = celeb2["name"]
    else:
        winner = "It's a tie!"

    await interaction.followup.send(f"""
🅰️ {celeb1['name']}: {a_votes} votes  
🅱️ {celeb2['name']}: {b_votes} votes  
🏆 **Winner: {winner}**
""")

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is ready and slash commands are synced.")
