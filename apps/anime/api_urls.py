from django.urls import path

from . import api_views

urlpatterns = [
    path("dashboard/", api_views.dashboard_api, name="api_dashboard"),
    path("anime/search/", api_views.anime_search_api, name="api_anime_search"),
    path("sync/anilist/", api_views.sync_anilist_api, name="api_sync_anilist"),
    path("watchlist/", api_views.watchlist_api, name="api_watchlist"),
    path("resume/", api_views.resume_api, name="api_resume"),
    path("anime/<int:anime_id>/progress/", api_views.progress_api, name="api_progress"),
    path("library/<int:anime_id>/progress/", api_views.progress_api, name="api_library_progress"),
    path("library/<int:anime_id>/status/", api_views.status_api, name="api_library_status"),
    path(
        "recommendations/",
        api_views.recommendations_api,
        name="api_recommendations",
    ),
    path("releases/", api_views.releases_api, name="api_releases"),
]
