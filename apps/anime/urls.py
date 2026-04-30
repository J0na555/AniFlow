from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("anime/<int:anime_id>/resume/", views.resume_anime, name="anime_resume"),
    path("anime/<int:anime_id>/play/", views.play_anime, name="anime_play"),
    path(
        "anime/<int:anime_id>/progress/",
        views.update_progress,
        name="anime_progress",
    ),
    path("sync/", views.sync_list, name="sync_list"),
    path("search/", views.search_anime, name="anime_search"),
]
