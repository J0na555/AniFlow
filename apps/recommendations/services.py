from __future__ import annotations

from apps.tracker.services import get_recommendations as tracker_get_recommendations


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

    return {"items": items, "message": ""}
