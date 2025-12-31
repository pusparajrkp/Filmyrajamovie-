import telebot
import requests
import json
import os
import urllib.parse
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CONFIG =================

BOT_TOKEN = "7782831994:AAHwuJVaLNLwngWfjbQMH9NYaGtejQnWvOI"
TMDB_API_KEY = "03985d11f17343d76561cebc240f5a32"

PRIVATE_CHANNEL_ID = -1003304944058 
CHANNEL_USERNAME = ""   # always lowercase
WATCH_WEBSITE = "https://www.filmyfiy.mov/site-1.html?to-search="

ADMIN_IDS = [6328021097]

USERS_FILE = "users.json"
RESULTS_PER_PAGE = 8

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ================= UTILS =================

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ================= START (PHOTO + BUTTONS) =================

@bot.message_handler(commands=["start"])
def start(m):
    users = load_json(USERS_FILE, [])
    if m.from_user.id not in users:
        users.append(m.from_user.id)
        save_json(USERS_FILE, users)

    caption = (
        f"<b>ʜᴇʟʟᴏ, {m.from_user.first_name}</b>\n\n"
        "ᴍʏ ɴᴀᴍᴇ ɪꜱ ꜰɪʟᴍʏ ʀᴀɴɪ ♡\n"
        "ɪ ᴄᴀɴ ᴘʀᴏᴠɪᴅᴇ ᴍᴏᴠɪᴇꜱ & ꜱᴇʀɪᴇꜱ\n"
        "ᴊᴜꜱᴛ ᴀᴅᴅ ᴍᴇ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ɢʀᴏᴜᴘ\n"
        "ᴀɴᴅ ᴇɴᴊᴏʏ 😍"
    )

    kb = InlineKeyboardMarkup(row_width=2)

    kb.add(
        InlineKeyboardButton(
            "Add Me to Group",
            url="https://t.me/filmyranibot?startgroup=true"
        )
    )

    kb.add(
        InlineKeyboardButton("Backup Channel", url="https://t.me/filmyrajamovie"),
        InlineKeyboardButton("Bot Channel", url="https://t.me/botchannel")
    )

    kb.add(
        InlineKeyboardButton("Movie group 1", url="https://t.me/+UacqMrCJqeZjMTY1"),
        InlineKeyboardButton("Movie group 2", url="https://t.me/+CoqbU5nFeCU4ZDFl")
    )

    kb.add(
        InlineKeyboardButton(
            "Share Me",
            url="https://t.me/share/url?url=https://t.me/YourBotUsername"
        )
    )

    bot.send_photo(
        m.chat.id,
        photo=open("start.jpg", "rb"),
        caption=caption,
        reply_markup=kb
    )

# ================= ADMIN STATS =================

@bot.message_handler(func=lambda m: m.text and m.text.lower() == "admin")
def admin_stats(m):
    if m.from_user.id not in ADMIN_IDS:
        return

    users = load_json(USERS_FILE, [])
    bot.send_message(
        m.chat.id,
        "ʏᴏᴜʀ ʙᴏᴛ ꜱᴛᴀᴛꜱ 📊\n\n"
        f"ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ : {len(users)}"
    )

# ================= SEARCH =================

@bot.message_handler(func=lambda m: m.text and not m.text.startswith("/"))
def search(m):
    query = m.text.strip()

    data = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": TMDB_API_KEY, "query": query}
    ).json()

    results = [x for x in data.get("results", []) if x.get("release_date")]

    if not results:
            not_found_text = (
                "<b>ʀᴇǫᴜᴇꜱᴛᴇᴅ ᴍᴏᴠɪᴇ / ꜱᴇʀɪᴇꜱ ɪꜱ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ʀɪɢʜᴛ ɴᴏᴡ :</b>\n\n"
                "🔴 <i>ᴊᴜꜱᴛ ᴛʏᴘᴇ ᴍᴏᴠɪᴇ ɴᴀᴍᴇ ᴡɪᴛʜ ʏᴇᴀʀ</i>\n"
                "🔴 <i>ꜰᴏʀ ᴇxᴀᴍᴘʟᴇ : \"Dhurandhar 2025\"</i>\n"
                "🔴 <i>ꜱᴇᴀʀᴄʜ ɪɴ ɢᴏᴏɢʟᴇ ꜰᴏʀ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ</i>"
            )

            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton(
                    "🔍 Google Search",
                    url=f"https://www.google.com/search?q={query.replace(' ', '+')}"
                )
            )

            bot.send_message(
                m.chat.id,
                not_found_text,
                reply_markup=kb,
                parse_mode="HTML",
                reply_to_message_id=m.message_id
            )
            return

    send_page(m.chat.id, m.from_user.first_name, query, results, 0)

