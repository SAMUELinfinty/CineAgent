import json
import unittest
from unittest.mock import AsyncMock, patch

import Agent
from telegram_client.movie_source import (
    MovieSourcePage,
    MovieSourceResult,
    PaginationInfo,
)


class FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class TestEndToEndMovieSourceWorkflow(unittest.TestCase):
    @patch("tools.MovieSourceClient")
    @patch("llm.requests.post")
    def test_agent_searches_filters_selects_and_responds(self, post, source_client_class):
        matching_result = MovieSourceResult(
            raw_text="[250 MB] Person of Interest S01E01 2011 720p",
            title="Person of Interest S01E01",
            year=2011,
            size_mb=250,
            quality="720p",
            callback_data=b"pmfile#opaque-callback",
        )
        rejected_result = MovieSourceResult(
            raw_text="[900 MB] Person of Interest S01E01 2011 1080p",
            title="Person of Interest S01E01",
            year=2011,
            size_mb=900,
            quality="1080p",
            callback_data=b"pmfile#another-callback",
        )
        page = MovieSourcePage(
            query="Person of Interest S01E01",
            response_text="Results",
            results=[rejected_result, matching_result],
            pagination=PaginationInfo(None, None, False, None),
        )
        source_client_class.return_value.search_pages = AsyncMock(return_value=[page])

        tool_arguments = {
            "query": "Person of Interest S01E01",
            "title_query": "Person of Interest S01E01",
            "episode": "S01E01",
            "max_size_mb": 300,
        }
        post.side_effect = [
            FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "movie-source-call",
                                        "type": "function",
                                        "function": {
                                            "name": "movie_source_search",
                                            "arguments": json.dumps(tool_arguments),
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ),
            FakeHttpResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "I found a 720p Person of Interest S01E01 result at 250 MB.",
                            }
                        }
                    ]
                }
            ),
        ]

        answer = Agent.run_agent(
            "Find Person of Interest S01E01 under 300 MB.", chat_id="end-to-end-test"
        )

        self.assertEqual(answer, "I found a 720p Person of Interest S01E01 result at 250 MB.")
        source_client_class.return_value.search_pages.assert_awaited_once_with(
            "Person of Interest S01E01", max_pages=1
        )

        second_request_payload = post.call_args_list[1].kwargs["json"]
        tool_message = next(message for message in second_request_payload["messages"] if message["role"] == "tool")
        tool_output = json.loads(tool_message["content"])
        selected = tool_output["selection"]["result"]

        self.assertEqual(selected["size_mb"], 250)
        self.assertEqual(selected["quality"], "720p")
        self.assertNotIn("callback_data", selected)


if __name__ == "__main__":
    unittest.main()
