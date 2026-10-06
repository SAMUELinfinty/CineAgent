"""Read-only search and parsing for the authorized Telegram movie source."""

import asyncio
import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any

from dotenv import load_dotenv
from telethon import TelegramClient


load_dotenv()

_SIZE_PATTERN = re.compile(r"(?<!\w)(\d+(?:\.\d+)?)\s*(KB|MB|GB)(?!\w)", re.IGNORECASE)
_YEAR_PATTERN = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_QUALITY_PATTERN = re.compile(r"(?<!\w)(2160p|1080p|720p|480p|4k)(?!\w)", re.IGNORECASE)
_PAGE_PATTERN = re.compile(r"\[(\d+)\s*/\s*(\d+)\]")


@dataclass(frozen=True)
class MovieSourceResult:
    """One inline button returned by the source bot."""

    raw_text: str
    title: str | None
    year: int | None
    size_mb: float | None
    quality: str | None
    callback_data: bytes | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly view while retaining a reversible callback form."""
        data = asdict(self)
        callback = self.callback_data
        data["callback_data"] = _callback_text(callback)
        data["callback_data_hex"] = callback.hex() if callback else None
        return data


@dataclass(frozen=True)
class PaginationInfo:
    current_page: int | None
    total_pages: int | None
    has_next_page: bool
    next_callback_data: bytes | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        callback = self.next_callback_data
        data["next_callback_data"] = _callback_text(callback)
        data["next_callback_data_hex"] = callback.hex() if callback else None
        return data


@dataclass(frozen=True)
class MovieSourcePage:
    query: str
    response_text: str | None
    results: list[MovieSourceResult]
    pagination: PaginationInfo

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "response_text": self.response_text,
            "results": [result.to_dict() for result in self.results],
            "pagination": self.pagination.to_dict(),
        }


@dataclass(frozen=True)
class SearchConstraints:
    """Explicit constraints applied to parsed source results."""

    title_query: str | None = None
    episode: str | None = None
    max_size_mb: float | None = None
    min_quality: str | None = None
    max_quality: str | None = None


@dataclass(frozen=True)
class SelectionOutcome:
    """The deterministic result of applying constraints and selecting one source item."""

    selected: MovieSourceResult | None
    matching_count: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.to_dict() if self.selected else None,
            "matching_count": self.matching_count,
            "reason": self.reason,
        }


_QUALITY_HEIGHTS = {"480p": 480, "720p": 720, "1080p": 1080, "2160p": 2160, "4k": 2160}
_EPISODE_PATTERN = re.compile(r"\bS(\d{1,2})\s*E(\d{1,2})\b|\b(\d{1,2})\s*x\s*(\d{1,2})\b", re.IGNORECASE)


def _button_text(button: Any) -> str:
    return str(getattr(button, "text", "") or "").strip()


def _button_data(button: Any) -> bytes | None:
    data = getattr(button, "data", None)
    if isinstance(data, bytes):
        return data
    return None


def _callback_text(data: bytes | None) -> str | None:
    if not data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _is_pagination_button(text: str) -> bool:
    return "next" in text.casefold() and _PAGE_PATTERN.search(text) is not None


def parse_size_mb(raw_text: str) -> float | None:
    """Extract an explicit KB/MB/GB size and normalize it to megabytes."""
    match = _SIZE_PATTERN.search(raw_text)
    if not match:
        return None

    value = float(match.group(1))
    unit = match.group(2).upper()
    if unit == "KB":
        return value / 1024
    if unit == "GB":
        return value * 1024
    return value


def parse_result_button(button: Any) -> MovieSourceResult:
    """Parse only explicit metadata from an inline result button."""
    raw_text = _button_text(button)
    year_match = _YEAR_PATTERN.search(raw_text)
    quality_match = _QUALITY_PATTERN.search(raw_text)

    title = None
    if year_match:
        # The source's known result format places a title before its year.
        # Without that clear delimiter, keeping title=None is safer than guessing.
        text_without_size = _SIZE_PATTERN.sub("", raw_text, count=1)
        title_year_match = _YEAR_PATTERN.search(text_without_size)
        prefix = text_without_size[: title_year_match.start()].strip(" -|[]")
        title = prefix or None

    return MovieSourceResult(
        raw_text=raw_text,
        title=title,
        year=int(year_match.group(1)) if year_match else None,
        size_mb=parse_size_mb(raw_text),
        quality=quality_match.group(1).lower() if quality_match else None,
        callback_data=_button_data(button),
    )


def parse_pagination(buttons: list[list[Any]]) -> PaginationInfo:
    """Detect, but do not activate, the source bot's next-page control."""
    for row in buttons:
        for button in row:
            text = _button_text(button)
            if not _is_pagination_button(text):
                continue
            page_match = _PAGE_PATTERN.search(text)
            return PaginationInfo(
                current_page=int(page_match.group(1)) if page_match else None,
                total_pages=int(page_match.group(2)) if page_match else None,
                has_next_page=True,
                next_callback_data=_button_data(button),
            )

    return PaginationInfo(None, None, False, None)


