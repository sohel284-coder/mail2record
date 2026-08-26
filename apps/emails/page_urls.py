from django.urls import path
from apps.emails.views import inbox

app_name = "emails_ui"

urlpatterns = [
    path("", inbox, name="inbox"),
]