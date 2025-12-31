import telebot
import requests
import urllib.parse
import json
import os
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========= CONFIG =========
BOT_TOKEN = "0"              # Telegram Bot Token
TMDB_API_KEY = "03985d11f17343d76561cebc240f5a32"           # TMDB API Key
PRIVATE_CHANNEL_ID = None  # Private channel with movies (integer, e.g. -1001234567890)
MOVIES_DB_FILE = "movies_db.json"  # Local database for movie tracking
USERS_DB_FILE = "users_db.json"    # Local database for users
ADMIN_IDS = []  # Your Telegram user ID(s) for admin commands, example: [12345678]

WEBSITE_URL = "https://www.filmyfiy.mov/site-1.html?to-search="
CHANNEL_USERNAME = "@filmyrajamovie"
HOW_TO_DOWNLOAD_LINK = "https://t.me/filmyrajamovie/5"
RESULTS_PER_PAGE = 8
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
    """Convert text to Unicode bold (keeps emoji and other chars unchanged)"""
    # Minimal conversion for ASCII letters -> mathematical bold (approx)
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

# -------------------------
# SEARCH / PAGING HELPERS
# -------------------------
def send_search_page(chat_id, username, query, results, page):
    """Sends a paged list of results (RESULTS_PER_PAGE per page) with nav buttons."""
    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    sliced = results[start:end]

    total_pages = (len(results) - 1) // RESULTS_PER_PAGE + 1 if results else 1

    kb = InlineKeyboardMarkup(row_width=1)

    # top how-to button
    kb.add(InlineKeyboardButton("📥 How To Download Movie", url=HOW_TO_DOWNLOAD_LINK))

    for mv in sliced:
        title = mv.get("title") or mv.get("original_title") or "Unknown"
        year_text = mv.get("release_date")[:4] if mv.get("release_date") else "N/A"
        safe_title = title.replace("|", "¦")
        # movie button opens details
        kb.add(InlineKeyboardButton(f"{title} ({year_text})", callback_data=f"movie|{mv['id']}|{safe_title}|{year_text}"))

    # nav row
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"page|{query}|{page-1}"))
    # center shows page number clearly as requested (Page 1 Page 2 style)
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))
    if end < len(results):
        nav.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"page|{query}|{page+1}"))
    kb.row(*nav)

    # Send greeting + header (keeps same style as other messages)
    # The user requested a visible greeting like: "Hey username i found some results"
    try:
        bot.send_message(chat_id, f"ʜᴇʏ, {username} 👋")
    except Exception:
        pass

    header = text_to_bold("🔍 𝐈 𝐅𝐨𝐮𝐧𝐝 𝐒𝐨𝐦𝐞 𝐑𝐞𝐬𝐮𝐥𝐭𝐬 𝐅𝐨𝐫 𝐘𝐨𝐮𝐫 𝐐𝐮𝐞𝐫𝐲 👉 ") + f"{query}"
    bot.send_message(chat_id, header, reply_markup=kb)

# -------------------------
# BOT HANDLERS
# -------------------------
BOT_USERNAME = "@filmyranibot"

