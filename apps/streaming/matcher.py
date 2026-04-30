from __future__ import annotations

from rapidfuzz import fuzz

from apps.anime.models import Anime
from apps.streaming.sources.base_source import StreamingSourceAdapter
from apps.streaming.types import AnimeMetadata, StreamingCandidate, StreamingMatch


MATCH_THRESHOLD = 0.75


def build_metadata(anime: Anime) -> AnimeMetadata:
    return AnimeMetadata(
        title_romaji=anime.title_romaji or "",
        title_english=anime.title_english or "",
        title_native=anime.title_native or "",
        season_year=anime.season_year,
        episodes=anime.episodes,
        studio=anime.studio or "",
    )


def choose_query(metadata: AnimeMetadata) -> str:
    return metadata.primary_title or ""


def _title_score(metadata: AnimeMetadata, candidate: StreamingCandidate) -> float:
    if not candidate.title:
        return 0.0
    scores = []
    for title in (metadata.title_english, metadata.title_romaji, metadata.title_native):
        if title:
            scores.append(fuzz.token_sort_ratio(title, candidate.title))
    if not scores:
        return 0.0
    return max(scores) / 100.0


def _year_score(metadata: AnimeMetadata, candidate: StreamingCandidate) -> float:
    if metadata.season_year is None or candidate.year is None:
        return 0.5
    return 1.0 if metadata.season_year == candidate.year else 0.0


def _episode_score(metadata: AnimeMetadata, candidate: StreamingCandidate) -> float:
    if metadata.episodes is None or candidate.episodes is None:
        return 0.5
    return 1.0 if abs(metadata.episodes - candidate.episodes) <= 1 else 0.0


def _studio_score(metadata: AnimeMetadata, candidate: StreamingCandidate) -> float:
    if not metadata.studio or not candidate.studio:
        return 0.5
    return fuzz.token_sort_ratio(metadata.studio, candidate.studio) / 100.0


def score_candidate(metadata: AnimeMetadata, candidate: StreamingCandidate) -> float:
    title_weight = 0.7
    year_weight = 0.1
    episode_weight = 0.1
    studio_weight = 0.1
    return (
        _title_score(metadata, candidate) * title_weight
        + _year_score(metadata, candidate) * year_weight
        + _episode_score(metadata, candidate) * episode_weight
        + _studio_score(metadata, candidate) * studio_weight
    )


def match_anime(anime: Anime, adapter: StreamingSourceAdapter) -> StreamingMatch | None:
    metadata = build_metadata(anime)
    query = choose_query(metadata)
    if not query:
        return None
    candidates = adapter.search(query)
    if not candidates:
        return None
    best_candidate = max(candidates, key=lambda candidate: score_candidate(metadata, candidate))
    best_score = score_candidate(metadata, best_candidate)
    if best_score < MATCH_THRESHOLD:
        return None
    return StreamingMatch(candidate=best_candidate, score=best_score)