def parse_search_response(query: str, response: Any) -> MovieSourcePage:
    """Turn a Telethon message into structured, source-neutral search data."""
    buttons = list(getattr(response, "buttons", None) or [])
    results = [
        parse_result_button(button)
        for row in buttons
        for button in row
        if not _is_pagination_button(_button_text(button))
    ]
    return MovieSourcePage(
        query=query,
        response_text=getattr(response, "message", None),
        results=results,
        pagination=parse_pagination(buttons),
    )


def _normalise_episode(value: str) -> str | None:
    match = _EPISODE_PATTERN.search(value)
    if not match:
        return None
    season, episode = match.group(1, 2) if match.group(1) else match.group(3, 4)
    return f"s{int(season):02d}e{int(episode):02d}"


def _normalise_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _quality_height(quality: str | None) -> int | None:
    if not quality:
        return None
    return _QUALITY_HEIGHTS.get(quality.casefold())


def _matches_title(result: MovieSourceResult, title_query: str) -> bool:
    """Match a title phrase after removing an optional episode token from the query."""
    title_without_episode = _EPISODE_PATTERN.sub("", title_query)
    query_text = _normalise_text(title_without_episode)
    if not query_text:
        return True
    return query_text in _normalise_text(result.title or result.raw_text)


def validate_constraints(constraints: SearchConstraints) -> None:
    """Reject invalid explicit constraints before examining any results."""
    if constraints.max_size_mb is not None and constraints.max_size_mb < 0:
        raise ValueError("max_size_mb cannot be negative.")

    if constraints.episode and _normalise_episode(constraints.episode) is None:
        raise ValueError("episode must use S01E01 or 1x01 format.")

    minimum = _quality_height(constraints.min_quality)
    maximum = _quality_height(constraints.max_quality)
    if constraints.min_quality and minimum is None:
        raise ValueError(f"Unsupported minimum quality: {constraints.min_quality}")
    if constraints.max_quality and maximum is None:
        raise ValueError(f"Unsupported maximum quality: {constraints.max_quality}")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("min_quality cannot be higher than max_quality.")


def matches_constraints(result: MovieSourceResult, constraints: SearchConstraints) -> bool:
    """Return whether a result satisfies every explicit constraint."""
    if constraints.title_query and not _matches_title(result, constraints.title_query):
        return False

    if constraints.episode:
        requested_episode = _normalise_episode(constraints.episode)
        found_episode = _normalise_episode(result.raw_text)
        if not requested_episode or found_episode != requested_episode:
            return False

    if constraints.max_size_mb is not None:
        if result.size_mb is None or result.size_mb > constraints.max_size_mb:
            return False

    result_quality = _quality_height(result.quality)
    if constraints.min_quality:
        minimum = _quality_height(constraints.min_quality)
        if result_quality is None or result_quality < minimum:
            return False

    if constraints.max_quality:
        maximum = _quality_height(constraints.max_quality)
        if result_quality is None or result_quality > maximum:
            return False

    return True


def filter_results(
    results: list[MovieSourceResult], constraints: SearchConstraints
) -> list[MovieSourceResult]:
    """Filter parsed results without inferring missing source metadata."""
    validate_constraints(constraints)
    return [result for result in results if matches_constraints(result, constraints)]


def filter_pages(
    pages: list[MovieSourcePage], constraints: SearchConstraints
) -> list[MovieSourceResult]:
    """Filter the combined results from one or more retrieved pages."""
    return filter_results(
        [result for page in pages for result in page.results], constraints
    )


