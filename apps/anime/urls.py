from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("anime/<int:anime_id>/resume/", views.resume_anime, name="anime_resume"),
    path("anime/<int:anime_id>/play/", views.play_anime, name="anime_play"),
    path(
        "anime/<int:anime_id>/mapping/<int:source_id>/confirm/",
        views.confirm_streaming_mapping,
        name="anime_confirm_mapping",
    ),
    path(
        "anime/<int:anime_id>/progress/",
        views.update_progress,
        name="anime_progress",
    ),
    path(
        "anime/<int:anime_id>/status/",
        views.update_status,
        name="anime_status",
    ),
    path("sync/", views.sync_list, name="sync_list"),
    path(
        "settings/watching-limit/ignore/",
        views.ignore_watching_limit,
        name="ignore_watching_limit",
    ),
    path("search/", views.search_anime, name="anime_search"),
    path("anime/add/", views.add_to_library_view, name="anime_add_to_library"),
    path("watching/", views.watching_list, name="watching_list"),
    path("completed/", views.completed_list, name="completed_list"),
    path("releases/", views.weekly_releases_page, name="weekly_releases"),
    path("recommendations/", views.recommendations_page, name="recommendations"),
    path("health/", views.health_check, name="health_check"),
]
