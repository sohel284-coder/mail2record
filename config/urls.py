from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("api/", include("apps.accounts.urls")),
    path("", include("apps.core.auth.urls")),
    path("templates/", include("apps.template.page_urls")),
    path("", include("apps.dashboard.urls")),
]
