from django.urls import path

from apps.emails.views import email_detail, inbox

app_name = "emails_ui"

urlpatterns = [
    path("", inbox, name="inbox"),
    path("<int:pk>/", email_detail, name="detail"),
]
