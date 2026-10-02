from State import state
import movies
import json

def tool_get_user_history(chat_id: str | int) -> dict:
    """Returns the user's liked, disliked, and seen movies history."""
    session = state.get_user_session(chat_id)
    return {
        "liked_movies": session.get("liked_movies", []),
        "disliked_movies": session.get("disliked_movies", []),
        "seen_count": len(session.get("seen_movies", []))
    }

def tool_search_movies_by_genre(genre: str) -> list[dict]:
    """Searches the watchlist CSV for movies matching a specific genre."""
    all_movies = movies.load_movies_from_csv()
    results = [
        m for m in all_movies 
        if genre.lower() in m.get("genres", "").lower()
    ]
    return results[:5]  # Limit top 5 matches

def tool_get_watchlist_stats() -> dict:
    """Returns general statistics about the user's movie dataset."""
    all_movies = movies.load_movies_from_csv()
    return {
        "total_movies": len(all_movies),
        "sample_titles": [m["title"] for m in all_movies[:5]]
    }

KNOWN_GENRES = [
    "action", "adventure", "animation", "biography", "comedy", "crime",
    "documentary", "drama", "family", "fantasy", "film-noir", "history",
    "horror", "music", "musical", "mystery", "romance", "sci-fi", "sport",
    "thriller", "war", "western"
]

# ─── Mood → Genre Mapping ──────────────────────────────────────────────────────
# Keywords the user might say → genres to search in the CSV
# The LLM passes the user's raw mood string; we do the mapping here in Python.
MOOD_GENRE_MAP = {
    # Dark / Intense
    "dark":        ["Crime", "Thriller", "Drama", "Horror"],
    "gritty":      ["Crime", "Drama", "Thriller"],
    "intense":     ["Thriller", "Action", "Crime"],
    "disturbing":  ["Horror", "Thriller", "Drama"],
    "noir":        ["Crime", "Film-Noir", "Mystery", "Thriller"],
    # Scary
    "scary":       ["Horror", "Thriller"],
    "horror":      ["Horror"],
    "creepy":      ["Horror", "Mystery", "Thriller"],
    # Funny / Light
    "funny":       ["Comedy"],
    "comedy":      ["Comedy"],
    "lighthearted":["Comedy", "Family", "Animation"],
    "feel-good":   ["Comedy", "Drama", "Family"],
    "cheerful":    ["Comedy", "Family", "Animation"],
    # Action / Adrenaline
    "action":      ["Action", "Adventure"],
    "adrenaline":  ["Action", "Thriller", "Adventure"],
    "exciting":    ["Action", "Adventure", "Thriller"],
    "explosive":   ["Action", "Adventure"],
    # Sci-Fi / Mind-bending
    "sci-fi":      ["Sci-Fi"],
    "mind-bending":["Sci-Fi", "Mystery", "Thriller"],
    "futuristic":  ["Sci-Fi", "Adventure"],
    "philosophical":["Sci-Fi", "Drama", "Mystery"],
    # Mystery / Puzzle
    "mystery":     ["Mystery", "Crime", "Thriller"],
    "detective":   ["Crime", "Mystery", "Thriller"],
    "suspense":    ["Thriller", "Mystery", "Crime"],
    # Emotional / Drama
    "emotional":   ["Drama", "Romance"],
    "dramatic":    ["Drama"],
    "romantic":    ["Romance", "Drama"],
    "sad":         ["Drama", "Romance"],
    # Epic / Adventure
    "epic":        ["Adventure", "Action", "Drama", "History"],
    "adventure":   ["Adventure", "Action"],
    "fantasy":     ["Fantasy", "Adventure"],
    # Inspiring / Biography
    "inspiring":   ["Drama", "Biography", "History"],
    "biography":   ["Biography", "Drama", "History"],
    "war":         ["War", "Drama", "History"],
    # Chill / Relaxed
    "chill":       ["Comedy", "Animation", "Family", "Drama"],
    "relaxed":     ["Comedy", "Animation", "Family"],
    "cozy":        ["Comedy", "Family", "Drama"],
}

def tool_recommend_by_mood(mood: str, chat_id: str | int = None) -> list[dict]:
    """Maps a mood/vibe string to genres, then returns up to 3 unseen watchlist movies that match."""
    mood_lower = mood.lower()

    # Step 1: Collect all genres that match any keyword in the mood string
    matched_genres: set[str] = set()
    for keyword, genres in MOOD_GENRE_MAP.items():
        if keyword in mood_lower:
            matched_genres.update(genres)

    # Step 2: Fallback — if no keyword matched, treat words in mood as genre hints directly
    if not matched_genres:
        for known in KNOWN_GENRES:
            if known in mood_lower:
                matched_genres.add(known.capitalize())

    # Step 3: Load watchlist and filter by matched genres
    all_movies = movies.load_movies_from_csv()

    # Exclude already-seen and disliked movies if we have a chat_id
    excluded: set[str] = set()
    if chat_id:
        session = state.get_user_session(chat_id)
        excluded = set(
            session.get("seen_movies", []) + session.get("disliked_movies", [])
        )

    candidates = [
        m for m in all_movies
        if m["title"] not in excluded
        and any(g.lower() in m.get("genres", "").lower() for g in matched_genres)
    ]

    # Return up to 3 diverse candidates (LLM picks the best one to pitch)
    return {
        "matched_genres": list(matched_genres),
        "candidates": candidates[:3]
    }

