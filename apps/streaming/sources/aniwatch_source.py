from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote, urlsplit

import httpx

from apps.streaming.types import StreamingCandidate

from .base_source import StreamingSourceAdapter


class AniWatchSourceAdapter(StreamingSourceAdapter):
    """Adapter for jp-animenities.com (branded as "AniWatch")."""

    source_names = (
        "jp animenities",
        "jp-animenities",
        "aniwatch",
        "ani watch",
    )

    _SEARCH_TIMEOUT_SECONDS = 10.0
    _USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # Card wrappers used on the search results page. The "featured-card" grid
    # holds the primary matches while "anime-card" holds secondary matches.
    _CARD_BLOCK_PATTERN = re.compile(
        r'<div\s+class="(?:featured-card|anime-card)"[^>]*'
        r'data-qtip-link="(?P<link>[^"]+)"'
        r'(?P<body>[\s\S]*?)'
        r'(?=<div\s+class="(?:featured-card|anime-card)"|<div\s+class="card-qtip"|</main>|</body>|\Z)',
        re.IGNORECASE,
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
        base = self.source.base_url.rstrip("/")

        if self.source.episode_pattern:
            path = self.source.episode_pattern.format(
                slug=normalized_slug,
                episode=episode,
            )
        else:
            # jp-animenities doesn't expose stable per-episode URLs; the title
            # page is the canonical landing spot for play/resume.
            path = f"title/{normalized_slug}"

        return f"{base}/{path.lstrip('/')}"

    def build_search_url(self, query: str) -> str:
        if self.source.search_url_template:
            return self.source.search_url_template.format(query=quote(query))
        base = self.source.base_url.rstrip("/")
        return f"{base}/search/?q={quote(query)}"

    @classmethod
    def _extract_candidates(cls, html: str) -> list[StreamingCandidate]:
        candidates: list[StreamingCandidate] = []
        seen_slugs: set[str] = set()

        for match in cls._CARD_BLOCK_PATTERN.finditer(html):
            link = match.group("link")
            slug = cls._normalize_slug(link)
            if not slug or slug in seen_slugs:
                continue

            body = match.group("body")
            title = cls._extract_title(body) or cls._title_from_slug(slug)
            if not title:
                continue

            candidates.append(
                StreamingCandidate(
                    title=title,
                    slug=slug,
                    year=cls._extract_year(body),
                    episodes=cls._extract_episodes(body),
                )
            )
            seen_slugs.add(slug)

        return candidates

    @classmethod
    def _extract_title(cls, body: str) -> str:
        # Prefer the structured English title attribute when available.
        attr_match = re.search(r'data-title-en="([^"]+)"', body, flags=re.IGNORECASE)
        if attr_match:
            title = cls._clean_text(attr_match.group(1))
            if title:
                return title

        anchor_match = re.search(
            r'<a[^>]+title="([^"]+)"',
            body,
            flags=re.IGNORECASE,
        )
        if anchor_match:
            title = cls._clean_text(anchor_match.group(1))
            if title:
                return title

        text_match = re.search(
            r'class="[^"]*(?:featured-card-title|anime-card-title)[^"]*"[^>]*>(?P<title>[\s\S]*?)</',
            body,
            flags=re.IGNORECASE,
        )
        if text_match:
            return cls._strip_html(text_match.group("title"))

        return ""

    @staticmethod
    def _extract_year(body: str) -> int | None:
        match = re.search(
            r'class="[^"]*badge-year[^"]*"[^>]*>\s*(\d{4})\s*<',
            body,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_episodes(body: str) -> int | None:
        match = re.search(
            r'class="[^"]*badge-episodes[^"]*"[^>]*>\s*(?:Ep\s*)?(\d+)\s*<',
            body,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        return unescape(re.sub(r"\s+", " ", raw_text)).strip()

    @classmethod
    def _strip_html(cls, raw_text: str) -> str:
        return cls._clean_text(re.sub(r"<[^>]*>", "", raw_text))

    @staticmethod
    def _title_from_slug(slug: str) -> str:
        normalized = re.sub(r"-\d+$", "", slug.strip().lower())
        normalized = normalized.replace("-", " ")
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _normalize_slug(raw_slug: str) -> str:
        normalized = raw_slug.strip()
        if normalized.startswith(("http://", "https://")):
            normalized = urlsplit(normalized).path

        normalized = normalized.strip("/")
        if "title/" in normalized:
            normalized = normalized.split("title/", 1)[1]

        # Strip any trailing /season/N or /episode/N suffix.
        normalized = re.split(r"/(?:season|episode)/", normalized, maxsplit=1)[0]
        return normalized.strip("/")
