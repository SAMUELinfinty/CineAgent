import json
import unittest

import movies
import tools


class TestWatchlistTools(unittest.TestCase):
    def test_finds_person_of_interest_in_the_existing_watchlist(self):
        results = tools.search_watchlist(query="Person of Interest")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Person of Interest")
        self.assertEqual(results[0]["type"], "TV Series")

    def test_filters_existing_watchlist_by_sci_fi_genre(self):
        results = tools.search_watchlist(genre="Sci-Fi")

        self.assertGreater(len(results), 0)
        self.assertTrue(all("sci-fi" in movie["genres"].lower() for movie in results))

    def test_pick_tool_uses_the_existing_watchlist(self):
        output = json.loads(
            tools.execute_tool_call("pick_from_watchlist", {}, chat_id="watchlist-tool-test")
        )
        known_titles = {movie["title"] for movie in movies.load_movies_from_csv()}

        self.assertIn(output["title"], known_titles)

    def test_pick_tool_is_exposed_to_the_agent(self):
        schema_names = {item["function"]["name"] for item in tools.TOOLS_SCHEMA}

        self.assertIn("search_watchlist", schema_names)
        self.assertIn("pick_from_watchlist", schema_names)


if __name__ == "__main__":
    unittest.main()
