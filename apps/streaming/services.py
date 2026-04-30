from __future__ import annotations

from decimal import Decimal

from apps.anime.models import Anime
from apps.streaming.matcher import match_anime
from apps.streaming.models import AnimeStreamingMapping, StreamingSource
from apps.streaming.sources import StreamingSourceAdapter


def get_mapping(anime: Anime, source: StreamingSource) -> AnimeStreamingMapping | None:
    return AnimeStreamingMapping.objects.filter(anime=anime, source=source).first()


def get_or_create_mapping(
    anime: Anime,
    source: StreamingSource,
    adapter: StreamingSourceAdapter,
) -> tuple[AnimeStreamingMapping | None, bool]:
    existing = get_mapping(anime, source)
    if existing:
        return existing, False

    match = match_anime(anime, adapter)
    if not match:
        return None, False

    mapping = AnimeStreamingMapping.objects.create(
        anime=anime,
        source=source,
        source_identifier=match.candidate.slug,
        confidence_score=Decimal(str(round(match.score, 3))),
        verified=False,
    )
    return mapping, True
