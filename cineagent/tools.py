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

def search_watchlist(query: str = "", genre: str = "", media_type: str = "") -> list[dict]:
    """Searches your real IMDb watchlist CSV for titles matching a query, genre, or media_type (Movie vs TV Series)."""
    all_movies = movies.load_movies_from_csv()
    results = []
    
    clean_query = (query or "").strip().lower()
    clean_genre = (genre or "").strip().lower()
    clean_type = (media_type or "").strip().lower()

    # Automatically handle common queries like 'tv series' or 'shows' passed in query parameter
    if clean_query in ["tv series", "tv show", "tv shows", "series", "shows"]:
        clean_type = "tv series"
        clean_query = ""
    elif clean_query in ["movie", "movies", "films", "film"]:
        clean_type = "movie"
        clean_query = ""

    for m in all_movies:
        item_title = m.get("title", "").lower()
        item_genre = m.get("genres", "").lower()
        item_type = m.get("type", "").lower()

        matches_query = clean_query in item_title if clean_query else True
        matches_genre = clean_genre in item_genre if clean_genre else True
        matches_type = clean_type in item_type if clean_type else True

        if matches_query and matches_genre and matches_type:
            results.append(m)
    return results[:5]

TOOL_ROUTER = {
    "get_user_history": tool_get_user_history,
    "search_movies_by_genre": tool_search_movies_by_genre,
    "get_watchlist_stats": tool_get_watchlist_stats,
    "search_watchlist": search_watchlist
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
    }
]
def execute_tool_call(tool_name: str, arguments: dict, chat_id: str | int = None) -> str:

    """Executes the requested tool by name with arguments and returns JSON string result."""
    if tool_name not in TOOL_ROUTER:
        return json.dumps({"error": f"Tool '{tool_name}' not found."})
    
    func = TOOL_ROUTER[tool_name]
    
    # Automatically inject chat_id if required by tool_get_user_history
    if tool_name == "get_user_history" and "chat_id" not in arguments and chat_id:
        arguments["chat_id"] = chat_id
        
    try:
        result = func(**arguments)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})
