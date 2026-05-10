from __future__ import annotations

from dataclasses import dataclass

from apps.anime.models import Anime
from apps.streaming.models import StreamingSource
from apps.streaming.services import get_or_create_mapping
from apps.streaming.sources import get_adapter_for_source
from apps.streaming.types import AnimeMetadata


@dataclass(frozen=True)
class StreamingRoute:
    url: str | None
    source: StreamingSource | None
    needs_confirmation: bool
    search_url: str | None = None


def ordered_sources_for_user(user) -> list[StreamingSource]:
    sources = list(
        StreamingSource.objects.filter(is_active=True).order_by("priority", "name")
    )
    preferred = getattr(getattr(user, "settings", None), "preferred_source", None)
    if preferred and preferred in sources:
        sources.remove(preferred)
        sources.insert(0, preferred)
    return sources


def resolve_streaming_route(user, anime: Anime, next_episode: int) -> StreamingRoute:
    search_url: str | None = None
    for source in ordered_sources_for_user(user):
        adapter = get_adapter_for_source(source)
        mapping, _ = get_or_create_mapping(anime, source, adapter)
        if mapping:
            url = adapter.build_episode_url(mapping.source_identifier, next_episode)
            return StreamingRoute(
                url=url,
                source=source,
                needs_confirmation=not mapping.verified,
            )
        if search_url is None:
            query = AnimeMetadata(
                title_romaji=anime.title_romaji or "",
                title_english=anime.title_english or "",
                title_native=anime.title_native or "",
                season_year=anime.season_year,
                episodes=anime.episodes,
                studio=anime.studio or "",
            ).primary_title
            if query:
                search_url = adapter.build_search_url(query)

    return StreamingRoute(url=None, source=None, needs_confirmation=False, search_url=search_url)
