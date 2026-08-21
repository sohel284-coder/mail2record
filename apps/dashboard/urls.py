from django.urls import path
from apps.dashboard.views import index, settings_page

app_name = "dashboard"

urlpatterns = [
    path("", index, name="index"),
    path("settings/", settings_page, name="settings"),
]