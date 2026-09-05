"""Gmail OAuth views.

- Hidden by default (GMAIL_OAUTH_ENABLED=False) — the views 404.
- When enabled, the start view must stash BOTH the state and the PKCE
  code_verifier in the session, or the callback's token exchange fails with
  'Missing code verifier' (regression).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    user = get_user_model().objects.create_user("emp", password="x")
    c = Client()
    c.force_login(user)
    return c


def test_oauth_is_404_when_disabled(client):
    assert client.get("/emails/oauth/gmail/start/").status_code == 404
    assert client.get("/emails/oauth/gmail/callback/").status_code == 404


@override_settings(GMAIL_OAUTH_ENABLED=True)
def test_start_redirects_to_google_and_stashes_state_and_verifier(client):
    resp = client.get("/emails/oauth/gmail/start/")

    assert resp.status_code == 302
    assert resp["Location"].startswith("https://accounts.google.com/")
    assert "code_challenge=" in resp["Location"]

    session = client.session
    assert session.get("gmail_oauth_state")
    verifier = session.get("gmail_oauth_verifier")
    assert verifier and len(verifier) == 128


@override_settings(GMAIL_OAUTH_ENABLED=True)
def test_callback_with_google_error_shows_a_message_not_a_crash(client):
    resp = client.get("/emails/oauth/gmail/callback/?error=access_denied", follow=False)
    assert resp.status_code == 302
    assert resp["Location"].endswith("/settings/")


def test_settings_page_hides_connect_gmail_button_by_default(client):
    body = client.get("/settings/").content.decode()
    assert "Connect a mailbox" in body
    assert "Connect Gmail with OAuth" not in body


@override_settings(GMAIL_OAUTH_ENABLED=True)
def test_settings_page_shows_connect_gmail_button_when_enabled(client):
    body = client.get("/settings/").content.decode()
    assert "Connect Gmail with OAuth" in body
