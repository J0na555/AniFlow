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
    path("sync/", views.sync_list, name="sync_list"),
    path(
        "settings/watching-limit/ignore/",
        views.ignore_watching_limit,
        name="ignore_watching_limit",
    ),
    path("search/", views.search_anime, name="anime_search"),
    path("health/", views.health_check, name="health_check"),
]
