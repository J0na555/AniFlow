from __future__ import annotations

import json
from functools import wraps

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods

from .services import WatchingLimitReached
from .models import UserAnime
from .api_services import add_to_library_payload
from .api_services import get_frontend_dashboard_payload
from .api_services import get_recommendations_payload
from .api_services import get_releases_payload
from .api_services import get_resume_payload
from .api_services import search_anime_payload
from .api_services import sync_anilist_payload
from .api_services import update_status_payload
from .api_services import get_watchlist_payload
from .api_services import update_progress_payload


def api_login_required(view_func):
    """JSON-aware ``@login_required`` for SPA endpoints.

    Django's stock ``login_required`` returns a 302 to ``LOGIN_URL`` when the
    caller isn't authenticated, which an SPA fetch can't sensibly interpret —
    the redirect is followed silently and the SPA sees an HTML page or 404
    instead of a clear "not authenticated" signal. Return a JSON 401 instead.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"detail": "Authentication required.", "code": "not_authenticated"},
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


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


@require_GET
def me_api(request):
    """Return the current session's user (or ``authenticated: false``).

    Unlike the other API endpoints, this one *never* returns 401: it always
    returns 200 with a small JSON payload describing whether the caller is
    logged in. The SPA polls this on load to decide between the dashboard UI
    and the login modal.
    """
    user = request.user
    if not user.is_authenticated:
        return JsonResponse({"authenticated": False})
    tracker_type = getattr(user, "tracker_type", "") or ""
    tracker_user_id = getattr(user, "tracker_user_id", "") or ""
    return JsonResponse(
        {
            "authenticated": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "tracker_type": tracker_type,
                "tracker_user_id": tracker_user_id,
            },
        }
    )


@api_login_required
@require_GET
def dashboard_api(request):
    return JsonResponse(get_frontend_dashboard_payload(request.user))


@api_login_required
@require_GET
def watchlist_api(request):
    status = (request.GET.get("status") or "").strip().lower() or None
    query = (request.GET.get("q") or "").strip()
    return JsonResponse(get_watchlist_payload(request.user, status=status, query=query))


@api_login_required
@require_GET
def resume_api(request):
    limit = _parse_positive_int(request.GET.get("limit"), fallback=10, maximum=50)
    return JsonResponse(get_resume_payload(request.user, limit=limit))


@api_login_required
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


@api_login_required
@require_http_methods(["POST"])
def sync_anilist_api(request):
    return JsonResponse(sync_anilist_payload(request.user))


@api_login_required
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


@api_login_required
@require_http_methods(["POST"])
def add_to_library_api(request):
    """Add a tracker title to the caller's library.

    Body: ``{"tracker_id": str, "status": str, "progress"?: int, "score"?: float}``.

    Mirrors the error envelopes used by ``progress_api`` / ``status_api`` so
    the SPA can share a single error handler.
    """
    if not getattr(request.user, "tracker_access_token", ""):
        return _json_error(
            "Connect your tracker before adding titles.",
            "tracker_not_connected",
            status=403,
        )

    if request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return _json_error("Invalid JSON body.", "invalid_body", status=400)
    else:
        body = request.POST

    tracker_id = str(body.get("tracker_id") or "").strip()
    if not tracker_id:
        return _json_error("Missing tracker_id.", "missing_tracker_id", status=400)

    status = str(body.get("status") or "").strip().lower()
    if not status:
        return _json_error("Missing status.", "missing_status", status=400)

    raw_progress = body.get("progress")
    if raw_progress is None or raw_progress == "":
        progress = 0
    else:
        try:
            progress = int(raw_progress)
        except (TypeError, ValueError):
            return _json_error("Invalid progress.", "invalid_progress", status=400)
        if progress < 0:
            return _json_error("Invalid progress.", "invalid_progress", status=400)

    raw_score = body.get("score")
    if raw_score in (None, ""):
        score: float | None = None
    else:
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return _json_error("Invalid score.", "invalid_score", status=400)

    try:
        payload = add_to_library_payload(
            request.user,
            tracker_id=tracker_id,
            status=status,
            progress=progress,
            score=score,
        )
    except WatchingLimitReached as exc:
        return _json_error(str(exc), "watching_limit_reached", status=409)
    except ValueError as exc:
        # ``add_to_library`` raises ``ValueError`` for both an unknown
        # ``status`` and a missing local ``Anime`` row (it converts the
        # underlying ``Anime.DoesNotExist`` itself). Disambiguate by message
        # so the SPA can react with the right toast.
        if "tracker_id" in str(exc):
            return _json_error(str(exc), "not_found", status=404)
        return _json_error("Invalid status.", "invalid_status", status=400)
    return JsonResponse(payload, status=201)


@api_login_required
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
    except WatchingLimitReached as exc:
        return _json_error(str(exc), "watching_limit_reached", status=409)
    except UserAnime.DoesNotExist:
        return _json_error("Anime entry not found.", "not_found", status=404)
    return JsonResponse(payload)


@api_login_required
@require_GET
def recommendations_api(request):
    return JsonResponse(get_recommendations_payload(request.user))


@api_login_required
@require_GET
def releases_api(request):
    return JsonResponse(get_releases_payload(request.user))
