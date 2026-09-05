from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("", include("apps.core.auth.urls")),
    path("templates/", include("apps.template.page_urls")),
    path("", include("apps.dashboard.urls")),
    path("inbox/", include("apps.emails.page_urls")),
    path("emails/", include("apps.emails.oauth_urls")),
    path("", include("apps.records.page_urls")),
    path("exports/", include("apps.exports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
