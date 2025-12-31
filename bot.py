import telebot
import requests
import urllib.parse
import json
import os
import time
import signal
import sys
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========= CONFIG =========
BOT_TOKEN = ""              # Telegram Bot Token
TMDB_API_KEY = ""           # TMDB API Key
PRIVATE_CHANNEL_ID =   # Private channel with movies
MOVIES_DB_FILE = "movies_db.json"  # Local database for movie tracking

WEBSITE_URL = "https://www.filmyfiy.mov/site-1.html?to-search="
CHANNEL_USERNAME = ""   # 👈 apna channel username (Join Us wala)
HOW_TO_DOWNLOAD_LINK = "https://t.me/filmyrajamovie/5"
REQUEST_GROUP_LINK = "https://t.me/+CoqbU5nFeCU4ZDFl"
# ==========================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

def load_movies_db():
    """Load movies database from JSON file"""
    if os.path.exists(MOVIES_DB_FILE):
        try:
            with open(MOVIES_DB_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_movies_db(data):
    """Save movies database to JSON file"""
    try:
        with open(MOVIES_DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error saving movies DB: {e}")
        return False

def api_request_with_retry(url, params=None, max_retries=3):
    """Make API request with retry logic"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            print(f"⏱️ API timeout (attempt {attempt + 1}/{max_retries})")
        except requests.exceptions.ConnectionError:
            print(f"🔌 API connection error (attempt {attempt + 1}/{max_retries})")
        except requests.exceptions.RequestException as e:
            print(f"📡 API request error: {e}")
            if attempt == max_retries - 1:
                return None
        
        if attempt < max_retries - 1:
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return None

def search_movie_in_db(title, year):
    """Search for movie in local database"""
    db = load_movies_db()
    key = f"{title}_{year}".lower()
    
    if key in db:
        return db[key]  # Returns dict with qualities
    
    return None

# ---------- START ----------
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🎬 Movie name likho\n\nExample: Pathaan | Avatar | KGF"
    )

@bot.message_handler(commands=["add"])
def add_movie_command(message):
    """Admin command to add movie to database"""
    try:
        # Format: /add Movie Name | 2023 | 480p:msg_id | 720p:msg_id | 1080p:msg_id
        text = message.text.replace("/add ", "").strip()
        parts = text.split("|")
        
        if len(parts) < 3:
            bot.send_message(message.chat.id, "❌ Format: /add Movie Name | Year | 480p:msg_id | 720p:msg_id | 1080p:msg_id")
            return
        
        title = parts[0].strip()
        year = parts[1].strip()
        qualities = {}
        
        for i in range(2, len(parts)):
            q_parts = parts[i].strip().split(":")
            if len(q_parts) == 2:
                quality = q_parts[0].strip()
                msg_id = int(q_parts[1].strip())
                qualities[quality] = msg_id
        
        db = load_movies_db()
        key = f"{title}_{year}".lower()
        db[key] = {
            "title": title,
            "year": year,
            "qualities": qualities
        }
        save_movies_db(db)
        
        bot.send_message(message.chat.id, f"✅ Movie added: {title} ({year})")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error: {e}")

# ---------- SEARCH ----------
@bot.message_handler(func=lambda m: True)
def search_movie(message):
    query = message.text.strip().lower()

    # Search in local database first
    db = load_movies_db()
    results = []
    
    for key, movie_data in db.items():
        title = movie_data.get("title", "").lower()
        if query in title:
            results.append((key, movie_data))
    
    # If found in database, show quality options directly
    if results:
        markup = InlineKeyboardMarkup(row_width=1)
        
        for key, movie_data in results[:5]:  # Show up to 5 movies
            title = movie_data.get("title", "Unknown")
            year = movie_data.get("year", "N/A")
            qualities = movie_data.get("qualities", {})
            
            # Add each quality as a separate button
            for quality, msg_id in qualities.items():
                button_text = f"{title} ({year}) {quality}"
                markup.add(
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"download|{msg_id}|{quality}"
                    )
                )
        
        bot.send_message(
            message.chat.id,
            f"🎬 Available Downloads For '{query}' 👇",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

    # If not in database, search TMDB for info (with retry)
    api_url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query
    }
    
    data = api_request_with_retry(api_url, params)
    if data is None:
        bot.send_message(message.chat.id, "❌ Search API error, try again")
        return

    if not data.get("results"):
        markup = InlineKeyboardMarkup()
        
        # Google search button
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        markup.add(
            InlineKeyboardButton("🔍 Search on Google", url=google_search_url)
        )
        
        message_text = (
            "❌ Requested Movie is not Available Right Now :\n\n"
            "⚡ Just Type Movie Name with Year\n"
            "⚡ For Example \"Dhurandhar 2025\"\n"
            "⚡ Search in Google for Correct Spelling"
        )
        
        bot.send_message(
            message.chat.id,
            message_text,
            reply_markup=markup
        )
        return

    markup = InlineKeyboardMarkup(row_width=1)

    # How to download (top)
    markup.add(
        InlineKeyboardButton("📥 How To Download Movie", url=HOW_TO_DOWNLOAD_LINK)
    )

    for movie in data["results"][:8]:
        title = movie["title"]
        year = movie["release_date"][:4] if movie.get("release_date") else "N/A"

        markup.add(
            InlineKeyboardButton(
                f" {title} ({year})",
                callback_data=f"movie|{movie['id']}|{title}|{year}"
            )
        )

    bot.send_message(
        message.chat.id,
        f"🔍 I Found Some Results For Your Query 👉 {query}",
        parse_mode="Markdown",
        reply_markup=markup
    )

# ---------- MOVIE DETAILS ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("movie|"))
def movie_details(call):
    try:
        parts = call.data.split("|")
        movie_id = parts[1]
        movie_title = parts[2] if len(parts) > 2 else ""
        movie_year = parts[3] if len(parts) > 3 else "N/A"

        url = f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}"
        movie = requests.get(url).json()

        title = movie.get("title", movie_title)
        year = movie["release_date"][:4] if movie.get("release_date") else movie_year
        lang = movie.get("original_language", "").upper()

        # 16:9 backdrop image
        poster = (
            f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
            if movie.get("backdrop_path") else None
        )

        # Search for movie in private channel database
        movie_data = search_movie_in_db(title, year)
        
        markup = InlineKeyboardMarkup(row_width=1)

        if movie_data and movie_data.get("qualities"):
            # Movie found in channel - show quality options
            caption = f"🎬 {title} ({year})"
            
            # Sort qualities: 1080p, 720p, 480p
            quality_order = ["1080p", "720p", "480p"]
            available_qualities = {q: movie_data["qualities"][q] for q in quality_order if q in movie_data["qualities"]}
            
            for quality, msg_id in available_qualities.items():
                markup.add(
                    InlineKeyboardButton(f"{title} ({year}) {quality}", callback_data=f"download|{msg_id}|{quality}")
                )
            
            caption += f"\n📢 Join Us: {CHANNEL_USERNAME}"
            
            if poster:
                bot.send_photo(
                    call.message.chat.id,
                    poster,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    caption,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
        else:
            # Movie not found in channel - show website option
            search_query = urllib.parse.quote_plus(title)
            watch_url = WEBSITE_URL + search_query

            caption = (
                f"🎬 {title} ({year}) {lang}\n\n"
                f"Movie Watch on website \n\n"
                f"📢 Join Us: {CHANNEL_USERNAME}"
            )

            markup.add(
                InlineKeyboardButton("▶️ Watch Now", url=watch_url)
            )

            if poster:
                bot.send_photo(
                    call.message.chat.id,
                    poster,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    caption,
                    parse_mode="Markdown",
                    reply_markup=markup
                )

        try:
            bot.answer_callback_query(call.id)
        except:
            pass
    except Exception as e:
        print(f"Movie details error: {e}")
        bot.answer_callback_query(call.id, "❌ Error loading movie", show_alert=True)

# ---------- DOWNLOAD HANDLER ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("download|"))
def handle_download(call):
    try:
        parts = call.data.split("|")
        msg_id = int(parts[1])
        quality = parts[2] if len(parts) > 2 else ""
        
        # Forward the movie file to user
        bot.forward_message(
            chat_id=call.message.chat.id,
            from_chat_id=PRIVATE_CHANNEL_ID,
            message_id=msg_id
        )
        
        bot.answer_callback_query(call.id, f"✅ {quality} is downloading...", show_alert=False)
    except Exception as e:
        print(f"Download error: {e}")
        bot.answer_callback_query(call.id, "❌ Error downloading file", show_alert=True)

if __name__ == "__main__":
    print("🚀 Bot starting... (Auto-restart enabled)")
    restart_count = 0
    max_restart_count = 10
    
    while restart_count < max_restart_count:
        try:
            print(f"📡 Polling... (restart count: {restart_count})")
            bot.infinity_polling(timeout=15, long_polling_timeout=10, skip_pending=True)
        except KeyboardInterrupt:
            print("🛑 Bot stopped by user")
            break
        except Exception as e:
            restart_count += 1
            print(f"❌ Bot error: {e}")
            print(f"🔄 Auto-restarting in 10 seconds... (attempt {restart_count}/{max_restart_count})")
            time.sleep(10)
            continue
    
    print("⛔ Bot crashed - max restart attempts reached")
