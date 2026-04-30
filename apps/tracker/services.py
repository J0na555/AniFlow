from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.anime.models import UserAnime
from apps.anime.services import upsert_from_tracker_payload

from .adapters import AniListAdapter, TrackerAdapter

TRACKER_TYPE_ANILIST = "anilist"


def get_adapter_for_user(user) -> TrackerAdapter:
    tracker_type = user.tracker_type or TRACKER_TYPE_ANILIST
    if tracker_type == TRACKER_TYPE_ANILIST:
        return AniListAdapter()
    raise ValueError(f"Unsupported tracker type: {tracker_type}")


def sync_user_list(user) -> list[UserAnime]:
    adapter = get_adapter_for_user(user)
    entries = adapter.get_user_list(user)
    synced: list[UserAnime] = []
    with transaction.atomic():
        for entry in entries:
            anime = upsert_from_tracker_payload(entry)
            user_anime, _ = UserAnime.objects.update_or_create(
                user=user,
                anime=anime,
                defaults={
                    "status": entry.get("status") or "planning",
                    "progress": entry.get("progress") or 0,
                    "score": entry.get("score"),
                    "start_date": entry.get("start_date"),
                    "completed_date": entry.get("completed_date"),
                },
            )
            synced.append(user_anime)
    return synced


def update_progress(user, tracker_id: str, progress: int) -> dict[str, Any]:
    adapter = get_adapter_for_user(user)
    response = adapter.update_progress(user, tracker_id, progress)
    return response