@bot.message_handler(commands=["start"])
def start(m):
    # optional: register user in your json/db
    # register_user(m.from_user)

    caption = (
        f"<b>HELLO, {m.from_user.first_name}</b>\n\n"
        "MY NAME IS FILMY RANI ♡\n"
        "I CAN PROVIDE MOVIES & SERIES\n        "
        "JUST ADD ME ADMIN IN YOUR GROUP\n\n"
        "AND ENJOY 😍"
    )

    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton(
            "Add Me to Group",
            url="https://t.me/FilmyRajaBot?startgroup=true"
        )
    )

    kb.add(
        InlineKeyboardButton("Backup Channel", url="https://t.me/filmyrajamovie"),
        InlineKeyboardButton("Bot Channel", url="https://t.me/filmyranibot")
    )

    kb.add(
        InlineKeyboardButton("Movie group 1", url="https://t.me/+UacqMrCJqeZjMTY1"),
        InlineKeyboardButton("Movie group 2", url="https://t.me/+CoqbU5nFeCU4ZDFl")
    )

    kb.add(
        InlineKeyboardButton(
            "Share Me",
            url="https://t.me/share/url?url=https://t.me/filmyrajabot"
        )
    )

    # send photo with inline keyboard
    if os.path.exists("start.jpg"):
        with open("start.jpg", "rb") as photo:
            bot.send_photo(m.chat.id,
                           photo=photo,
                           caption=caption,
                           reply_markup=kb,
                           parse_mode="HTML")
    else:
        bot.send_message(m.chat.id, caption, reply_markup=kb, parse_mode="HTML")

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
        if PRIVATE_CHANNEL_ID is None or message.chat.id != PRIVATE_CHANNEL_ID:
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

        # Generate and add auto-caption (use bot's own caption for private channel items)
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

    raw_query = message.text.strip()
    if not raw_query:
        return

    query_for_search = raw_query  # keep original casing for display
    query = raw_query.strip()

    # Detect quality token (if user wrote "Movie 720p" or "Movie 1080p")
    desired_quality = None
    lquery = query.lower()
    for q in ["1080p", "720p", "480p", "360p", "240p"]:
        if q in lquery:
            desired_quality = q
            # remove quality token from query for searching titles
            lquery = lquery.replace(q, "").strip()
            query = lquery
            break

    # First search local DB (exact-ish)
    db = load_movies_db()
    db_results = []
    for key, movie_data in db.items():
        title = movie_data.get("title", "").lower()
        year = movie_data.get("year", "")
        if query.lower() in title:
            if desired_quality:
                if desired_quality in movie_data.get("qualities", {}):
                    db_results.append((key, movie_data))
            else:
                db_results.append((key, movie_data))

    # If there are local DB results, show them first as immediate download options
    if db_results:
        markup = InlineKeyboardMarkup(row_width=1)
        for key, movie_data in db_results[:50]:  # show up to 50 matches from DB
            title = movie_data.get("title", "Unknown")
                        year = movie_data.get("year", "N/A")
            qualities = movie_data.get("qualities", {})

            # Add a header/button for the movie (opens details which will show quality buttons)
            safe_title = title.replace("|", "¦")
            markup.add(InlineKeyboardButton(f"{title} ({year})", callback_data=f"movie_local|{safe_title}|{year}"))

            # Add quality buttons directly under header for quick download (if many, keep reasonable)
            quality_order = ["1080p", "720p", "480p", "360p", "240p"]
            for q in quality_order:
                if q in qualities:
                    msg_id = qualities[q]
                    markup.add(InlineKeyboardButton(f"{title} ({year}) {q}", callback_data=f"download|{msg_id}|{q}"))

        # Add greeting + header (explicit phrasing requested by user)
        try:
            bot.send_message(message.chat.id, f"ʜᴇʏ, {message.from_user.first_name} 👋")
        except Exception:
            pass
        header = text_to_bold("🔍 𝐈 𝐅𝐨𝐮𝐧𝐝 𝐒𝐨𝐦𝐞 𝐑𝐞𝐬𝐮𝐥𝐭𝐬 𝐅𝐨𝐫 𝐘𝐨𝐮𝐫 𝐐𝐮𝐞𝐫𝐲 👉 ") + f"{query_for_search}"
        bot.send_message(message.chat.id, header, reply_markup=markup)
        return

    # If not found locally or no suitable qualities, search TMDB
    api_url = "https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query}
    data = api_request_with_retry(api_url, params)
    if data is None:
        bot.send_message(message.chat.id, "❌ Search API error, try again")
        return

    results = [x for x in data.get("results", []) if x.get("release_date")]
    if not results:
        markup = InlineKeyboardMarkup()
        google_search_url = f"https://www.google.com/search?q={urllib.parse.quote(message.text.strip())}"
        markup.add(InlineKeyboardButton("🔍 Search on Google", url=google_search_url))

        try:
            bot.send_message(message.chat.id, f"ʜᴇʏ, {message.from_user.first_name} 👋")
        except Exception:
            pass

        message_text = (
            "❌ Requested Movie is not Available Right Now :\n\n"
            "⚡ Just Type Movie Name with Year\n"
            "⚡ For Example \"Dhurandhar 2025\"\n"
            "⚡ Search in Google for Correct Spelling"
        )
        bot.send_message(message.chat.id, message_text, reply_markup=markup)
        return

    # Send greeting + header then paged results
    try:
        bot.send_message(message.chat.id, f"ʜᴇʏ, {message.from_user.first_name} 👋")
    except Exception:
        pass
    send_search_page(message.chat.id, message.from_user.first_name, query_for_search, results, 0)

