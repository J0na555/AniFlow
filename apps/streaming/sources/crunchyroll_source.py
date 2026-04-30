from __future__ import annotations

from apps.streaming.types import StreamingCandidate

from .base_source import StreamingSourceAdapter


class CrunchyrollSourceAdapter(StreamingSourceAdapter):
    def search(self, query: str) -> list[StreamingCandidate]:
        # Search-only fallback until a real Crunchyroll parser is added.
        return []

    def build_episode_url(self, slug: str, episode: int) -> str:
        if slug.startswith("http://") or slug.startswith("https://"):
            return slug
        if not self.source.episode_pattern:
            return f"{self.source.base_url.rstrip('/')}/{slug.lstrip('/')}"
        path = self.source.episode_pattern.format(slug=slug, episode=episode)
        return f"{self.source.base_url.rstrip('/')}/{path.lstrip('/')}"
