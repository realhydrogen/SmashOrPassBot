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
import requests


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
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

spotify = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

async def get_musicbrainz_artist(gender="female"):
    gender = gender.lower()
    query = f"gender:{gender} AND type:person AND tag:music"
    url = f"https://musicbrainz.org/ws/2/artist/?query={query}&fmt=json&limit=20"

    headers = {
        "User-Agent": "SmashPassBot/1.0 (https://example.com/contact)"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()

    artists = data.get("artists", [])
    filtered_artists = [a for a in artists if a.get("name")]

    if not filtered_artists:
        return None

    artist = random.choice(filtered_artists)

    return {
        "name": artist["name"],
        # Placeholder image or integrate a lookup (e.g. Wikipedia or Bing image)
        "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/480px-No_image_available.svg.png"
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
    category_map = {
        "model": "Category:Female_models",
        "pornstar": "Category:American_female_pornographic_film_actors",
        "influencer": "Category:Social_media_influencers"
    }

    if category == "all":
        category = random.choice(["model", "pornstar", "influencer"])

    wiki_category = category_map.get(category)
    if not wiki_category:
        return None

    # Step 1: Get list of pages in the category
    async with aiohttp.ClientSession() as session:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": wiki_category,
            "cmlimit": 20
        }
        async with session.get(url, params=params) as resp:
            data = await resp.json()

        pages = data.get("query", {}).get("categorymembers", [])
        if not pages:
            return None

        page_title = random.choice(pages)["title"]

        # Step 2: Get image for selected page
        params = {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "titles": page_title,
            "pithumbsize": 500
        }
        async with session.get(url, params=params) as resp:
            image_data = await resp.json()

        image_pages = image_data.get("query", {}).get("pages", {})
        for page in image_pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                return {
                    "name": page_title,
                    "image": thumb
                }

    return None

async def get_random_celeb(gender="female"):
    url = 'https://api.api-ninjas.com/v1/celebrity'
    headers = {'X-Api-Key': os.getenv("API_NINJAS_KEY")}
    params = {"gender": gender}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            print(f"API Status: {response.status}")
            print(f"API Response: {await response.text()}")
            if response.status == 200:
                data = await response.json()
                if data:
                    celeb = random.choice(data)
                    image_url = f"https://ui-avatars.com/api/?name={celeb['name'].replace(' ', '+')}&background=random"
                    return {
                        "name": celeb["name"],
                        "image": image_url
                    }
    return None

async def get_wiki_image_for_name(name: str):
    search_url = "https://en.wikipedia.org/w/api.php"
    search_params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": name,
        "srlimit": 1
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(search_url, params=search_params) as resp:
            search_data = await resp.json()

        search_results = search_data.get("query", {}).get("search", [])
        if not search_results:
            return None

        page_title = search_results[0]["title"]

        image_params = {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "titles": page_title,
            "pithumbsize": 500
        }
        async with session.get(search_url, params=image_params) as resp:
            image_data = await resp.json()

        pages = image_data.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {}).get("source")
            if thumb:
                return {
                    "name": page_title,
                    "image": thumb
                }

    return None

def log_match(winner, loser, a_votes, b_votes, gender):
    log_data = {
        "winner": winner,
        "loser": loser,
        "votes": {"🅰️": a_votes, "🅱️": b_votes},
        "gender": gender,
        "timestamp": datetime.utcnow().isoformat()
    }
    with open("match_log.json", "a") as f:
        f.write(json.dumps(log_data) + "\n")

@bot.tree.command(name="smash", description="Vote on who you would smash")
@app_commands.describe(
    gender="Choose male or female",
    duration="How many seconds to vote (5-60)"
)
async def smash(
    interaction: discord.Interaction,
    gender: Literal["male", "female"] = "female",
    duration: int = 10
):
    await interaction.response.send_message("🔄 Loading matchup...", ephemeral=True)

    if duration < 5 or duration > 60:
        await interaction.edit_original_response(content="⏱ Duration must be between 5 and 60 seconds.")
        return

    if smash_lock.locked():
        await interaction.edit_original_response(content="⚠️ A match is already running. Please wait.")
        return

    async with smash_lock:
        celeb1 = await get_random_celeb(gender)
        celeb2 = await get_random_celeb(gender)

