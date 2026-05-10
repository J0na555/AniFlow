from django.contrib import admin
from django.templatetags.static import static
from django.urls import include, path
from django.views.generic.base import RedirectView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=static("anime/branding/favicon.ico"), permanent=False)),
    path("admin/", admin.site.urls),
    path("auth/", include("apps.users.urls")),
    path("api/", include("apps.anime.api_urls")),
    path("", include("apps.anime.urls")),
]
