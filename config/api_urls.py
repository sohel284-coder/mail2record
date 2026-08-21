"""API URL routes (namespace: api)."""

from django.urls import path

from config import api_views

app_name = "api"

urlpatterns = [
    path("health/", api_views.HealthView.as_view(), name="health"),
]
