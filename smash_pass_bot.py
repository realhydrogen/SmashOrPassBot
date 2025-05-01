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
import wikipediaapi
from typing import Literal
import json
from datetime import datetime

# Global lock and winner memory
smash_lock = asyncio.Lock()
last_winner = None

wiki = wikipediaapi.Wikipedia(
    language='en',
    user_agent='SmashPassBot/1.0 (https://example.com/contact)'
)

load_dotenv()
print("SmashPassBot starting up...")
print("DISCORD_TOKEN:", os.getenv("DISCORD_TOKEN"))
TOKEN = os.getenv("DISCORD_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

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

async def get_wiki_celeb(gender="female", category="model"):
    search_terms = {
        "model": f"{gender} fashion model",
        "pornstar": f"{gender} pornographic actor",
        "influencer": f"{gender} social media influencer"
    }
    search_query = search_terms.get(category, f"{gender} celebrity")

    async with aiohttp.ClientSession() as session:
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": search_query,
            "srlimit": 20
        }
        async with session.get(search_url, params=search_params) as resp:
            data = await resp.json()
        pages = data.get("query", {}).get("search", [])
        if not pages:
            return None
        page_title = random.choice(pages)["title"]

        image_params = {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "titles": page_title,
            "pithumbsize": 500
        }
        async with session.get(search_url, params=image_params) as resp:
            image_data = await resp.json()
        image_pages = image_data.get("query", {}).get("pages", {})
        for page in image_pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                return {"name": page_title, "image": thumb}
    return None

async def get_random_celeb(gender="female", category="actor"):
    if category == "actor":
        return await get_tmdb_celeb(gender)
    elif category == "singer":
        celeb = await get_spotify_artist(gender)
        if celeb:
            return celeb
    elif category in ["model", "influencer", "pornstar"]:
        celeb = await get_wiki_celeb(gender, category)
        if celeb:
            return celeb
    return await get_tmdb_celeb(gender)

def log_match(winner, loser, a_votes, b_votes, gender, category):
    log_data = {
        "winner": winner,
        "loser": loser,
        "votes": {"🅰️": a_votes, "🅱️": b_votes},
        "gender": gender,
        "category": category,
        "timestamp": datetime.utcnow().isoformat()
    }
    with open("match_log.json", "a") as f:
        f.write(json.dumps(log_data) + "\n")

