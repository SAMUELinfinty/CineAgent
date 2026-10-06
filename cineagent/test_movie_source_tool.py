import json
import unittest
from unittest.mock import AsyncMock, patch

import tools
from telegram_client.movie_source import (
    MovieSourcePage,
    MovieSourceResult,
    PaginationInfo,
)


class TestMovieSourceTool(unittest.TestCase):
    def setUp(self):
        self.result = MovieSourceResult(
            raw_text="[250 MB] Person of Interest S01E01 2011 720p",
            title="Person of Interest S01E01",
            year=2011,
            size_mb=250,
            quality="720p",
            callback_data=b"pmfile#private-to-telegram",
        )
        self.page = MovieSourcePage(
            query="Person of Interest S01E01",
            response_text="Results",
            results=[self.result],
            pagination=PaginationInfo(None, None, False, None),
        )

    @patch("tools.MovieSourceClient")
    def test_returns_selected_result_without_callback_data(self, source_client_class):
        source_client_class.return_value.search_pages = AsyncMock(return_value=[self.page])

        output = tools.tool_movie_source_search(
            query="Person of Interest S01E01",
            title_query="Person of Interest S01E01",
            episode="S01E01",
            max_size_mb=300,
        )

        source_client_class.return_value.search_pages.assert_awaited_once_with(
            "Person of Interest S01E01", max_pages=1
        )
        self.assertEqual(output["selection"]["result"]["title"], "Person of Interest S01E01")
        self.assertNotIn("callback_data", output["selection"]["result"])

    @patch("tools.MovieSourceClient")
    def test_router_returns_a_clear_no_match_result(self, source_client_class):
        source_client_class.return_value.search_pages = AsyncMock(return_value=[self.page])

        output = json.loads(
            tools.execute_tool_call(
                "movie_source_search",
                {"query": "Person of Interest S01E01", "max_size_mb": 100},
            )
        )

        self.assertIsNone(output["selection"]["result"])
        self.assertEqual(output["selection"]["matching_count"], 0)


if __name__ == "__main__":
    unittest.main()
