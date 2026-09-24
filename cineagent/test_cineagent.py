import unittest
import json
import movies
import tools
from State import state

class TestCineAgentSystem(unittest.TestCase):

    def test_csv_loading(self):
        """Test that watchlist.csv is parsed and contains titles."""
        all_titles = movies.load_movies_from_csv()
        self.assertIsInstance(all_titles, list)
        self.assertGreater(len(all_titles), 0, "watchlist.csv should contain at least 1 title")
        self.assertIn("title", all_titles[0])

    def test_state_recommendation_filtering(self):
        """Test that state properly excludes seen titles from recommendations."""
        test_chat_id = "test_user_999"
        all_movies = movies.load_movies_from_csv()
        
        if len(all_movies) >= 2:
            movie1 = all_movies[0]["title"]
            # Mark movie1 as seen
            state.set_current_movie(test_chat_id, movie1)
            
            # Pick next recommendation
            rec = movies.pick_recommendation(
                seen_titles=[movie1], 
                disliked_titles=[]
            )
            self.assertIsNotNone(rec)
            self.assertNotEqual(rec["title"], movie1, "Recommendation should not be an already seen movie")

    def test_tool_execution(self):
        """Test that tools return valid JSON data."""
        res = tools.execute_tool_call("get_watchlist_stats", {})
        data = json.loads(res)
        self.assertIn("total_movies", data)
        self.assertGreater(data["total_movies"], 0)

if __name__ == "__main__":
    unittest.main()
