from __future__ import annotations

from urllib.parse import urlparse

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from apps.anime.models import Anime, UserAnime
from apps.anime.services import add_to_library
from apps.anime.services import apply_progress_update, normalize_tracker_status
from apps.anime.services import update_user_anime_status
from apps.anime.services import WatchingLimitReached
from apps.productivity.services import enable_watching_limit_override
from apps.productivity.services import get_productivity_stats
from apps.productivity.services import get_watching_limit_state
from apps.recommendations.services import get_recommendations
from apps.releases.services import get_weekly_releases
from apps.streaming.models import AnimeStreamingMapping
from apps.streaming.models import StreamingSource
from apps.streaming.router import ordered_sources_for_user
from apps.streaming.router import resolve_streaming_route
from apps.streaming.sources import get_adapter_for_source
from apps.tracker.services import search_anime as tracker_search_anime
from apps.tracker.services import update_progress as tracker_update_progress
from apps.tracker.services import sync_user_list


def _build_dashboard_context(
    user,
    *,
    oob: bool = False,
    watching_limit_error: str = "",
) -> dict:
    entries = UserAnime.objects.filter(user=user).select_related("anime")
    watching = entries.filter(status="watching").order_by("-updated_at")
    completed = entries.filter(status="completed").order_by("-updated_at")
    watching_entries = list(watching)
    productivity_stats = get_productivity_stats(user, entries=entries)
    watching_limit = get_watching_limit_state(
        user,
        watching_count=len(watching_entries),
    )
    context = {
        "continue_watching": list(watching[:5]),
        "watching_entries": watching_entries,
        "completed_entries": list(completed),
        "productivity_stats": productivity_stats,
        "watching_limit": watching_limit,
        "watching_limit_error": watching_limit_error,
        "recommendations": get_recommendations(user, limit=6),
        "weekly_releases": get_weekly_releases(user, limit=6),
        "library_status_choices": UserAnime.STATUS_CHOICES,
    }
    if oob:
        context["oob"] = True
    return context


def dashboard(request):
    if not request.user.is_authenticated:
        return render(request, "anime/dashboard.html", {"unauthenticated": True})

    if not UserAnime.objects.filter(user=request.user).exists():
        sync_user_list(request.user)

    context = _build_dashboard_context(request.user)
    return render(request, "anime/dashboard.html", context)


def _confirmation_redirect(anime_id: int, source_id: int, next_episode: int):
    confirmation_url = reverse(
        "anime_confirm_mapping",
        kwargs={
            "anime_id": anime_id,
            "source_id": source_id,
        },
    )
    return redirect(f"{confirmation_url}?next_episode={next_episode}")


@login_required
def resume_anime(request, anime_id: int):
    user_anime = get_object_or_404(UserAnime, user=request.user, anime_id=anime_id)
    if user_anime.status in {"completed", "dropped"}:
        return HttpResponseBadRequest("This title is not active.")

    next_episode = user_anime.progress + 1
    route = resolve_streaming_route(request.user, user_anime.anime, next_episode)
    if route.needs_confirmation and route.source:
        return _confirmation_redirect(
            anime_id=user_anime.anime_id,
            source_id=route.source.id,
            next_episode=next_episode,
        )
    if route.url:
        return redirect(route.url)
    if route.search_url:
        return redirect(route.search_url)
    return HttpResponse("No streaming source available.", status=404)


def play_anime(request, anime_id: int):
    anime = get_object_or_404(Anime, id=anime_id)
    route = resolve_streaming_route(request.user, anime, next_episode=1)
    if route.needs_confirmation and route.source:
        return _confirmation_redirect(
            anime_id=anime.id,
            source_id=route.source.id,
            next_episode=1,
        )
    if route.url:
        return redirect(route.url)
    if route.search_url:
        return redirect(route.search_url)
    return HttpResponse("No streaming source available.", status=404)


@login_required
@require_POST
def update_progress(request, anime_id: int):
    user_anime = get_object_or_404(UserAnime, user=request.user, anime_id=anime_id)
    raw_progress = request.POST.get("progress", "").strip()
    if not raw_progress.isdigit():
        return HttpResponseBadRequest("Invalid progress.")

    progress = int(raw_progress)
    watching_limit = get_watching_limit_state(request.user)
    if user_anime.status == "planning" and progress > 0 and watching_limit.reached:
        warning_message = (
            "Watching limit reached. Override the limit before starting another title."
        )
        if request.headers.get("HX-Request") == "true":
            context = _build_dashboard_context(
                request.user,
                oob=True,
                watching_limit_error=warning_message,
            )
            return render(request, "anime/partials/dashboard_sections.html", context)
        return HttpResponseBadRequest(warning_message)

    tracker_response = tracker_update_progress(
        request.user, user_anime.anime.tracker_id, progress
    )
    tracker_status = normalize_tracker_status(tracker_response.get("status"))
    apply_progress_update(
        user_anime,
        tracker_response.get("progress", progress),
        tracker_status,
    )

    if request.headers.get("HX-Request") == "true":
        context = _build_dashboard_context(request.user, oob=True)
        response = render(request, "anime/partials/dashboard_sections.html", context)
        # Add a success toast
        toast_html = render(request, "partials/toast.html", {
            "id": "sync-success",
            "message": "AniList synced successfully!",
            "type": "success"
        }).content.decode("utf-8")
        
        # Append toast OOB
        response.content += f'<div id="toast-container" hx-swap-oob="beforeend">{toast_html}</div>'.encode("utf-8")
        return response

    return redirect("dashboard")


