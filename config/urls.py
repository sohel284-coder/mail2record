from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("", include("apps.core.auth.urls")),
    path("templates/", include("apps.template.page_urls")),
    path("", include("apps.dashboard.urls")),
    path("inbox/", include("apps.emails.page_urls")),
]
