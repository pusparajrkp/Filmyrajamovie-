import telebot
import requests
import os
from urllib.parse import quote_plus
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8375545383:AAEMnp48xXivpUqkcOa1t3tXuDfFxWqe03A"
TMDB_API_KEY = os.getenv("TMDB_API_KEY") or "03985d11f17343d76561cebc240f5a32"

MOVIE_WEBSITE = "https://www.filmyfiy.mov/site-1.html?to-search="  # <-- apni website
BOT_USERNAME = "@filmyrajabot"  # optional

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_MOVIE_URL = "https://api.themoviedb.org/3/movie/"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"


# ========= START =========
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "🎬 <b>Movie Search Bot</b>\n\n"
        "👉 Kisi bhi movie ka <b>naam likho</b>\n"
        "👉 Multiple movie options milenge\n"
        "👉 Watch Now button se website open hogi"
    )


# ========= SEARCH MOVIE =========
@bot.message_handler(func=lambda m: True)
def search_movie(message):
    query = message.text.strip()

    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": False,
        "language": "en-US",
        "page": 1
    }

    r = requests.get(TMDB_SEARCH_URL, params=params)
    data = r.json()

    if not data.get("results"):
        bot.reply_to(message, "❌ Movie nahi mili")
        return

    markup = InlineKeyboardMarkup()
    results = data["results"][:10]

    for movie in results:
        title = movie.get("title")
        year = movie.get("release_date", "")[:4]
        movie_id = movie.get("id")

        btn_text = f"{title} ({year})"
        markup.add(
            InlineKeyboardButton(
                btn_text,
                callback_data=f"movie_{movie_id}"
            )
        )

    bot.send_message(
        message.chat.id,
        "🎥 <b>Select Movie</b>",
        reply_markup=markup
    )


# ========= MOVIE DETAILS =========
@bot.callback_query_handler(func=lambda call: call.data.startswith("movie_"))
def movie_details(call):
    movie_id = call.data.split("_")[1]

    params = {
        "api_key": TMDB_API_KEY,
        "language": "en-US"
    }

    r = requests.get(TMDB_MOVIE_URL + movie_id, params=params)
    movie = r.json()

    title = movie.get("title")
    overview = movie.get("overview", "No description available")
    rating = movie.get("vote_average", "N/A")
    year = movie.get("release_date", "")[:4]
    poster = movie.get("poster_path")

    search_name = quote_plus(title)
    watch_url = MOVIE_WEBSITE + search_name

    caption = (
        f"🎬 <b>{title}</b> ({year})\n\n"
        f"⭐ Rating: {rating}\n\n"
        f"{overview}\n\n"
        f"🔎 <i>Searched via {BOT_USERNAME}</i>"
    )

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("▶️ Watch Now", url=watch_url)
    )

    if poster:
        bot.send_photo(
            call.message.chat.id,
            POSTER_BASE + poster,
            caption=caption,
            reply_markup=markup
        )
    else:
        bot.send_message(
            call.message.chat.id,
            caption,
            reply_markup=markup
        )

    bot.answer_callback_query(call.id)


# ========= RUN =========
print("Bot started...")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
