from __future__ import annotations

from apps.streaming.types import StreamingCandidate

from .base_source import StreamingSourceAdapter


class TemplateSourceAdapter(StreamingSourceAdapter):
    def search(self, query: str) -> list[StreamingCandidate]:
        return []

    def build_episode_url(self, slug: str, episode: int) -> str:
        path = self.source.episode_pattern.format(slug=slug, episode=episode)
        return f"{self.source.base_url.rstrip('/')}/{path.lstrip('/')}"