def select_result(
    results: list[MovieSourceResult], constraints: SearchConstraints
) -> SelectionOutcome:
    """Select the first constrained match, preserving the source bot's result order."""
    matches = filter_results(results, constraints)
    if not matches:
        return SelectionOutcome(
            selected=None,
            matching_count=0,
            reason="No source result matched the explicit constraints.",
        )

    return SelectionOutcome(
        selected=matches[0],
        matching_count=len(matches),
        reason="Selected the first matching result in source order.",
    )


def select_from_pages(
    pages: list[MovieSourcePage], constraints: SearchConstraints
) -> SelectionOutcome:
    """Select one matching result from all already retrieved pages."""
    return select_result(
        [result for page in pages for result in page.results], constraints
    )


def should_fetch_next_page(page: MovieSourcePage, pages_retrieved: int, max_pages: int) -> bool:
    """Return whether the caller explicitly allowed one more page request."""
    return (
        pages_retrieved < max_pages
        and page.pagination.has_next_page
        and page.pagination.next_callback_data is not None
    )


class MovieSourceClient:
    """A minimal, session-backed client for bounded source-bot searches."""

    def __init__(self, session_name: str = "cineagent") -> None:
        api_id_text = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.phone = os.getenv("TELEGRAM_PHONE")
        self.target_bot_username = os.getenv("TARGET_BOT_USERNAME")

        if not api_id_text or not self.api_hash or not self.phone:
            raise RuntimeError("TELEGRAM_API_ID, TELEGRAM_API_HASH, and TELEGRAM_PHONE must be set.")
        if not self.target_bot_username:
            raise RuntimeError("TARGET_BOT_USERNAME must be set.")

        self.client = TelegramClient(session_name, int(api_id_text), self.api_hash)

    async def search(self, query: str, timeout: float = 30) -> MovieSourcePage:
        """Search once, parse the first response page, and disconnect."""
        return (await self.search_pages(query, max_pages=1, timeout=timeout))[0]

    async def search_pages(
        self, query: str, max_pages: int = 1, timeout: float = 30
    ) -> list[MovieSourcePage]:
        """Search and retrieve at most ``max_pages`` source-bot result pages."""
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Search query cannot be empty.")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1.")

        await self.client.connect()
        try:
            if not await self.client.is_user_authorized():
                await self.client.start(phone=self.phone)

            bot = await self.client.get_entity(self.target_bot_username)
            async with self.client.conversation(bot) as conversation:
                await conversation.send_message(cleaned_query)
                response = await conversation.get_response(timeout=timeout)
                pages = [parse_search_response(cleaned_query, response)]

                while should_fetch_next_page(pages[-1], len(pages), max_pages):
                    callback_data = pages[-1].pagination.next_callback_data
                    await response.click(data=callback_data)
                    response = await conversation.get_edit(response, timeout=timeout)
                    pages.append(parse_search_response(cleaned_query, response))

            return pages
        finally:
            await self.client.disconnect()


async def _main() -> None:
    argument_parser = argparse.ArgumentParser(description="Search the authorized Telegram movie source.")
    argument_parser.add_argument("query", nargs="*", default=["Person of Interest S01E01"])
    argument_parser.add_argument("--max-pages", type=int, default=1)
    argument_parser.add_argument("--title")
    argument_parser.add_argument("--episode")
    argument_parser.add_argument("--max-size-mb", type=float)
    argument_parser.add_argument("--min-quality", choices=sorted(_QUALITY_HEIGHTS))
    argument_parser.add_argument("--max-quality", choices=sorted(_QUALITY_HEIGHTS))
    args = argument_parser.parse_args()

    query = " ".join(args.query)
    pages = await MovieSourceClient().search_pages(query, max_pages=args.max_pages)
    constraints = SearchConstraints(
        title_query=args.title,
        episode=args.episode,
        max_size_mb=args.max_size_mb,
        min_quality=args.min_quality,
        max_quality=args.max_quality,
    )
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(
        json.dumps(
            {
                "pages": [page.to_dict() for page in pages],
                "filtered_results": [result.to_dict() for result in filter_pages(pages, constraints)],
                "selection": select_from_pages(pages, constraints).to_dict(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
