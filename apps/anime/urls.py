from django.urls import path

from . import views

urlpatterns = [
    path("anime/<int:anime_id>/resume/", views.resume_anime, name="anime_resume"),
]
