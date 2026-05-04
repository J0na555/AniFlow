from django.urls import path

from . import api_views

urlpatterns = [
    path("dashboard/", api_views.dashboard_api, name="api_dashboard"),
    path("watchlist/", api_views.watchlist_api, name="api_watchlist"),
    path("resume/", api_views.resume_api, name="api_resume"),
    path("anime/<int:anime_id>/progress/", api_views.progress_api, name="api_progress"),
    path(
        "recommendations/",
        api_views.recommendations_api,
        name="api_recommendations",
    ),
    path("releases/", api_views.releases_api, name="api_releases"),
]
