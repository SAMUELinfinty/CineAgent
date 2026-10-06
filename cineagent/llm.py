import os
import json
import requests
from dotenv import load_dotenv
import tools

load_dotenv()

# ─── CineAgent Persona ────────────────────────────────────────────────────────
# This is injected as the FIRST system message in every LLM call.
# Think of it as the "soul" of the bot — it shapes tone, rules, and behavior.
CINEAGENT_PERSONA = """You are CineAgent — a passionate, opinionated AI cinephile and personal movie concierge.

Your personality:
- You speak like a film critic who genuinely loves movies across all eras, genres, and cultures
- You are enthusiastic but never over-the-top; thoughtful but never dry
- You give honest takes and specific reasons why someone should watch a film TODAY
- You avoid hollow phrases like "masterpiece" or "timeless classic" unless you can justify them
- When recommending, you paint a vivid picture of the viewing experience — the mood, tension, and feeling

Your capabilities:
- You can search the user's personal IMDb watchlist by title, genre, or mood
- You recommend movies based on the user's current vibe, history, and preferences
- You always try to recommend from the user's actual watchlist before making up suggestions
- You know what the user has seen, liked, and disliked
- You can search the authorized movie source for an available result without downloading anything

Your rules:
- Never invent plot details, cast members, or awards you are not certain about
- Always search the watchlist first when recommending or looking up a film
- Keep responses concise and punchy — this is a chat, not a film school essay
- If the user asks for a mood-based pick, call the recommend_by_mood tool
- For a mood-based pick, pass the user's mood words to the tool and recommend only from its returned watchlist candidates
- If the user asks to pick something from their watchlist, call pick_from_watchlist
- If the user asks whether a title is in their watchlist, call search_watchlist
- Only call set_user_preferences when the user explicitly asks to remember a preference or directly states a lasting preference
- Never store an inferred preference or a one-time mood as a permanent preference
- If the user asks to find an available movie or episode release, call movie_source_search with only explicit constraints
- Never claim that a file was downloaded or that a Telegram button was activated
- Be warm, direct, and always cinema-passionate"""

openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

# ⚠️  Model choice matters enormously for tool/function calling.
# Small models (< 7B) often output tool calls as raw text tokens instead
# of the structured JSON {"tool_calls": [...]} the API expects.
# nemotron-120b was VERIFIED to emit proper structured tool_calls on OpenRouter.
# (Google Gemma-31b and Qwen-27b were rate-limited on the free shared pool)
model = "nvidia/nemotron-3-super-120b-a12b:free"

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

def ask_openrouter(prompt: str, system_context: str = "", chat_id: str = None, enable_tools: bool = False) -> str:
    if not openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    messages = []

    # Always inject the CineAgent persona as the first system message.
    # If extra context is provided (e.g. current movie), we append it to the persona.
    full_system = CINEAGENT_PERSONA
    if system_context:
        full_system += f"\n\nAdditional context: {system_context}"
    messages.append({"role": "system", "content": full_system})

    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages
    }
    
    if enable_tools:
        payload["tools"] = tools.TOOLS_SCHEMA

    try:
        # Step 1: Initial call to OpenRouter
        response = requests.post(
            openrouter_url,
            json=payload,
            headers={"Authorization": f"Bearer {openrouter_api_key}"},
            timeout=60,
        )
        response.raise_for_status()
        res_json = response.json()

        # Log and surface API errors clearly instead of cryptic KeyErrors
        if "choices" not in res_json:
            print(f"OpenRouter API error response: {res_json}")
            raise ValueError(f"No choices in response: {res_json.get('error', res_json)}")

        message_data = res_json["choices"][0]["message"]

        # Step 2: Check if LLM requested a Tool Call
        if "tool_calls" in message_data and message_data["tool_calls"]:
            messages.append(message_data)

            for tool_call in message_data["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                raw_args = tool_call["function"].get("arguments", "{}")
                try:
                    fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    fn_args = {}

                tool_output = tools.execute_tool_call(tool_name, fn_args, chat_id=chat_id)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": tool_output
                })

            # Step 3: Follow-up request with tool results
            second_response = requests.post(
                openrouter_url,
                json={"model": model, "messages": messages},
                headers={"Authorization": f"Bearer {openrouter_api_key}"},
                timeout=60,
            )
            second_response.raise_for_status()
            content = second_response.json()["choices"][0]["message"]["content"]
        else:
            content = message_data.get("content", "")

        if not content:
            raise ValueError("The AI service returned an empty response")
        return content

    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"Agent Loop Error: {exc}")
        raise RuntimeError("The movie assistant is temporarily unavailable. Please try again.") from exc
