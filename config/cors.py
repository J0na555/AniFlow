from __future__ import annotations

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
        allowed_origins: Iterable[str] = getattr(request, "cors_allowed_origins", None) or []
        if not allowed_origins:
            from django.conf import settings

            allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])

        if origin and origin in set(allowed_origins):
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Credentials"] = "true"
            response["Vary"] = "Origin"
        return response
