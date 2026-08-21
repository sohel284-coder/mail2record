from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import DetectColumnsView, TemplateViewSet

router = DefaultRouter()
router.register("templates", TemplateViewSet, basename="template")

app_name = "template_api"

urlpatterns = [
    path(
        "templates/detect-columns/",
        DetectColumnsView.as_view(),
        name="detect-columns",
    ),
] + router.urls
