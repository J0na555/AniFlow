from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods

from .models import UserAnime
from .api_services import get_frontend_dashboard_payload
from .api_services import get_recommendations_payload
from .api_services import get_releases_payload
from .api_services import get_resume_payload
from .api_services import search_anime_payload
from .api_services import sync_anilist_payload
from .api_services import update_status_payload
from .api_services import get_watchlist_payload
from .api_services import update_progress_payload


def _parse_positive_int(value: str, *, fallback: int, minimum: int = 1, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return min(max(parsed, minimum), maximum)


def _json_error(detail: str, code: str, *, status: int) -> JsonResponse:
    return JsonResponse({"detail": detail, "code": code}, status=status)


def _extract_progress(request) -> int | None:
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        progress = payload.get("progress")
    else:
        progress = request.POST.get("progress")

    try:
        parsed = int(progress)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


@login_required
@require_GET
def dashboard_api(request):
    return JsonResponse(get_frontend_dashboard_payload(request.user))


@login_required
@require_GET
def watchlist_api(request):
    status = (request.GET.get("status") or "").strip().lower() or None
    query = (request.GET.get("q") or "").strip()
    return JsonResponse(get_watchlist_payload(request.user, status=status, query=query))


@login_required
@require_GET
def resume_api(request):
    limit = _parse_positive_int(request.GET.get("limit"), fallback=10, maximum=50)
    return JsonResponse(get_resume_payload(request.user, limit=limit))


@login_required
@require_http_methods(["POST", "PATCH"])
def progress_api(request, anime_id: int):
    progress = _extract_progress(request)
    if progress is None:
        return _json_error("Invalid progress.", "invalid_progress", status=400)

    try:
        payload = update_progress_payload(
            request.user,
            anime_id=anime_id,
            progress=progress,
        )
    except UserAnime.DoesNotExist:
        return _json_error("Anime entry not found.", "not_found", status=404)
    return JsonResponse(payload)


@login_required
@require_http_methods(["POST"])
def sync_anilist_api(request):
    return JsonResponse(sync_anilist_payload(request.user))


@login_required
@require_GET
def anime_search_api(request):
    query = (request.GET.get("q") or "").strip()
    page = _parse_positive_int(request.GET.get("page"), fallback=1, minimum=1, maximum=10_000)
    page_size = _parse_positive_int(
        request.GET.get("page_size"), fallback=20, minimum=1, maximum=100
    )
    return JsonResponse(
        search_anime_payload(request.user, query=query, page=page, page_size=page_size)
    )


@login_required
@require_http_methods(["POST"])
def status_api(request, anime_id: int):
    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        status = (payload.get("status") or "").strip().lower()
    else:
        status = (request.POST.get("status") or "").strip().lower()

    if not status:
        return _json_error("Missing status.", "missing_status", status=400)

    try:
        payload = update_status_payload(request.user, anime_id=anime_id, status=status)
    except ValueError:
        return _json_error("Invalid status.", "invalid_status", status=400)
    except UserAnime.DoesNotExist:
        return _json_error("Anime entry not found.", "not_found", status=404)
    return JsonResponse(payload)


@login_required
@require_GET
def recommendations_api(request):
    return JsonResponse(get_recommendations_payload(request.user))


@login_required
@require_GET
def releases_api(request):
    return JsonResponse(get_releases_payload(request.user))
