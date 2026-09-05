from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_views import (
    EmailAccountTestView,
    EmailAccountView,
    EmailViewSet,
    ImapConnectView,
)

router = DefaultRouter()
router.register("emails", EmailViewSet, basename="email")

app_name = "emails_api"
urlpatterns = [
    path("email-account/", EmailAccountView.as_view(), name="email-account"),
    path("email-account/imap/", ImapConnectView.as_view(), name="email-account-imap"),
    path("email-account/test/", EmailAccountTestView.as_view(), name="email-account-test"),
] + router.urls
