import json
import unittest
from unittest.mock import patch

import tools


class TestMoodRecommendationTool(unittest.TestCase):
    def test_dark_mood_returns_real_watchlist_candidates(self):
        result = tools.tool_recommend_by_mood("dark thriller", chat_id="mood-dark-test")

        self.assertGreater(len(result["matched_genres"]), 0)
        self.assertGreater(len(result["candidates"]), 0)
        self.assertTrue(
            all(
                any(genre.lower() in movie["genres"].lower() for genre in result["matched_genres"])
                for movie in result["candidates"]
            )
        )

    def test_seen_titles_are_excluded_from_mood_candidates(self):
        initial = tools.tool_recommend_by_mood("funny")
        seen_title = initial["candidates"][0]["title"]

        with patch.object(
            tools.state,
            "get_user_session",
            return_value={"seen_movies": [seen_title], "disliked_movies": []},
        ):
            result = tools.tool_recommend_by_mood("funny", chat_id="mood-seen-test")

        self.assertNotIn(seen_title, [movie["title"] for movie in result["candidates"]])

    def test_agent_tool_router_passes_the_mood_to_python(self):
        output = json.loads(
            tools.execute_tool_call(
                "recommend_by_mood", {"mood": "mind-bending sci-fi"}, chat_id="mood-router-test"
            )
        )

        self.assertIn("Sci-Fi", output["matched_genres"])
        self.assertGreater(len(output["candidates"]), 0)


if __name__ == "__main__":
    unittest.main()
