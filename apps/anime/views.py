from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods

from apps.anime.models import Anime, UserAnime
from apps.anime.services import apply_progress_update, normalize_tracker_status
from apps.productivity.services import enable_watching_limit_override
from apps.productivity.services import get_productivity_stats
from apps.productivity.services import get_watching_limit_state
from apps.streaming.models import AnimeStreamingMapping
from apps.streaming.models import StreamingSource
from apps.streaming.router import resolve_streaming_route
from apps.streaming.sources import get_adapter_for_source
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
    planning = entries.filter(status="planning").order_by(
        "anime__title_english", "anime__title_romaji"
    )
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
        "planning_entries": list(planning),
        "completed_entries": list(completed),
        "productivity_stats": productivity_stats,
        "watching_limit": watching_limit,
        "watching_limit_error": watching_limit_error,
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
        return render(request, "anime/partials/dashboard_sections.html", context)

    return redirect("dashboard")


@login_required
@require_POST
def sync_list(request):
    sync_user_list(request.user)
    if request.headers.get("HX-Request") == "true":
        context = _build_dashboard_context(request.user, oob=True)
        return render(request, "anime/partials/dashboard_sections.html", context)
    return redirect("dashboard")


@login_required
@require_POST
def ignore_watching_limit(request):
    enable_watching_limit_override(request.user)
    if request.headers.get("HX-Request") == "true":
        context = _build_dashboard_context(request.user, oob=True)
        return render(request, "anime/partials/dashboard_sections.html", context)
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

    sources = list(StreamingSource.objects.filter(is_active=True).order_by("priority"))
    source_links = [
        {
            "source": source,
            "search_url": get_adapter_for_source(source).build_search_url(query)
            if query
            else "",
        }
        for source in sources
    ]

    context = {
        "query": query,
        "results": results,
        "user_entries": user_entries,
        "source_links": source_links,
        "unauthenticated": not request.user.is_authenticated,
    }
    return render(request, "anime/search.html", context)
