from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote, urlsplit

import httpx

from apps.streaming.types import StreamingCandidate
from .base_source import StreamingSourceAdapter


class AniWavesSourceAdapter(StreamingSourceAdapter):
    source_names = ("aniwaves", "ani waves")

    _SEARCH_TIMEOUT_SECONDS = 10.0
    _USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    def search(self, query: str) -> list[StreamingCandidate]:
        if not query:
            return []

        try:
            response = httpx.get(
                self.build_search_url(query),
                headers={"User-Agent": self._USER_AGENT},
                timeout=self._SEARCH_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        return self._extract_candidates(response.text)

    def build_episode_url(self, slug: str, episode: int) -> str:
        normalized_slug = self._normalize_slug(slug)
        # AniWaves series pages reliably use /watch/{slug}; episode selection
        # happens on that page.
        path = f"watch/{normalized_slug}"
        return f"{self.source.base_url.rstrip('/')}/{path.lstrip('/')}"

    def build_search_url(self, query: str) -> str:
        if self.source.search_url_template and "/filter?" in self.source.search_url_template:
            return self.source.search_url_template.format(query=quote(query))
        base = self.source.base_url.rstrip('/')
        return f"{base}/filter?keyword={quote(query)}"

    @classmethod
    def _extract_candidates(cls, html: str) -> list[StreamingCandidate]:
        candidates: list[StreamingCandidate] = []
        seen_slugs: set[str] = set()

        for match in re.finditer(
            r'<a\b[^>]+href="(?P<href>[^"]*?/watch/[^"]+)"[^>]*>(?P<title>.*?)</a>',
            html,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            href = match.group("href")
            slug = cls._normalize_slug(href)
            if not slug or slug in seen_slugs:
                continue

            title = cls._strip_html(match.group("title") or "")
            if not title:
                title = cls._title_from_slug(slug)
            if not title:
                continue

            year = cls._extract_year_from_context(html, match.start())

            candidates.append(
                StreamingCandidate(
                    title=title,
                    slug=slug,
                    year=year,
                )
            )
            seen_slugs.add(slug)

        return candidates

    @classmethod
    def _extract_year_from_context(cls, html: str, match_pos: int) -> int | None:
        context = html[max(0, match_pos - 300):match_pos + 300]

        match = re.search(r"Released:\s*(\d{4})", context, re.IGNORECASE)
        if match:
            return int(match.group(1))

        match = re.search(r"\((\d{4})\)", context)
        if match:
            return int(match.group(1))

        return None

    @staticmethod
    def _strip_html(raw_text: str) -> str:
        text_without_tags = re.sub(r"<[^>]*>", "", raw_text)
        collapsed_whitespace = re.sub(r"\s+", " ", text_without_tags)
        return unescape(collapsed_whitespace).strip()

    @staticmethod
    def _title_from_slug(slug: str) -> str:
        # Convert "kaguya-sama-...-77991" into a fuzzy-matchable title.
        normalized = re.sub(r"-\d+$", "", slug.strip().lower())
        normalized = normalized.replace("-", " ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    @staticmethod
    def _normalize_slug(raw_slug: str) -> str:
        if raw_slug.startswith("http://") or raw_slug.startswith("https://"):
            raw_slug = urlsplit(raw_slug).path

        raw_slug = raw_slug.strip("/")

        if "watch/" in raw_slug:
            raw_slug = raw_slug.split("watch/", 1)[1]

        if "/ep-" in raw_slug:
            raw_slug = raw_slug.split("/ep-", 1)[0]

        return raw_slug.strip("/")