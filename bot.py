import telebot
import requests
import urllib.parse
import json
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========= CONFIG =========
BOT_TOKEN = "7782831994:AAHwuJVaLNLwngWfjbQMH9NYaGtejQnWvOI"              # Telegram Bot Token
TMDB_API_KEY = "03985d11f17343d76561cebc240f5a32"           # TMDB API Key
PRIVATE_CHANNEL_ID = -1003304944058 # Private channel with movies (integer, e.g. -1001234567890)
MOVIES_DB_FILE = "movies_db.json"  # Local database for movie tracking
USERS_DB_FILE = "users_db.json"    # Local database for users
ADMIN_IDS = [6328021097]  # Your Telegram user ID(s) for admin commands, example: [12345678]

WEBSITE_URL = "https://www.filmyfiy.mov/site-1.html?to-search="
CHANNEL_USERNAME = "@filmyrajamovie"
HOW_TO_DOWNLOAD_LINK = "https://t.me/filmyrajamovie/5"
# ==========================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# -------------------------
# Storage helpers
# -------------------------
def load_json_file(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving {path}: {e}")
        return False

def load_movies_db():
    return load_json_file(MOVIES_DB_FILE)

def save_movies_db(data):
    return save_json_file(MOVIES_DB_FILE, data)

def load_users_db():
    return load_json_file(USERS_DB_FILE)

def save_users_db(data):
    return save_json_file(USERS_DB_FILE, data)

def register_user(user):
    """Register user (chat_id) for broadcast and stats"""
    try:
        if not user:
            return False
        users = load_users_db()
        uid = str(user.id)
        entry = users.get(uid, {})
        # store basic info to identify the user later
        entry.update({
            "id": user.id,
            "chat_id": user.id,
            "username": getattr(user, "username", None),
            "first_name": getattr(user, "first_name", None),
            "last_name": getattr(user, "last_name", None),
            "added_at": entry.get("added_at", int(time.time()))
        })
        users[uid] = entry
        save_users_db(users)
        return True
    except Exception as e:
        print(f"register_user error: {e}")
        return False

def get_users_list():
    users = load_users_db()
    # return list of chat_ids
    return [u.get("chat_id") for u in users.values() if u.get("chat_id")]

def get_users_count():
    users = load_users_db()
    return len(users)

# -------------------------
# Utility helpers
# -------------------------
def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def text_to_bold(text):
    """Convert text to Unicode bold"""
    # Bold Unicode mapping
    bold_map = {
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟',
        'g': '𝐠', 'h': '𝐡', 'i': '𝐢', 'j': '𝐣', 'k': '𝐤', 'l': '𝐥',
        'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫',
        's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱',
        'y': '𝐲', 'z': '𝐳',
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅',
        'G': '𝐆', 'H': '𝐇', 'I': '𝐈', 'J': '𝐉', 'K': '𝐊', 'L': '𝐋',
        'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑',
        'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗',
        'Y': '𝐘', 'Z': '𝐙',
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒',
        '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗'
    }
    return ''.join(bold_map.get(c, c) for c in text)

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

# -------------------------
# Movie filename parser
# -------------------------
def parse_movie_from_filename(filename):
    """Parse movie info from filename.
    Returns dict with title, year, qualities (list).
    """
    import re
    # Remove file extension
    name = filename.rsplit('.', 1)[0] if '.' in filename else filename

    # Extract ALL qualities (1080p, 720p, 480p, 360p, 240p)
    quality_matches = re.findall(r'(1080p|720p|480p|360p|240p)', name, re.IGNORECASE)
    qualities = sorted({q.lower() for q in quality_matches}, reverse=True)  # dedupe & sort

    if not qualities:
        # if no quality found, still try to parse title/year but return None to skip
        return None

    # Extract year (4 digits)
    year_match = re.search(r'(19\d{2}|20\d{2})', name)
    year = year_match.group(1) if year_match else None

    if not year:
        return None

    # Remove brackets, size, quality, year, codec info
    title = re.sub(r'\[.*?\]', '', name)  # Remove [SIZE]
    title = re.sub(r'(1080p|720p|480p|360p|240p|x264|x265|HEVC|HDTC|HDRip|BluRay|WEB|HDTV|BRRip)', '', title, flags=re.IGNORECASE)
    title = re.sub(r'(19\d{2}|20\d{2})', '', title)  # Remove year
    title = re.sub(r'[_\-\.]+', ' ', title)  # Replace separators with space
    title = title.strip()

    if not title or len(title) < 2:
        return None

    return {
        "title": title,
        "year": year,
        "qualities": qualities  # e.g. ['1080p','720p']
    }

# ---------- START ----------
@bot.message_handler(commands=["start"])
def start(message):
    register_user(message.from_user)
    msg = text_to_bold("🎬 Movie name likho\n\nExample: Pathaan | Avatar | KGF")
    bot.send_message(
        message.chat.id,
        msg
    )

@bot.message_handler(commands=["help"])
def help_cmd(message):
    register_user(message.from_user)
    help_text = (
        "🛠 Bot Commands:\n\n"
        "/start - Start the bot\n"
        "/help - Show this help\n\n"
        "Admin-only commands:\n"
        "/stats - Show number of users\n"
        "/broadcast <message> - Send message to all users\n"
        "/add <Title> | <Year> | 1080p:msg_id | 720p:msg_id - Manually add movie\n"
        "/update <Title> | <Year> | 1080p:new_id | 720p:new_id - Update message ids\n"
    )
    bot.send_message(message.chat.id, help_text)

# ---------- CHANNEL AUTO-ADD ----------
@bot.channel_post_handler(content_types=['video', 'document'])
def handle_channel_video(message):
    """Auto-add movies from private channel with auto-caption.
       Supports filenames that contain multiple quality tags (like "Movie 2023 1080p 720p ...").
    """
    try:
        # Only process in private channel
        if message.chat.id != PRIVATE_CHANNEL_ID:
            return

        # Get file name
        filename = None
        if getattr(message, "video", None) and getattr(message.video, "file_name", None):
            filename = message.video.file_name
        elif getattr(message, "document", None) and getattr(message.document, "file_name", None):
            filename = message.document.file_name

        if not filename:
            return

        # Parse movie info from filename
        movie_info = parse_movie_from_filename(filename)
        if not movie_info:
            return

        title = movie_info["title"]
        year = movie_info["year"]
        qualities = movie_info["qualities"]  # list
        msg_id = message.message_id

        # Load database
        db = load_movies_db()
        key = f"{title}_{year}".lower()

        if key not in db:
            db[key] = {
                "title": title,
                "year": year,
                "qualities": {}
            }

        # For each parsed quality, save the message id.
        # Usually each forwarded file will have one quality, but if filename contains multiple, assign same msg_id.
        for quality in qualities:
            # Save as lower-case key (consistent)
            db[key]["qualities"][quality] = msg_id

        save_movies_db(db)

        # Generate and add auto-caption
        caption = text_to_bold(f"🎬 𝐌𝐎𝐕𝐈𝐄 : {title}\n📅 𝐘𝐄𝐀𝐑 : {year}\n🎞 𝐐𝐔𝐀𝐋𝐈𝐓𝐈𝐄𝐒 : {', '.join(qualities)}")

        try:
            bot.edit_message_caption(
                chat_id=PRIVATE_CHANNEL_ID,
                message_id=msg_id,
                caption=caption
            )
        except Exception:
            # ignore if we can't edit (maybe not a media with caption)
            pass

        print(f"✅ Auto-added: {title} ({year}) - {qualities}")

    except Exception as e:
        print(f"Channel auto-add error: {e}")

# ---------- ADMIN: add / update (already present but ensured consistency) ----------
@bot.message_handler(commands=["add"])
def add_movie_command(message):
    register_user(message.from_user)
    """Admin command to add movie to database"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Only admin can use this command")
        return

    try:
        # Format: /add Movie Name | 2023 | 1080p:msg_id | 720p:msg_id
        text = message.text.replace("/add", "", 1).strip()
        parts = [p.strip() for p in text.split("|")]

        if len(parts) < 3:
            msg = text_to_bold("❌ Format: /add Movie Name | Year | 1080p:msg_id | 720p:msg_id")
            bot.send_message(message.chat.id, msg)
            return

        title = parts[0]
        year = parts[1]
        qualities = {}

        for i in range(2, len(parts)):
            q_parts = parts[i].strip().split(":")
            if len(q_parts) == 2:
                quality = q_parts[0].strip().lower()
                try:
                    msg_id = int(q_parts[1].strip())
                    qualities[quality] = msg_id
                except:
                    pass

        if not qualities:
            msg = text_to_bold("❌ No valid qualities provided")
            bot.send_message(message.chat.id, msg)
            return

        db = load_movies_db()
        key = f"{title}_{year}".lower()
        db[key] = {
            "title": title,
            "year": year,
            "qualities": qualities
        }
        save_movies_db(db)

        msg = text_to_bold(f"✅ 𝐌𝐎𝐕𝐈𝐄 𝐀𝐃𝐃𝐄𝐃 : {title} ({year})")
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        msg = text_to_bold(f"❌ Error: {e}")
        bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=["update"])
def update_movie_command(message):
    register_user(message.from_user)
    """Admin command to update movie message IDs"""
    if not is_admin(message.from_user.id):
        msg = text_to_bold("❌ Only admin can use this command")
        bot.send_message(message.chat.id, msg)
        return

    try:
        # Format: /update Movie Name | Year | 1080p:new_id | 720p:new_id
        text = message.text.replace("/update", "", 1).strip()
        parts = [p.strip() for p in text.split("|")]

        if len(parts) < 3:
            msg = text_to_bold("❌ Format: /update Movie Name | Year | 1080p:new_id | 720p:new_id")
            bot.send_message(message.chat.id, msg)
            return

        title = parts[0]
        year = parts[1]
        qualities = {}

        for i in range(2, len(parts)):
            q_parts = parts[i].strip().split(":")
            if len(q_parts) == 2:
                quality = q_parts[0].strip().lower()
                try:
                    msg_id = int(q_parts[1].strip())
                    qualities[quality] = msg_id
                except:
                    pass

        if not qualities:
            msg = text_to_bold("❌ No valid qualities provided")
            bot.send_message(message.chat.id, msg)
            return

        db = load_movies_db()
        key = f"{title}_{year}".lower()

        if key not in db:
            msg = text_to_bold(f"❌ Movie not found: {title} ({year})")
            bot.send_message(message.chat.id, msg)
            return

        # merge existing qualities with new values
        db[key]["qualities"].update(qualities)
        save_movies_db(db)

        msg = text_to_bold(f"✅ 𝐌𝐎𝐕𝐈𝐄 𝐔𝐏𝐃𝐀𝐓𝐄𝐃 : {title} ({year})")
        bot.send_message(message.chat.id, msg)
    except Exception as e:
        msg = text_to_bold(f"❌ Error: {e}")
        bot.send_message(message.chat.id, msg)

# ---------- ADMIN: stats & broadcast ----------
@bot.message_handler(commands=["stats", "users"])
def stats_command(message):
    register_user(message.from_user)
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Only admin can use this command")
        return
    count = get_users_count()
    users = load_users_db()
    lines = [f"Total users: {count}", ""]
    # show up to first 20 users
    i = 0
    for uid, info in users.items():
        if i >= 20:
            break
        lines.append(f"- {info.get('first_name','')} @{info.get('username','')} ({info.get('id')})")
        i += 1
    if count > 20:
        lines.append(f"... and {count-20} more")
    bot.send_message(message.chat.id, "\n".join(lines))

@bot.message_handler(commands=["broadcast"])
def broadcast_command(message):
    register_user(message.from_user)
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Only admin can use this command")
        return

    # Format: /broadcast Your message here...
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        bot.send_message(message.chat.id, "❌ Usage: /broadcast <message to send>")
        return

    users = load_users_db()
    if not users:
        bot.send_message(message.chat.id, "❌ No users to broadcast to.")
        return

    sent = 0
    failed = 0
    bot.send_message(message.chat.id, f"📢 Broadcasting to {len(users)} users. Starting...")
    for uid, info in users.items():
        chat_id = info.get("chat_id")
        if not chat_id:
            failed += 1
            continue
        try:
            bot.send_message(chat_id, text)
            sent += 1
            # small sleep to avoid flood limits
            time.sleep(0.05)
        except Exception as e:
            print(f"Broadcast to {chat_id} failed: {e}")
            failed += 1
            # continue broadcasting to others

    bot.send_message(message.chat.id, f"✅ Broadcast finished. Sent: {sent}, Failed: {failed}")

# ---------- SEARCH ----------
@bot.message_handler(func=lambda m: True)
def search_movie(message):
    # register user for broadcasts/stats
    register_user(message.from_user)

    raw_query = message.text.strip().lower()
    if not raw_query:
        return

    # Detect quality token (if user wrote "Movie 720p" or "Movie 1080p")
    desired_quality = None
    for q in ["1080p", "720p", "480p", "360p", "240p"]:
        if q in raw_query:
            desired_quality = q
            # remove quality token from query for searching titles
            raw_query = raw_query.replace(q, "").strip()
            break

    query = raw_query

    # Search in local database first
    db = load_movies_db()
    results = []

    for key, movie_data in db.items():
        title = movie_data.get("title", "").lower()
        year = movie_data.get("year", "")
        # match if query in title or query equals title or includes year in query
        if query in title:
            # if desired_quality specified, ensure movie has that quality
            if desired_quality:
                if desired_quality in movie_data.get("qualities", {}):
                    results.append((key, movie_data))
            else:
                results.append((key, movie_data))

    # If found in database, show quality options directly
    if results:
        markup = InlineKeyboardMarkup(row_width=1)

        for key, movie_data in results[:10]:  # show up to 10 movies
            title = movie_data.get("title", "Unknown")
            year = movie_data.get("year", "N/A")
            qualities = movie_data.get("qualities", {})

            # Sort qualities by preferred order
            quality_order = ["1080p", "720p", "480p", "360p", "240p"]
            available_qualities = [q for q in quality_order if q in qualities]

            # If user asked for desired_quality but somehow not present, skip
            if desired_quality and desired_quality not in available_qualities:
                continue

            # Add each quality as a separate button
            for quality in available_qualities:
                msg_id = qualities[quality]
                button_text = f"{title} ({year}) {quality}"
                markup.add(
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"download|{msg_id}|{quality}"
                    )
                )

        if markup.keyboard:
            msg = text_to_bold(f"🎬 Available Downloads For '{query or message.text.strip()}' 👇")
            bot.send_message(
                message.chat.id,
                msg,
                reply_markup=markup
            )
            return

    # If not in database (or after filtering by desired_quality), search TMDB for info (with retry)
    api_url = "https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query or message.text.strip()
    }

    data = api_request_with_retry(api_url, params)
    if data is None:
        bot.send_message(message.chat.id, "❌ Search API error, try again")
        return

    if not data.get("results"):
        markup = InlineKeyboardMarkup()

        # Google search button
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(message.text.strip())}"
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
        title = movie.get("title") or movie.get("original_title")
        year = movie.get("release_date")[:4] if movie.get("release_date") else "N/A"

        # Attach movie id & title & year in callback data (escape pipe by replacing)
        safe_title = title.replace("|", "¦") if title else ""
        markup.add(
            InlineKeyboardButton(
                f" {title} ({year})",
                callback_data=f"movie|{movie['id']}|{safe_title}|{year}"
            )
        )

    msg = text_to_bold(f"🔍 I Found Some Results For Your Query 👉 {message.text.strip()}")
    bot.send_message(
        message.chat.id,
        msg,
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
        movie_data = None
        
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
        
        # Copy the movie file to user (without channel attribution)
        bot.copy_message(
            chat_id=call.message.chat.id,
            from_chat_id=PRIVATE_CHANNEL_ID,
            message_id=msg_id
        )
        
        bot.answer_callback_query(call.id, f"✅ {quality} downloading...", show_alert=False)
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