if not celeb1 or not celeb2:
    await interaction.edit_original_response(content="❌ Couldn't fetch enough celebrity data. Try again!")
    return

    # Retry if same name (max 3 tries)
    attempts = 0
    while celeb1["name"] == celeb2["name"] and attempts < 3:
    celeb2 = await get_random_celeb(gender)
    if not celeb2:
        await interaction.edit_original_response(content="❌ Failed to fetch unique celebrities.")
        return
    attempts += 1

    if not celeb1 or not celeb2:
        await interaction.edit_original_response(content="❌ Couldn't fetch enough celebrity data. Try again!")
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

        message = await interaction.edit_original_response(content=None, embed=embed, attachments=[file])
        await message.add_reaction("🅰️")
        await message.add_reaction("🅱️")
        await asyncio.sleep(duration)

        updated_message = await interaction.channel.fetch_message(message.id)
        reactions = {r.emoji: r.count - 1 for r in updated_message.reactions}
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
        )

        global last_winner
        if winner != "It's a tie!":
            last_winner = {
                "name": celeb1["name"] if winner == celeb1["name"] else celeb2["name"],
                "image": celeb1["image"] if winner == celeb1["name"] else celeb2["image"],
                "gender": gender,
            }

        result_text = f"""
🅰️ {celeb1['name']}: {a_votes} votes  
🅱️ {celeb2['name']}: {b_votes} votes  
🏆 **Winner: {winner}**
"""
        await interaction.followup.send(result_text)

@bot.tree.command(name="smashing", description="Pit the previous winner against a new contender")
async def smashing(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Loading next matchup...", ephemeral=True)

    global last_winner
    if not last_winner:
        await interaction.edit_original_response(content="⚠️ No previous winner found. Run `/smash` first!")
        return

    new_celeb = await get_random_celeb(last_winner["gender"])
    if not new_celeb:
        await interaction.edit_original_response(content="❌ Couldn't fetch a new contender. Try again!")
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

    message = await interaction.edit_original_response(content=None, embed=embed, attachments=[file])
    await message.add_reaction("🅰️")
    await message.add_reaction("🅱️")
    await asyncio.sleep(10)

    updated_message = await interaction.channel.fetch_message(message.id)
    reactions = {r.emoji: r.count - 1 for r in updated_message.reactions}
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
    await interaction.response.send_message("📊 Gathering top results...", ephemeral=True)

    if not os.path.exists("match_log.json"):
        await interaction.edit_original_response(content="❌ No match history found.")
        return

    from collections import Counter

    smash_counts = Counter()

    with open("match_log.json", "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("winner") and entry["winner"] != "tie":
                    smash_counts[entry["winner"]] += 1
            except json.JSONDecodeError:
                continue

    if not smash_counts:
        await interaction.edit_original_response(content="⚠️ No smash data to rank yet.")
        return

    top_celebrities = smash_counts.most_common(5)
    embed = discord.Embed(title="🏆 Top 5 Most Smashed Celebrities")

    for i, (name, count) in enumerate(top_celebrities, start=1):
        embed.add_field(name=f"#{i} {name}", value=f"{count} smashes", inline=False)
        image_url = f"https://ui-avatars.com/api/?name={top_celebrities[0][0].replace(' ', '+')}&background=random"
        embed.set_thumbnail(url=image_url)

    await interaction.edit_original_response(content=None, embed=embed)


@bot.event
async def on_ready():
    print(f"Bot is ready! Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Bot is in {len(bot.guilds)} guilds")
    
    try:
        print("Attempting to sync commands...")
        # Try global sync first
        await bot.tree.sync()
        print("Global sync completed!")
        
        # Then sync to each guild individually
        for guild in bot.guilds:
            try:
                await bot.tree.sync(guild=guild)
                print(f"✅ Synced commands to guild: {guild.name} ({guild.id})")
            except Exception as e:
                print(f"❌ Failed to sync to {guild.name}: {str(e)}")
    except Exception as e:
        print(f"Failed to sync commands: {str(e)}")
    
bot.run(TOKEN)