# ---------- PAGE NAV HANDLER ----------
@bot.callback_query_handler(func=lambda c: c.data.startswith("page|"))
def change_page(c):
    try:
        _, query, page = c.data.split("|", 2)
        page = int(page)
        api_url = "https://api.themoviedb.org/3/search/movie"
        params = {"api_key": TMDB_API_KEY, "query": query}
        data = api_request_with_retry(api_url, params)
        results = [x for x in data.get("results", []) if x.get("release_date")] if data else []
        # delete previous header message (optional), then send new page results
        try:
            bot.delete_message(c.message.chat.id, c.message.message_id)
        except Exception:
            pass
        send_search_page(c.message.chat.id, c.from_user.first_name, query, results, page)
        bot.answer_callback_query(c.id)
    except Exception as e:
        print(f"change_page error: {e}")
        try:
            bot.answer_callback_query(c.id, "❌ Error changing page", show_alert=True)
        except:
            pass

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def noop(c):
    bot.answer_callback_query(c.id)

# ---------- MOVIE DETAILS ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("movie|") or call.data.startswith("movie_local|"))
def movie_details(call):
    try:
        # Try to show a friendly header (user requested that "Hey username i found some results" be visible)
        try:
            bot.send_message(call.message.chat.id, f"ʜᴇʏ, {call.from_user.first_name} 👋")
        except Exception:
            pass

        if call.data.startswith("movie_local|"):
            # Called from local DB quick button
            _, safe_title, year = call.data.split("|", 2)
            title = safe_title.replace("¦", "|")
            # try to fetch TMDB info by searching title + year
            params = {"api_key": TMDB_API_KEY, "query": f"{title} {year}"}
            data = api_request_with_retry("https://api.themoviedb.org/3/search/movie", params)
            movie = data.get("results", [None])[0] if data and data.get("results") else None
            movie_id = movie.get("id") if movie else None
        else:
            parts = call.data.split("|")
            movie_id = parts[1]
            movie = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}", params={"api_key": TMDB_API_KEY}).json() if movie_id else None

        # If we have movie data from TMDB, extract details
        if movie:
            title = movie.get("title") or movie.get("original_title") or ""
            year = movie.get("release_date")[:4] if movie.get("release_date") else ""
            lang = (movie.get("original_language") or "").upper()
            genres = movie.get("genres") or []
            genre_names = ", ".join([g.get("name", "") for g in genres]) if genres else "N/A"

            # Poster/backdrop selection - use the largest available for a full poster appearance
            poster = None
            if movie.get("backdrop_path"):
                poster = f"https://image.tmdb.org/t/p/w1280{movie['backdrop_path']}"
            elif movie.get("poster_path"):
                poster = f"https://image.tmdb.org/t/p/w780{movie['poster_path']}"

            # Check if movie exists in local DB
            movie_data = None
            try:
                movie_data = search_movie_in_db(title, year)
            except Exception:
                movie_data = None

            channel_url = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}"

            # Prepare caption details (consistent style with other captions in this script)
            if movie_data and movie_data.get("qualities"):
                # Movie available in private channel -> show our own caption style (not TMDB caption),
                # show full poster and quality buttons that copy message from private channel
                quality_order = ["1080p", "720p", "480p", "360p", "240p"]
                available_qualities = {q: movie_data["qualities"][q] for q in quality_order if q in movie_data["qualities"]}

                kb = InlineKeyboardMarkup(row_width=1)

                # Blue details / channel button
                details_parts = [f"{title} ({year})"]
                if available_qualities:
                    details_parts.append(" ".join(list(available_qualities.keys())))
                details_text = " • ".join(details_parts)
                # keep details button opening the channel (Join us)
                kb.add(InlineKeyboardButton(details_text, url=channel_url))

                # Quality download buttons
                for quality, msg_id in available_qualities.items():
                    kb.add(InlineKeyboardButton(f"{title} ({year}) {quality}", callback_data=f"download|{msg_id}|{quality}"))

                kb.add(InlineKeyboardButton("Join Us", url=channel_url))

                # Use our own caption format (as requested)
                caption = text_to_bold(f"🎬 𝐌𝐎𝐕𝐈𝐄 : {title}\n📅 𝐘𝐄𝐀𝐑 : {year}\n🎞 𝐐𝐔𝐀𝐋𝐈𝐓𝐈𝐄𝐒 : {', '.join(list(available_qualities.keys()))}\n\n📢 Join Us : {CHANNEL_USERNAME}")

                if poster:
                    bot.send_photo(call.message.chat.id, poster, caption=caption, reply_markup=kb)
                else:
                    bot.send_message(call.message.chat.id, caption, reply_markup=kb)
            else:
                # Movie not available in private channel -> TMDB style with Watch Now button
                kb = InlineKeyboardMarkup(row_width=1)

                # Details button that opens your channel (blue)
                details_text = f"{title} ({year}) • {genre_names}" if genre_names else f"{title} ({year})"
                kb.add(InlineKeyboardButton(details_text, url=channel_url))

                # Watch now button to website (encoded title)
                watch_url = WEBSITE_URL + urllib.parse.quote_plus(title)
                kb.add(InlineKeyboardButton("▶️ Watch Now", url=watch_url))

                kb.add(InlineKeyboardButton("Join Channel", url=channel_url))

                # TMDB style caption but keep the script's styling requirements
                caption = (
                    f"🎬 {title} ({year})\n\n"
                    f"LANGUAGE : {lang}\n"
                    f"RATING : {movie.get('vote_average','N/A')} ⭐\n"
                    f"GENRE : {genre_names}\n\n"
                    f"Movie Watch on website\n\n"
                    f"📢 Join Us : {CHANNEL_USERNAME}"
                )

                if poster:
                    bot.send_photo(call.message.chat.id, poster, caption=caption, reply_markup=kb)
                else:
                    bot.send_message(call.message.chat.id, caption, reply_markup=kb)
        else:
            bot.answer_callback_query(call.id, "❌ Movie info not found", show_alert=True)

        try:
            bot.answer_callback_query(call.id)
        except:
            pass

    except Exception as e:
        print(f"Movie details error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Error loading movie", show_alert=True)
        except:
            pass