def send_page(chat_id, username, query, results, page):
    start = page * RESULTS_PER_PAGE
    end = start + RESULTS_PER_PAGE
    sliced = results[start:end]

    total_pages = (len(results) - 1) // RESULTS_PER_PAGE + 1
    kb = InlineKeyboardMarkup(row_width=1)

    for mv in sliced:
        title = mv["title"]
        year = mv["release_date"][:4]
        kb.add(
            InlineKeyboardButton(
                f"{title} ({year})",
                callback_data=f"movie|{title}|{year}"
            )
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ ᴘʀᴇᴠ", callback_data=f"page|{query}|{page-1}"))

    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="noop"))

    if end < len(results):
        nav.append(InlineKeyboardButton("ɴᴇxᴛ ➡️", callback_data=f"page|{query}|{page+1}"))

    kb.row(*nav)

    bot.send_message(
        chat_id,
        f"ʜᴇʏ, {username} 👋\n\n"
        f"ɪ ꜰᴏᴜɴᴅ ꜱᴏᴍᴇ ʀᴇꜱᴜʟᴛꜱ ꜰᴏʀ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ɴᴀᴍᴇ 👇",
        reply_markup=kb
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("page|"))
def change_page(c):
    _, query, page = c.data.split("|")
    page = int(page)

    data = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": TMDB_API_KEY, "query": query}
    ).json()

    results = [x for x in data.get("results", []) if x.get("release_date")]

    bot.delete_message(c.message.chat.id, c.message.message_id)
    send_page(c.message.chat.id, c.from_user.first_name, query, results, page)
    bot.answer_callback_query(c.id)

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def noop(c):
    bot.answer_callback_query(c.id)

# ================= MOVIE DETAILS =================

@bot.callback_query_handler(func=lambda c: c.data.startswith("movie|"))
def movie_details(c):
    _, title, year = c.data.split("|")

    info = requests.get(
        "https://api.themoviedb.org/3/search/movie",
        params={"api_key": TMDB_API_KEY, "query": title}
    ).json()["results"][0]

    poster = f"https://image.tmdb.org/t/p/w500{info['poster_path']}" if info.get("poster_path") else None

    caption = (
    f"ᴍᴏᴠɪᴇ : {title}\n"
    f"ʏᴇᴀʀ : {year}\n"
    f"ʀᴀᴛɪɴɢ : {info.get('vote_average','N/A')} ⭐\n"
    f"ɢᴇɴʀᴇ : ᴀᴄᴛɪᴏɴ, ᴛʜʀɪʟʟᴇʀ\n\n"
    f"ᴊᴏɪɴ ᴜꜱ : {CHANNEL_USERNAME.lower()}\n\n"
    )

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            "▶️ ᴡᴀᴛᴄʜ ɴᴏᴡ",
            url=WATCH_WEBSITE + urllib.parse.quote_plus(title)
        )
    )

    if poster:
        bot.send_photo(
            c.message.chat.id,
            poster,
            caption=caption,
            reply_markup=kb
        )
    else:
        bot.send_message(
            c.message.chat.id,
            caption,
            reply_markup=kb
        )

    bot.answer_callback_query(c.id)
    
# ================= KEEP ALIVE =================
from app import keep_alive
keep_alive()

# ================= RUN =================
bot.infinity_polling()
