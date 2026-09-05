"""Mailbox-connection API: status never leaks credentials; IMAP connect tests
the login before saving; one mailbox per user; disconnect."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.emails import api_views
from apps.emails.models import EmailAccount

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user("emp", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    c.user = user
    return c


class _OkProvider:
    def __init__(self, account):
        self.account = account

    def test_connection(self):
        return None


class _FailProvider:
    def __init__(self, account):
        self.account = account

    def test_connection(self):
        raise ConnectionError("authentication failed")


def test_status_when_no_mailbox(client):
    resp = client.get("/api/email-account/")
    assert resp.status_code == 200
    assert resp.json() == {"connected": False, "suggested_imap": None}


def test_status_suggests_imap_host_from_address(client):
    resp = client.get("/api/email-account/?email_address=someone@outlook.com")
    assert resp.json()["suggested_imap"] == {"host": "outlook.office365.com", "port": 993}


def test_imap_connect_tests_then_saves_and_never_returns_credentials(client, monkeypatch):
    monkeypatch.setattr(api_views, "get_email_provider", _OkProvider)
    resp = client.post(
        "/api/email-account/imap/",
        {"email_address": "me@outlook.com", "password": "app-specific-pw"},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["connected"] is True and body["provider"] == "imap"
    assert body["imap_host"] == "outlook.office365.com"
    assert "password" not in str(body) and "credentials" not in str(body)

    account = EmailAccount.objects.get(user=client.user)
    assert account.credentials == {"password": "app-specific-pw"}  # stored, encrypted
    assert "app-specific-pw" not in account.credentials_encrypted


def test_imap_connect_rejects_bad_credentials_without_saving(client, monkeypatch):
    monkeypatch.setattr(api_views, "get_email_provider", _FailProvider)
    resp = client.post(
        "/api/email-account/imap/",
        {"email_address": "me@outlook.com", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 400
    assert "authentication failed" in resp.json()["detail"]
    assert not EmailAccount.objects.filter(user=client.user).exists()


def test_imap_connect_replaces_any_existing_mailbox(client, monkeypatch):
    EmailAccount.objects.create(
        user=client.user, provider="gmail", email_address="old@gmail.com",
    )
    monkeypatch.setattr(api_views, "get_email_provider", _OkProvider)
    client.post(
        "/api/email-account/imap/",
        {"email_address": "new@outlook.com", "password": "pw"},
        format="json",
    )
    accounts = EmailAccount.objects.filter(user=client.user)
    assert accounts.count() == 1
    assert accounts.first().email_address == "new@outlook.com"


def test_disconnect(client):
    EmailAccount.objects.create(user=client.user, provider="gmail", email_address="x@gmail.com")
    assert client.delete("/api/email-account/").status_code == 204
    assert not EmailAccount.objects.filter(user=client.user).exists()


def test_another_user_mailbox_is_not_visible(client):
    other = get_user_model().objects.create_user("other", password="x")
    EmailAccount.objects.create(user=other, provider="gmail", email_address="other@gmail.com")
    assert client.get("/api/email-account/").json()["connected"] is False
