from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse

from apps.tracker.adapters.anilist_adapter import ANILIST_API_URL
from apps.tracker.services import TRACKER_TYPE_ANILIST, sync_user_list

from .models import UserSettings

ANILIST_AUTHORIZE_URL = "https://anilist.co/api/v2/oauth/authorize"
ANILIST_TOKEN_URL = "https://anilist.co/api/v2/oauth/token"

VIEWER_QUERY = """
query Viewer {
  Viewer {
    id
    name
  }
}
"""


def _get_anilist_config() -> tuple[str, str, str]:
    client_id = getattr(settings, "ANILIST_CLIENT_ID", "")
    client_secret = getattr(settings, "ANILIST_CLIENT_SECRET", "")
    redirect_uri = getattr(settings, "ANILIST_REDIRECT_URI", "")
    if not (client_id and client_secret and redirect_uri):
        raise ImproperlyConfigured("AniList OAuth env vars are not configured.")
    return client_id, client_secret, redirect_uri


def _fetch_viewer(access_token: str) -> dict:
    response = httpx.post(
        ANILIST_API_URL,
        json={"query": VIEWER_QUERY},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise ValueError(payload["errors"])
    return payload["data"]["Viewer"]


def _unique_username(base: str) -> str:
    User = get_user_model()
    sanitized = "".join(ch for ch in base if ch.isalnum() or ch == "_").lower()
    sanitized = sanitized[:150] or "anilist_user"
    candidate = sanitized
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{sanitized}_{suffix}"
        candidate = candidate[:150]
    return candidate


def anilist_login(request: HttpRequest) -> HttpResponse:
    client_id, _, redirect_uri = _get_anilist_config()
    state = secrets.token_urlsafe(16)
    request.session["anilist_oauth_state"] = state
    params = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
    )
    return redirect(f"{ANILIST_AUTHORIZE_URL}?{params}")


def anilist_callback(request: HttpRequest) -> HttpResponse:
    oauth_error = request.GET.get("error")
    if oauth_error:
        return HttpResponseBadRequest(
            f"AniList authorization error: {oauth_error}"
        )

    expected_state = request.session.get("anilist_oauth_state", "")
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")
    if not code or not state or state != expected_state:
        msg = "Invalid OAuth response."
        if settings.DEBUG:
            if not expected_state:
                msg += (
                    " No session state (session cookie missing or wrong site). "
                    "Use the same host for the whole flow (localhost vs 127.0.0.1), "
                    "and set COOKIE_SECURE=0 when using http://."
                )
            elif not code:
                msg += " Missing authorization code."
            elif state != expected_state:
                msg += " State mismatch (retry login, avoid duplicate callback)."
        return HttpResponseBadRequest(msg)

    request.session.pop("anilist_oauth_state", None)

    client_id, client_secret, redirect_uri = _get_anilist_config()
    token_response = httpx.post(
        ANILIST_TOKEN_URL,
        json={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=30.0,
    )
    token_response.raise_for_status()
    token_payload = token_response.json()
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token") or ""
    if not access_token:
        return HttpResponseBadRequest("AniList token exchange failed.")

    viewer = _fetch_viewer(access_token)
    tracker_user_id = str(viewer["id"])
    viewer_name = viewer.get("name") or "AniListUser"

    User = get_user_model()
    if request.user.is_authenticated:
        user = request.user
    else:
        user = User.objects.filter(
            tracker_type=TRACKER_TYPE_ANILIST,
            tracker_user_id=tracker_user_id,
        ).first()
        if not user:
            username = _unique_username(viewer_name)
            user = User.objects.create_user(username=username)
            user.set_unusable_password()

    user.tracker_type = TRACKER_TYPE_ANILIST
    user.tracker_user_id = tracker_user_id
    user.tracker_access_token = access_token
    user.tracker_refresh_token = refresh_token
    user.save()

    UserSettings.objects.get_or_create(user=user)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    sync_user_list(user)
    return redirect(reverse("anilist_complete"))


def anilist_complete(request: HttpRequest) -> HttpResponse:
    return HttpResponse(
        "AniList connected and list synced. You can close this tab."
    )