@bot.tree.command(name="smash", description="Vote on who you would smash")
@app_commands.describe(
    gender="Choose male or female",
    category="Choose a type of celebrity",
    duration="How many seconds to vote (5-60)"
)
async def smash(interaction: discord.Interaction,
    gender: Literal["male", "female"] = "female",
    category: Literal["actor", "singer", "model", "pornstar", "influencer"] = "actor",
    duration: int = 10):
    await interaction.response.defer()
    if duration < 5 or duration > 60:
        await interaction.followup.send("⏱ Duration must be between 5 and 60 seconds.", ephemeral=True)
        return
    if smash_lock.locked():
        await interaction.followup.send("⚠️ A Smash or Pass match is already running. Please wait!", ephemeral=True)
        return
    async with smash_lock:
        celeb1 = await get_random_celeb(gender, category)
        celeb2 = await get_random_celeb(gender, category)
        if not celeb1 or not celeb2:
            await interaction.followup.send("❌ Couldn't fetch enough celebrity data. Try again!", ephemeral=True)
            return
        IMG_WIDTH = 300
        IMG_HEIGHT = 450
        GAP = 20
        CANVAS_WIDTH = IMG_WIDTH * 2 + GAP
        async with aiohttp.ClientSession() as session:
            async with session.get(celeb1["image"]) as r1:
                img1_bytes = await r1.read()
            async with session.get(celeb2["image"]) as r2:
                img2_bytes = await r2.read()
        img1 = Image.open(BytesIO(img1_bytes)).resize((IMG_WIDTH, IMG_HEIGHT))
        img2 = Image.open(BytesIO(img2_bytes)).resize((IMG_WIDTH, IMG_HEIGHT))
        combined = Image.new("RGB", (CANVAS_WIDTH, IMG_HEIGHT), color=(0, 0, 0))
        combined.paste(img1, (0, 0))
        combined.paste(img2, (IMG_WIDTH + GAP, 0))
        draw = ImageDraw.Draw(combined)
        font = ImageFont.load_default()
        text = "VS"
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(((CANVAS_WIDTH // 2) - (text_width // 2), (IMG_HEIGHT // 2) - (text_height // 2)),
                  text, fill=(255, 255, 255), font=font)
        buffer = BytesIO()
        combined.save(buffer, format="PNG")
        buffer.seek(0)
        file = discord.File(fp=buffer, filename="versus.png")
        embed = discord.Embed(title="Who would you smash?")
        embed.add_field(name="🅰️ " + celeb1["name"], value="Left", inline=True)
        embed.add_field(name="🅱️ " + celeb2["name"], value="Right", inline=True)
        embed.set_image(url="attachment://versus.png")
        embed.set_footer(text=f"Vote with 🅰️ or 🅱️ - {duration} seconds!")
        msg = await interaction.followup.send(embed=embed, file=file)
        await msg.add_reaction("🅰️")
        await msg.add_reaction("🅱️")
        await asyncio.sleep(duration)
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
        log_match(
            winner=winner if winner != "It's a tie!" else "tie",
            loser=celeb2["name"] if winner == celeb1["name"] else celeb1["name"],
            a_votes=a_votes,
            b_votes=b_votes,
            gender=gender,
            category=category
        )
        global last_winner
        if winner != "It's a tie!":
            last_winner = {
                "name": celeb1["name"] if winner == celeb1["name"] else celeb2["name"],
                "image": celeb1["image"] if winner == celeb1["name"] else celeb2["image"],
                "gender": gender,
                "category": category
            }
        await interaction.followup.send(f"""
🅰️ {celeb1['name']}: {a_votes} votes  
🅱️ {celeb2['name']}: {b_votes} votes  
🏆 **Winner: {winner}**
""")

@bot.tree.command(name="smashing", description="Pit the previous winner against a new contender")
async def smashing(interaction: discord.Interaction):
    await interaction.response.defer()
    global last_winner
    if not last_winner:
        await interaction.followup.send("⚠️ No previous winner found. Run `/smash` first!", ephemeral=True)
        return
    new_celeb = await get_random_celeb(last_winner["gender"], last_winner["category"])
    if not new_celeb:
        await interaction.followup.send("❌ Couldn't fetch a new contender. Try again!", ephemeral=True)
        return
    IMG_WIDTH = 300
    IMG_HEIGHT = 450
    GAP = 20
    CANVAS_WIDTH = IMG_WIDTH * 2 + GAP
    async with aiohttp.ClientSession() as session:
        async with session.get(last_winner["image"]) as r1:
            img1_bytes = await r1.read()
        async with session.get(new_celeb["image"]) as r2:
            img2_bytes = await r2.read()
    img1 = Image.open(BytesIO(img1_bytes)).resize((IMG_WIDTH, IMG_HEIGHT))
    img2 = Image.open(BytesIO(img2_bytes)).resize((IMG_WIDTH, IMG_HEIGHT))
    combined = Image.new("RGB", (CANVAS_WIDTH, IMG_HEIGHT), color=(0, 0, 0))
    combined.paste(img1, (0, 0))
    combined.paste(img2, (IMG_WIDTH + GAP, 0))
    draw = ImageDraw.Draw(combined)
    font = ImageFont.load_default()
    text = "VS"
    bbox = font.getbbox(text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(((CANVAS_WIDTH // 2) - (text_width // 2), (IMG_HEIGHT // 2) - (text_height // 2)),
              text, fill=(255, 255, 255), font=font)
    buffer = BytesIO()
    combined.save(buffer, format="PNG")
    buffer.seek(0)
    file = discord.File(fp=buffer, filename="versus.png")
    embed = discord.Embed(title=f"{last_winner['name']} defends the title!")
    embed.add_field(name="🅰️ " + last_winner["name"], value="Champion", inline=True)
    embed.add_field(name="🅱️ " + new_celeb["name"], value="Challenger", inline=True)
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
        winner = last_winner["name"]
    elif b_votes > a_votes:
        winner = new_celeb["name"]
        last_winner = new_celeb
    else:
        winner = "It's a tie!"
    await interaction.followup.send(f"""
🅰️ {last_winner['name']}: {a_votes} votes  
🅱️ {new_celeb['name']}: {b_votes} votes  
🏆 **Winner: {winner}**
""")
    
@bot.tree.command(name="top", description="Show the top 5 most smashed celebrities")
async def top(interaction: discord.Interaction):
    await interaction.response.defer()

    if not os.path.exists("match_log.json"):
        await interaction.followup.send("No match history found.", ephemeral=True)
        return

    from collections import Counter

    smash_counts = Counter()

    with open("match_log.json", "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("winner") and entry.get("winner") != "tie":
                    smash_counts[entry["winner"]] += 1
            except json.JSONDecodeError:
                continue

    if not smash_counts:
        await interaction.followup.send("No smash data to rank yet.", ephemeral=True)
        return

    top_celebrities = smash_counts.most_common(5)
    embed = discord.Embed(title="🏆 Top 5 Most Smashed Celebrities")

    for i, (name, count) in enumerate(top_celebrities, start=1):
        embed.add_field(name=f"#{i} {name}", value=f"{count} smashes", inline=False)

    await interaction.followup.send(embed=embed)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await bot.tree.sync(guild=guild)
        print(f"✅ Synced commands to guild: {guild.name} ({guild.id})")
    print(f"{bot.user} is ready.")
