from __future__ import annotations

from apps.anime.services import upsert_from_tracker_payload
from apps.tracker.services import get_recommendations as tracker_get_recommendations


def _serialize_recommendation(user, item: dict) -> dict:
    anime = upsert_from_tracker_payload(
        {
            "tracker_type": getattr(user, "tracker_type", "") or "anilist",
            **item,
        }
    )
    return {
        **item,
        "anime_id": anime.id,
    }


def get_recommendations(user, *, limit: int = 8) -> dict:
    try:
        items = tracker_get_recommendations(user, limit=limit)
    except Exception:
        return {
            "items": [],
            "message": "Could not load recommendations from AniList right now.",
        }

    if not items:
        return {
            "items": [],
            "message": "No recommendations are available from AniList yet.",
        }

    return {"items": [_serialize_recommendation(user, item) for item in items], "message": ""}
