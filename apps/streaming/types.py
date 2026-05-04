from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnimeMetadata:
    title_romaji: str
    title_english: str
    title_native: str
    season_year: int | None
    episodes: int | None
    studio: str

    @property
    def primary_title(self) -> str:
        return self.title_english or self.title_romaji or self.title_native


@dataclass(frozen=True)
class StreamingCandidate:
    title: str
    slug: str
    year: int | None = None
    episodes: int | None = None
    studio: str = ""


@dataclass(frozen=True)
class StreamingMatch:
    candidate: StreamingCandidate
    score: float
    needs_confirmation: bool
