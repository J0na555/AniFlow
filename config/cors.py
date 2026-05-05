from __future__ import annotations

import re
from typing import Iterable


class SimpleCorsMiddleware:
    """Minimal CORS support for API routes and local frontend development."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "OPTIONS" and request.path.startswith("/api/"):
            response = self._options_response(request)
        else:
            response = self.get_response(request)
        return self._apply_cors_headers(request, response)

    def _options_response(self, request):
        from django.http import HttpResponse

        response = HttpResponse(status=204)
        requested_headers = request.headers.get("Access-Control-Request-Headers", "")
        response["Access-Control-Allow-Headers"] = requested_headers or "Content-Type, Authorization"
        response["Access-Control-Allow-Methods"] = "GET, POST, PATCH, PUT, DELETE, OPTIONS"
        return response

    def _apply_cors_headers(self, request, response):
        origin = request.headers.get("Origin", "")
        if not origin:
            return response

        from django.conf import settings

        allowed_origins: Iterable[str] = (
            getattr(request, "cors_allowed_origins", None)
            or getattr(settings, "CORS_ALLOWED_ORIGINS", [])
        )
        # Strip a trailing slash from the configured origin AND from the
        # incoming Origin header — the spec says the header has no slash, but
        # being defensive here saves a lot of head-scratching when somebody
        # pastes "https://app.example.com/" into the env var.
        normalized_origin = origin.rstrip("/")
        normalized_allowed = {value.rstrip("/") for value in allowed_origins}

        is_allowed = normalized_origin in normalized_allowed
        if not is_allowed:
            for pattern in getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", []):
                try:
                    if re.fullmatch(pattern, normalized_origin):
                        is_allowed = True
                        break
                except re.error:
                    continue

        if is_allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Vary"] = "Origin"
        return response
