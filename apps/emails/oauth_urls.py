from django.urls import path

from . import oauth_views

app_name = "emails_oauth"

urlpatterns = [
    path("oauth/gmail/start/", oauth_views.gmail_oauth_start, name="gmail_start"),
    path("oauth/gmail/callback/", oauth_views.gmail_oauth_callback, name="gmail_callback"),
]
