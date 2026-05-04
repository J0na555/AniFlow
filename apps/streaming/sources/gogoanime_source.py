from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlsplit

import httpx

from apps.streaming.types import StreamingCandidate

from .base_source import StreamingSourceAdapter


class GogoanimeSourceAdapter(StreamingSourceAdapter):
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
        if normalized_slug.startswith("category/"):
            normalized_slug = normalized_slug.removeprefix("category/")

        if self.source.episode_pattern:
            path = self.source.episode_pattern.format(
                slug=normalized_slug,
                episode=episode,
            )
        else:
            path = f"{normalized_slug}-episode-{episode}"
        return f"{self.source.base_url.rstrip('/')}/{path.lstrip('/')}"

    @classmethod
    def _extract_candidates(cls, html: str) -> list[StreamingCandidate]:
        candidates: list[StreamingCandidate] = []
        seen_slugs: set[str] = set()
        for block in re.findall(r"<li\b[^>]*>.*?</li>", html, flags=re.DOTALL | re.IGNORECASE):
            anchor = re.search(
                r'<a[^>]+href="(?P<href>[^"]*?/category/[^"]+)"[^>]*>(?P<title>.*?)</a>',
                block,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if not anchor:
                continue

            slug = cls._normalize_slug(anchor.group("href"))
            if not slug or slug in seen_slugs:
                continue

            title = cls._strip_html(anchor.group("title"))
            if not title:
                continue

            year = cls._extract_year(block)
            candidates.append(
                StreamingCandidate(
                    title=title,
                    slug=slug,
                    year=year,
                )
            )
            seen_slugs.add(slug)

        return candidates

    @staticmethod
    def _strip_html(raw_text: str) -> str:
        text_without_tags = re.sub(r"<[^>]*>", "", raw_text)
        collapsed_whitespace = re.sub(r"\s+", " ", text_without_tags)
        return unescape(collapsed_whitespace).strip()

    @staticmethod
    def _extract_year(text: str) -> int | None:
        release = re.search(
            r"Released:\s*(?P<year>\d{4})",
            text,
            flags=re.IGNORECASE,
        )
        if not release:
            return None
        return int(release.group("year"))

    @staticmethod
    def _normalize_slug(raw_slug: str) -> str:
        normalized = raw_slug.strip()
        if normalized.startswith("http://") or normalized.startswith("https://"):
            normalized = urlsplit(normalized).path

        normalized = normalized.strip("/")
        if "category/" in normalized:
            normalized = normalized.split("category/", 1)[1]
        return normalized.strip("/")
