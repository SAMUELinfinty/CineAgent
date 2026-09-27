import socket
import tools
import json
# Force IPv4 socket resolution to prevent Windows IPv6 DNS timeouts on Telegram API
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET] or res
socket.getaddrinfo = _ipv4_only_getaddrinfo

import os
import requests
import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from State import state
import movies
from Agent import run_agent
from llm import ask_openrouter



load_dotenv()

telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
personal_chat_id = os.getenv("PERSONAL_CHAT_ID")
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
model = "liquid/lfm-2.5-2.6b:free"

if not telegram_bot_token:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Add it to a .env file.")
if not personal_chat_id:
    raise RuntimeError("PERSONAL_CHAT_ID is not set. Add it to a .env file.")
if not openrouter_api_key:
    raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to a .env file.")

bot = telebot.TeleBot(telegram_bot_token, parse_mode=None)


def get_movie_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("Yes", callback_data="yes"),
        InlineKeyboardButton("No", callback_data="no")
    )
    keyboard.row(InlineKeyboardButton("Another Movie", callback_data="another"))
    return keyboard


def format_movie_recommendation(movie_data: dict, pitch: str) -> str:
    """Keep essential movie facts visible even if the AI omits them."""
    return "\n".join((
        f"🎬 {movie_data['title']} ({movie_data['year']})",
        f"⭐ IMDb: {movie_data['rating']}/10",
        f"🎭 Genres: {movie_data['genres']}",
        f"🎥 Director: {movie_data['director']}",
        "",
        pitch.strip(),
    ))

def generate_movie_recommendation(chat_id):
    # 1. Fetch user's history from state
    session = state.get_user_session(chat_id)
    seen = session.get("seen_movies", [])
    disliked = session.get("disliked_movies", [])

    # 2. Pick unseen movie from watchlist CSV
    movie_data = movies.pick_recommendation(seen_titles=seen, disliked_titles=disliked)

    if not movie_data:
        return (
            "🎬 You've reviewed all titles in your IMDb watchlist!\n"
            "Add more titles to Data/watchlist.csv or clear your session history.",
            None
        )

    selected_movie = movie_data["title"]
    state.set_current_movie(chat_id, selected_movie)

    # 3. Create a rich prompt using CSV metadata
    prompt = (
        f"You are CineAgent, a passionate AI movie assistant.\n"
        f"Write a spoiler-free, compelling 2-3 sentence pitch for '{movie_data['title']}'.\n"
        f"Focus on its premise, tone, and why someone should watch it today.\n"
        f"Do not invent plot details, ratings, cast, or awards. Do not add a title or metadata heading."
    )

    pitch = ask_openrouter(prompt)
    return format_movie_recommendation(movie_data, pitch), get_movie_keyboard()

@bot.message_handler(commands=['movie'])
def movie_command(message: Message):
    if str(message.chat.id) != personal_chat_id:
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return

    try:
        bot.send_chat_action(message.chat.id, "typing")
        text, keyboard = generate_movie_recommendation(message.chat.id)
        bot.reply_to(message, text, reply_markup=keyboard)
    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, "Sorry, I couldn't create a recommendation right now. Please try again.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    if str(chat_id) != personal_chat_id:
        bot.answer_callback_query(call.id, "You are not authorized to use this bot.")
        return

    current = state.get_current_movie(chat_id)

    # Guard Clause: User clicked Yes or No without an active movie recommendation
    if call.data in ["yes", "no"] and not current:
        bot.answer_callback_query(call.id, "No active recommendation! Type /movie to get one.")
        return

    if call.data == "yes":
        state.record_feedback(chat_id, current, liked=True)
        bot.answer_callback_query(call.id, f"Glad you liked '{current}'!")
    elif call.data == "no":
        state.record_feedback(chat_id, current, liked=False)
        bot.answer_callback_query(call.id, f"Noted! We'll avoid similar recommendations.")
    elif call.data == "another":
        try:
            bot.send_chat_action(chat_id, "typing")
            text, keyboard = generate_movie_recommendation(chat_id)

            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=text,
                reply_markup=keyboard
            )
        except Exception as e:
            bot.answer_callback_query(call.id, "Couldn't find another title. Please try again.")


@bot.message_handler(func=lambda message: True)
def handle_message(message: Message):
    if str(message.chat.id) != personal_chat_id:
        bot.reply_to(message, "Sorry, you are not authorized to use this bot.")
        return


    try:
        bot.send_chat_action(message.chat.id, "typing")
        current_movie = state.get_current_movie(message.chat.id)
        
        # Include current movie context if available
        system_context = f"The user is currently discussing the movie: {current_movie}." if current_movie else ""
        answer = run_agent(message.text, chat_id=message.chat.id)
        bot.reply_to(message,answer)
    except Exception as e:
        print(f"Agent Error: {e}")
        bot.reply_to(message, "Sorry, the assistant is temporarily unavailable. Please try again.")

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
