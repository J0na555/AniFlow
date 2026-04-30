from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect

from apps.anime.models import UserAnime
from apps.streaming.router import resolve_streaming_route


@login_required
def resume_anime(request, anime_id: int):
    user_anime = get_object_or_404(UserAnime, user=request.user, anime_id=anime_id)
    if user_anime.status in {"completed", "dropped"}:
        return HttpResponseBadRequest("This title is not active.")

    next_episode = user_anime.progress + 1
    route = resolve_streaming_route(request.user, user_anime.anime, next_episode)
    if route.url:
        return redirect(route.url)
    if route.search_url:
        return redirect(route.search_url)
    return HttpResponse("No streaming source available.", status=404)