# ---------- DOWNLOAD HANDLER ----------
@bot.callback_query_handler(func=lambda call: call.data.startswith("download|"))
def handle_download(call):
    try:
        parts = call.data.split("|")
        msg_id = int(parts[1])
        quality = parts[2] if len(parts) > 2 else ""

        if PRIVATE_CHANNEL_ID is None:
            bot.answer_callback_query(call.id, "❌ Server not configured (PRIVATE_CHANNEL_ID)", show_alert=True)
            return

        # Copy the movie file to user (without channel attribution)
        bot.copy_message(
            chat_id=call.message.chat.id,
            from_chat_id=PRIVATE_CHANNEL_ID,
            message_id=msg_id
        )

        bot.answer_callback_query(call.id, f"✅ {quality} downloading...", show_alert=False)
    except Exception as e:
        print(f"Download error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Error downloading file", show_alert=True)
        except:
            pass

# ---------- Helper: search movie in DB ----------
def search_movie_in_db(title, year):
    """Search for movie in local database"""
    db = load_movies_db()
    key = f"{title}_{year}".lower()

    if key in db:
        return db[key]  # Returns dict with qualities

    # Try fuzzy matching by title only (ignore punctuation and case)
    for k, v in db.items():
        if v.get("title", "").lower() == title.lower() and str(v.get("year", "")) == str(year):
            return v
    return None

# ---------- RUN ----------
if __name__ == "__main__":
    print("✅ Bot started")

    restart_count = 0
    max_restart_count = 10

    while restart_count < max_restart_count:
        try:
            print(f"🚀 Polling... (restart count: {restart_count})")
            bot.infinity_polling(
                timeout=15,
                long_polling_timeout=10,
                skip_pending=True
            )
        except KeyboardInterrupt:
            print("🛑 Bot stopped by user")
            break
        except Exception as e:
            restart_count += 1
            print(f"❌ Bot error: {e}")
            print(f"🔄 Auto-restarting in 10 seconds... ({restart_count}/{max_restart_count})")
            time.sleep(10)