def _dashboard_referer_path(request) -> bool:
    """True when the HX Referer is the root dashboard (path ``/``)."""
    referer = request.META.get("HTTP_REFERER") or ""
    if not referer:
        return True
    path = urlparse(referer).path.rstrip("/")
    return path == ""


def _append_toast_oob(response: HttpResponse, request, *, toast_id: str, message: str) -> HttpResponse:
    toast_html = render(
        request,
        "partials/toast.html",
        {"id": toast_id, "message": message, "type": "success"},
    ).content.decode("utf-8")
    response.content += (
        f'<div id="toast-container" hx-swap-oob="beforeend">{toast_html}</div>'.encode("utf-8")
    )
    return response


@login_required
@require_POST
def update_status(request, anime_id: int):
    raw_status = (request.POST.get("status") or "").strip().lower()
    if not raw_status:
        return HttpResponseBadRequest("Missing status.")

    try:
        update_user_anime_status(request.user, anime_id=anime_id, status=raw_status)
    except ValueError:
        return HttpResponseBadRequest("Invalid status.")
    except WatchingLimitReached as exc:
        if request.headers.get("HX-Request") != "true":
            return HttpResponseBadRequest(str(exc))
        if _dashboard_referer_path(request):
            context = _build_dashboard_context(
                request.user,
                oob=True,
                watching_limit_error=str(exc),
            )
            return render(request, "anime/partials/dashboard_sections.html", context)
        response = HttpResponse(status=200)
        response["HX-Redirect"] = request.META.get("HTTP_REFERER") or reverse("dashboard")
        return response
    except UserAnime.DoesNotExist:
        return HttpResponseNotFound("Entry not found.")

    next_url = request.META.get("HTTP_REFERER") or reverse("dashboard")

    if request.headers.get("HX-Request") == "true":
        if not _dashboard_referer_path(request):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = next_url
            return response
        context = _build_dashboard_context(request.user, oob=True)
        response = render(request, "anime/partials/dashboard_sections.html", context)
        return _append_toast_oob(
            response,
            request,
            toast_id="status-updated",
            message="List status updated.",
        )

    return redirect(next_url)


@login_required
@require_POST
def sync_list(request):
    sync_user_list(request.user)
    if request.headers.get("HX-Request") == "true":
        context = _build_dashboard_context(request.user, oob=True)
        response = render(request, "anime/partials/dashboard_sections.html", context)
        # Add a success toast
        toast_html = render(request, "partials/toast.html", {
            "id": "sync-success",
            "message": "AniList synced successfully!",
            "type": "success"
        }).content.decode("utf-8")
        
        # Append toast OOB
        response.content += f'<div id="toast-container" hx-swap-oob="beforeend">{toast_html}</div>'.encode("utf-8")
        return response
    return redirect("dashboard")


@login_required
@require_POST
def ignore_watching_limit(request):
    enable_watching_limit_override(request.user)
    if request.headers.get("HX-Request") == "true":
        context = _build_dashboard_context(request.user, oob=True)
        response = render(request, "anime/partials/dashboard_sections.html", context)
        # Add a success toast
        toast_html = render(request, "partials/toast.html", {
            "id": "sync-success",
            "message": "AniList synced successfully!",
            "type": "success"
        }).content.decode("utf-8")
        
        # Append toast OOB
        response.content += f'<div id="toast-container" hx-swap-oob="beforeend">{toast_html}</div>'.encode("utf-8")
        return response
    return redirect("dashboard")


@require_http_methods(["GET", "POST"])
def confirm_streaming_mapping(request, anime_id: int, source_id: int):
    anime = get_object_or_404(Anime, id=anime_id)
    source = get_object_or_404(StreamingSource, id=source_id, is_active=True)
    mapping = get_object_or_404(
        AnimeStreamingMapping,
        anime=anime,
        source=source,
    )
    adapter = get_adapter_for_source(source)

    next_episode = request.GET.get("next_episode", "1").strip()
    if not next_episode.isdigit():
        next_episode = "1"
    next_episode_int = max(int(next_episode), 1)

    if request.method == "POST":
        mapping.verified = True
        mapping.save(update_fields=["verified", "updated_at"])
        return redirect(adapter.build_episode_url(mapping.source_identifier, next_episode_int))

    primary_title = anime.title_english or anime.title_romaji or anime.title_native or ""
    context = {
        "anime": anime,
        "source": source,
        "mapping": mapping,
        "next_episode": next_episode_int,
        "search_url": adapter.build_search_url(primary_title) if primary_title else None,
    }
    return render(request, "anime/confirm_mapping.html", context)


