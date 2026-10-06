import unittest

from telegram_client.movie_source import (
    MovieSourceClient,
    SearchConstraints,
    filter_results,
    parse_result_button,
    parse_search_response,
    select_result,
    should_fetch_next_page,
)


class FakeButton:
    def __init__(self, text, data=None):
        self.text = text
        self.data = data


class FakeResponse:
    def __init__(self, message, buttons):
        self.message = message
        self.buttons = buttons


class FakePageResponse(FakeResponse):
    def __init__(self, message, buttons):
        super().__init__(message, buttons)
        self.clicked_data = None

    async def click(self, *, data):
        self.clicked_data = data


class FakeConversation:
    def __init__(self, first_response, second_response):
        self.first_response = first_response
        self.second_response = second_response
        self.sent_query = None
        self.edited_message = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def send_message(self, query):
        self.sent_query = query

    async def get_response(self, *, timeout):
        return self.first_response

    async def get_edit(self, message, *, timeout):
        self.edited_message = message
        return self.second_response


class FakeClient:
    def __init__(self, conversation):
        self._conversation = conversation
        self.connected = False

    async def connect(self):
        self.connected = True

    async def is_user_authorized(self):
        return True

    async def get_entity(self, username):
        return username

    def conversation(self, bot):
        return self._conversation

    async def disconnect(self):
        self.connected = False


class TestMovieSourceParser(unittest.TestCase):
    def test_parses_explicit_result_metadata(self):
        result = parse_result_button(
            FakeButton("[946 MB] This Is Not A Test 2025 720p x264 -", b"pmfile#123")
        )

        self.assertEqual(result.title, "This Is Not A Test")
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.size_mb, 946)
        self.assertEqual(result.quality, "720p")
        self.assertEqual(result.callback_data, b"pmfile#123")

    def test_leaves_unknown_fields_as_none(self):
        result = parse_result_button(FakeButton("Unstructured response", b"pmfile#456"))

        self.assertIsNone(result.title)
        self.assertIsNone(result.year)
        self.assertIsNone(result.size_mb)
        self.assertIsNone(result.quality)

    def test_keeps_binary_callback_data_in_hex(self):
        result = parse_result_button(FakeButton("Result", b"\xff\x00"))

        self.assertIsNone(result.to_dict()["callback_data"])
        self.assertEqual(result.to_dict()["callback_data_hex"], "ff00")

    def test_separates_next_page_from_results(self):
        response = FakeResponse(
            "Results",
            [
                [FakeButton("[250 MB] Example 2024 720p", b"pmfile#1")],
                [FakeButton("NEXT [1/33] ➡️", b"next#1")],
            ],
        )

        page = parse_search_response("Example", response)
        self.assertEqual(len(page.results), 1)
        self.assertTrue(page.pagination.has_next_page)
        self.assertEqual(page.pagination.current_page, 1)
        self.assertEqual(page.pagination.total_pages, 33)
        self.assertEqual(page.pagination.next_callback_data, b"next#1")

    def test_next_page_requires_an_explicit_limit_and_callback(self):
        page = parse_search_response(
            "Example",
            FakeResponse("Results", [[FakeButton("NEXT [1/33] ➡️", b"next#1")]]),
        )

        self.assertFalse(should_fetch_next_page(page, pages_retrieved=1, max_pages=1))
        self.assertTrue(should_fetch_next_page(page, pages_retrieved=1, max_pages=2))


class TestMovieSourceFiltering(unittest.TestCase):
    def setUp(self):
        self.episode_result = parse_result_button(
            FakeButton("[250 MB] Person of Interest S01E01 2011 720p", b"one")
        )
        self.large_result = parse_result_button(
            FakeButton("[1.20 GB] Person of Interest S01E01 2011 1080p", b"two")
        )
        self.unknown_result = parse_result_button(FakeButton("Person of Interest", b"three"))

    def test_filters_by_title_episode_size_and_quality(self):
        constraints = SearchConstraints(
            title_query="Person of Interest S01E01",
            episode="S01E01",
            max_size_mb=300,
            max_quality="720p",
        )

        matches = filter_results(
            [self.episode_result, self.large_result, self.unknown_result], constraints
        )

        self.assertEqual(matches, [self.episode_result])

    def test_unknown_metadata_does_not_satisfy_a_constraint(self):
        matches = filter_results(
            [self.unknown_result], SearchConstraints(max_size_mb=300, min_quality="720p")
        )

        self.assertEqual(matches, [])

    def test_quality_bounds_are_resolution_based(self):
        matches = filter_results(
            [self.episode_result, self.large_result],
            SearchConstraints(min_quality="720p", max_quality="720p"),
        )

        self.assertEqual(matches, [self.episode_result])

    def test_rejects_invalid_constraints_even_without_results(self):
        with self.assertRaisesRegex(ValueError, "min_quality"):
            filter_results([], SearchConstraints(min_quality="1080p", max_quality="720p"))


class TestMovieSourceSelection(unittest.TestCase):
    def setUp(self):
        self.first_match = parse_result_button(
            FakeButton("[700 MB] Example 2024 720p", b"first")
        )
        self.second_match = parse_result_button(
            FakeButton("[500 MB] Example 2024 720p", b"second")
        )
        self.non_match = parse_result_button(
            FakeButton("[200 MB] Different 2024 720p", b"different")
        )

    def test_selects_first_match_in_source_order(self):
        outcome = select_result(
            [self.non_match, self.first_match, self.second_match],
            SearchConstraints(title_query="Example", max_quality="720p"),
        )

        self.assertEqual(outcome.selected, self.first_match)
        self.assertEqual(outcome.matching_count, 2)
        self.assertIn("source order", outcome.reason)

    def test_returns_no_match_outcome(self):
        outcome = select_result(
            [self.non_match], SearchConstraints(title_query="Example", max_size_mb=100)
        )

        self.assertIsNone(outcome.selected)
        self.assertEqual(outcome.matching_count, 0)
        self.assertEqual(outcome.reason, "No source result matched the explicit constraints.")


class TestMovieSourcePagination(unittest.IsolatedAsyncioTestCase):
    async def test_search_pages_clicks_next_and_parses_the_edit(self):
        first_response = FakePageResponse(
            "Page one",
            [
                [FakeButton("[100 MB] First 2024 720p", b"pmfile#first")],
                [FakeButton("NEXT [1/2] ➡️", b"next#page-two")],
            ],
        )
        second_response = FakePageResponse(
            "Page two",
            [[FakeButton("[200 MB] Second 2024 1080p", b"pmfile#second")]],
        )
        conversation = FakeConversation(first_response, second_response)
        source = MovieSourceClient.__new__(MovieSourceClient)
        source.client = FakeClient(conversation)
        source.phone = None
        source.target_bot_username = "@authorized_bot"

        pages = await source.search_pages("Example", max_pages=2)

        self.assertEqual(conversation.sent_query, "Example")
        self.assertEqual(first_response.clicked_data, b"next#page-two")
        self.assertIs(conversation.edited_message, first_response)
        self.assertEqual([page.response_text for page in pages], ["Page one", "Page two"])


if __name__ == "__main__":
    unittest.main()
