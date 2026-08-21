"""Root URL configuration for Mail2Record."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("dashboard.urls")),
]
