from django.urls import path

from . import views

urlpatterns = [
    path("anilist/login/", views.anilist_login, name="anilist_login"),
    path("anilist/callback/", views.anilist_callback, name="anilist_callback"),
    path("anilist/complete/", views.anilist_complete, name="anilist_complete"),
]
