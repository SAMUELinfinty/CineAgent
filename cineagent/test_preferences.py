import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import Agent
from State import StateManager
import tools


class TestPreferenceState(unittest.TestCase):
    def test_preferences_are_saved_and_loaded_as_explicit_data(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_path = Path(temporary_directory) / "preferences.json"
            manager = StateManager(filename=str(state_path))
            saved = manager.update_preferences(
                "preference-test",
                preferred_genres=["Sci-Fi", "Thriller"],
                disliked_genres=["Horror"],
                preferred_media_type="TV Series",
                explicit_preference="Avoid gore",
                recommendation_style="Keep it concise",
            )

            reloaded = StateManager(filename=str(state_path)).get_preferences("preference-test")

        self.assertEqual(saved, reloaded)
        self.assertEqual(reloaded["preferred_genres"], ["Sci-Fi", "Thriller"])
        self.assertEqual(reloaded["disliked_genres"], ["Horror"])
        self.assertEqual(reloaded["preferred_media_type"], "TV Series")

    @patch("tools.state.update_preferences")
    def test_preference_tool_saves_explicit_values(self, update_preferences):
        update_preferences.return_value = {"preferred_genres": ["Sci-Fi"]}

        output = json.loads(
            tools.execute_tool_call(
                "set_user_preferences",
                {"preferred_genres": ["Sci-Fi"]},
                chat_id="preference-router-test",
            )
        )

        update_preferences.assert_called_once_with(
            "preference-router-test",
            preferred_genres=["Sci-Fi"],
            disliked_genres=None,
            preferred_media_type=None,
            explicit_preference=None,
            recommendation_style=None,
        )
        self.assertEqual(output["preferred_genres"], ["Sci-Fi"])

    def test_disliked_genres_are_excluded_from_mood_candidates(self):
        session = {
            "seen_movies": [],
            "disliked_movies": [],
            "preferences": {"disliked_genres": ["Horror"], "preferred_genres": [], "preferred_media_type": None},
        }
        preferences = session["preferences"]
        with patch.object(tools.state, "get_user_session", return_value=session), patch.object(
            tools.state, "get_preferences", return_value=preferences
        ):
            result = tools.tool_recommend_by_mood("dark")

        self.assertTrue(all("horror" not in movie["genres"].lower() for movie in result["candidates"]))

    @patch("Agent.ask_openrouter", return_value="Recommendation")
    @patch.object(Agent.state, "get_preferences")
    @patch.object(Agent.state, "get_current_movie", return_value=None)
    def test_agent_receives_explicit_preferences_in_context(
        self, _, get_preferences, ask_openrouter
    ):
        get_preferences.return_value = {
            "preferred_genres": ["Sci-Fi"],
            "disliked_genres": ["Horror"],
            "preferred_media_type": None,
            "explicit_preferences": [],
            "recommendation_style": "Keep it concise",
        }

        Agent.run_agent("Recommend something", chat_id="preference-agent-test")

        system_context = ask_openrouter.call_args.kwargs["system_context"]
        self.assertIn("explicit user preferences", system_context)
        self.assertIn("Sci-Fi", system_context)


if __name__ == "__main__":
    unittest.main()
