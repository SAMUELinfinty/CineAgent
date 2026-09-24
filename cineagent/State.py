import json
import os
import threading

STATE_FILE = os.path.join(os.path.dirname(__file__), "user_states.json")

class StateManager:
    def __init__(self, filename=STATE_FILE):
        self.filename = filename
        # State-changing methods call helpers that also acquire this lock.
        # RLock prevents a self-deadlock during a /movie request.
        self.lock = threading.RLock()
        self.sessions = self._load_states()

    def _load_states(self):
        """Load state from JSON file if it exists."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading state file: {e}")
        return {}

    def save(self):
        """Save current state to JSON file."""
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving state file: {e}")

    def get_user_session(self, chat_id: str | int) -> dict:
        """Get or initialize a user session."""
        chat_id = str(chat_id)
        with self.lock:
            if chat_id not in self.sessions:
                self.sessions[chat_id] = {
                    "current_movie": None,
                    "seen_movies": [],
                    "liked_movies": [],
                    "disliked_movies": []
                }
            return self.sessions[chat_id]

    def set_current_movie(self, chat_id: str | int, movie: str):
        chat_id = str(chat_id)
        with self.lock:
            session = self.get_user_session(chat_id)
            session["current_movie"] = movie
            if movie not in session["seen_movies"]:
                session["seen_movies"].append(movie)
            self.save()

    def get_current_movie(self, chat_id: str | int) -> str | None:
        return self.get_user_session(chat_id).get("current_movie")

    def record_feedback(self, chat_id: str | int, movie: str, liked: bool):
        chat_id = str(chat_id)
        with self.lock:
            session = self.get_user_session(chat_id)
            target_list = session["liked_movies"] if liked else session["disliked_movies"]
            if movie and movie not in target_list:
                target_list.append(movie)
            self.save()

    def get_unseen_movies(self, chat_id: str | int, all_movies: list[str]) -> list[str]:
        """Returns movies from the candidate list that the user hasn't been recommended yet."""
        session = self.get_user_session(chat_id)
        seen = set(session.get("seen_movies", []))
        unseen = [m for m in all_movies if m not in seen]
        return unseen if unseen else all_movies  # Reset if all seen

# Instantiate global singleton manager
state = StateManager()
