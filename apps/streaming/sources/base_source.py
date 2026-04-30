from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import quote

from apps.streaming.models import StreamingSource
from apps.streaming.types import StreamingCandidate


class StreamingSourceAdapter(ABC):
    def __init__(self, source: StreamingSource) -> None:
        self.source = source

    @abstractmethod
    def search(self, query: str) -> list[StreamingCandidate]:
        raise NotImplementedError

    @abstractmethod
    def build_episode_url(self, slug: str, episode: int) -> str:
        raise NotImplementedError

    def build_search_url(self, query: str) -> str:
        return self.source.search_url_template.format(query=quote(query))