def search_watchlist(query: str = "", genre: str = "", media_type: str = "") -> list[dict]:
    """Searches your real IMDb watchlist CSV for titles matching a query, genre, or media_type (Movie vs TV Series)."""
    all_movies = movies.load_movies_from_csv()
    results = []
    
    q = (query or "").strip().lower()
    g = (genre or "").strip().lower()
    t = (media_type or "").strip().lower()

    # Extract media type keywords from query/genre if present
    for mkw, target_t in [
        ("tv series", "tv series"), ("tv show", "tv series"), 
        ("shows", "tv series"), ("series", "tv series"), 
        ("movies", "movie"), ("movie", "movie"), ("films", "movie"), ("film", "movie")
    ]:
        if mkw in q:
            t = target_t
            q = q.replace(mkw, "").strip()
        if mkw in g:
            t = target_t
            g = g.replace(mkw, "").strip()

    # Extract genre keywords from query if query contains known genres
    for genre_kw in KNOWN_GENRES:
        if genre_kw in q:
            g = genre_kw
            q = q.replace(genre_kw, "").strip()

    for m in all_movies:
        item_title = m.get("title", "").lower()
        item_genre = m.get("genres", "").lower()
        item_type = m.get("type", "").lower()

        matches_q = q in item_title if q else True
        matches_g = g in item_genre if g else True
        matches_t = t in item_type if t else True

        if matches_q and matches_g and matches_t:
            results.append(m)

    return results[:5]

TOOL_ROUTER = {
    "get_user_history": tool_get_user_history,
    "search_movies_by_genre": tool_search_movies_by_genre,
    "get_watchlist_stats": tool_get_watchlist_stats,
    "search_watchlist": search_watchlist,
    "recommend_by_mood": tool_recommend_by_mood,
}
# OpenAPI/OpenRouter JSON Schemas
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_user_history",
            "description": "Get the user's liked movies, disliked movies, and total seen count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "string",
                        "description": "The user's Telegram chat ID."
                    }
                },
                "required": ["chat_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_movies_by_genre",
            "description": "Search the movie watchlist for movies of a specific genre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "genre": {
                        "type": "string",
                        "description": "Genre to filter by, e.g., 'Crime', 'Drama', 'Action', 'Sci-Fi'."
                    }
                },
                "required": ["genre"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_watchlist_stats",
            "description": "Get general statistics about the available watchlist dataset.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_watchlist",
            "description": "Searches the user's real IMDb watchlist CSV by title keyword or genre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Title or keyword to search for, e.g. 'Person of Interest', 'Primal'."
                    },
                    "genre": {
                        "type": "string",
                        "description": "Optional genre filter, e.g. 'Crime', 'Sci-Fi'."
                    },
                    "media_type": {
                        "type": "string",
                        "description": "Optional media type filter: 'Movie' or 'TV Series'."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_by_mood",
            "description": "Recommends movies from the watchlist based on the user's current mood or vibe. Use this when the user describes how they feel or what kind of experience they want (e.g. 'something dark', 'a feel-good comedy', 'edge-of-seat thriller').",
            "parameters": {
                "type": "object",
                "properties": {
                    "mood": {
                        "type": "string",
                        "description": "The user's mood or vibe, e.g. 'dark gritty thriller', 'something funny and lighthearted', 'mind-bending sci-fi'."
                    }
                },
                "required": ["mood"]
            }
        }
    }
]
def execute_tool_call(tool_name: str, arguments: dict, chat_id: str | int = None) -> str:

    """Executes the requested tool by name with arguments and returns JSON string result."""
    if tool_name not in TOOL_ROUTER:
        return json.dumps({"error": f"Tool '{tool_name}' not found."})
    
    func = TOOL_ROUTER[tool_name]
    
    # Inject chat_id for tools that use it to personalise results
    # (filtering seen/disliked movies, fetching user session, etc.)
    CHAT_ID_TOOLS = {"get_user_history", "recommend_by_mood"}
    if tool_name in CHAT_ID_TOOLS and "chat_id" not in arguments and chat_id:
        arguments["chat_id"] = chat_id
        
    try:
        result = func(**arguments)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})