def _tracker_hits_not_in_library(user, query: str) -> list[dict]:
    """AniList search hits excluding titles already on the user's list."""
    if not query.strip():
        return []
    try:
        hits = tracker_search_anime(user, query)
    except Exception:
        return []

    owned_keys = {
        (e.anime.tracker_type, str(e.anime.tracker_id))
        for e in UserAnime.objects.filter(user=user).select_related("anime")
    }
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        tt = hit.get("tracker_type") or ""
        tid = str(hit.get("tracker_id") or "")
        if not tt or not tid:
            continue
        key = (tt, tid)
        if key in owned_keys or key in seen:
            continue
        seen.add(key)
        results.append(hit)
    return results


@login_required
@require_POST
def add_to_library_view(request):
    """HTMX: add an AniList hit from search (payload resolved via optional ``q``)."""
    if not getattr(request.user, "tracker_access_token", ""):
        return render(
            request,
            "anime/partials/_search_add_card.html",
            {"needs_tracker_connect": True},
        )

    tracker_id = (request.POST.get("tracker_id") or "").strip()
    status = (request.POST.get("status") or "").strip().lower()
    q = (request.POST.get("q") or "").strip()

    if not tracker_id or not status:
        return HttpResponseBadRequest("Missing tracker_id or status.")

    payload: dict | None = None
    if q:
        for hit in tracker_search_anime(request.user, q):
            if str(hit.get("tracker_id")) == tracker_id:
                payload = hit
                break

    template_ctx: dict = {"tracker_id": tracker_id, "search_query": q}

    try:
        entry = add_to_library(
            request.user,
            tracker_id=tracker_id,
            status=status,
            payload=payload,
        )
    except WatchingLimitReached as exc:
        template_ctx["error"] = str(exc)
        return render(request, "anime/partials/_search_add_card.html", template_ctx)
    except ValueError as exc:
        template_ctx["error"] = str(exc)
        return render(request, "anime/partials/_search_add_card.html", template_ctx)

    return render(
        request,
        "anime/partials/_search_add_card.html",
        {"added": True, "entry": entry, "search_query": q},
    )


def search_anime(request):
    query = request.GET.get("q", "").strip()
    results = []
    user_entries: dict[int, UserAnime] = {}
    if query:
        results = list(
            Anime.objects.filter(
                Q(title_english__icontains=query)
                | Q(title_romaji__icontains=query)
                | Q(title_native__icontains=query)
            )
            .order_by("title_english", "title_romaji")
            .distinct()[:15]
        )
        if request.user.is_authenticated and results:
            entries = UserAnime.objects.filter(
                user=request.user,
                anime__in=results,
            ).select_related("anime")
            user_entries = {entry.anime_id: entry for entry in entries}

    sources = (
        ordered_sources_for_user(request.user)
        if request.user.is_authenticated
        else list(StreamingSource.objects.filter(is_active=True).order_by("priority", "name"))
    )
    source_links = [
        {
            "source": source,
            "search_url": get_adapter_for_source(source).build_search_url(query)
            if query
            else "",
        }
        for source in sources
    ]

    tracker_results: list[dict] = []
    has_tracker_token = False
    if request.user.is_authenticated and query.strip():
        has_tracker_token = bool(getattr(request.user, "tracker_access_token", ""))
        if has_tracker_token:
            tracker_results = _tracker_hits_not_in_library(request.user, query)

    context = {
        "query": query,
        "results": results,
        "user_entries": user_entries,
        "source_links": source_links,
        "unauthenticated": not request.user.is_authenticated,
        "library_status_choices": UserAnime.STATUS_CHOICES
        if request.user.is_authenticated
        else [],
        "tracker_results": tracker_results,
        "has_tracker_token": has_tracker_token,
    }
    return render(request, "anime/search.html", context)


@login_required
def watching_list(request):
    entries = UserAnime.objects.filter(user=request.user, status="watching").select_related("anime").order_by("-updated_at")
    return render(
        request,
        "anime/watching.html",
        {
            "watching_entries": entries,
            "library_status_choices": UserAnime.STATUS_CHOICES,
        },
    )


@login_required
def completed_list(request):
    entries = UserAnime.objects.filter(user=request.user, status="completed").select_related("anime").order_by("-updated_at")
    return render(
        request,
        "anime/completed.html",
        {
            "completed_entries": entries,
            "library_status_choices": UserAnime.STATUS_CHOICES,
        },
    )


@login_required
def weekly_releases_page(request):
    releases = get_weekly_releases(request.user, limit=50)
    return render(request, "anime/weekly_releases.html", {"weekly_releases": releases})


@login_required
def recommendations_page(request):
    recommendations = get_recommendations(request.user, limit=50)
    return render(request, "anime/recommendations.html", {"recommendations": recommendations})


def health_check(request):
    """
    Health check endpoint for monitoring and cronjobs.
    Verifies that the application and database are responsive.
    """
    health_data = {
        "status": "healthy",
        "database": "connected",
    }
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as e:
        health_data["status"] = "unhealthy"
        health_data["database"] = f"error: {str(e)}"
        return JsonResponse(health_data, status=503)

    return JsonResponse(health_data)
