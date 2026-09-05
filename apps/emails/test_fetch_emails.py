"""fetch_emails: iterates connected mailboxes, records sync status, saves
new emails + attachments, skips duplicates."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.emails.models import Email, EmailAccount

pytestmark = pytest.mark.django_db


class _FakeProvider:
    def __init__(self, messages):
        self._messages = messages

    def fetch_new_messages(self, max_results=25):
        return self._messages


@pytest.fixture
def user():
    return get_user_model().objects.create_user("alice", password="x")


@pytest.fixture
def account(user):
    acc = EmailAccount(
        user=user, provider=EmailAccount.Provider.IMAP,
        email_address="alice@example.com", is_active=True,
        config={"host": "imap.example.com", "port": 993},
    )
    acc.credentials = {"password": "app-pw"}
    acc.save()
    return acc


def _msg(mid, subject="Hi", attachments=None):
    return {
        "message_id": mid, "sender": "vendor@x.test", "recipient": "alice@example.com",
        "subject": subject, "body_text": "body", "body_html": "", "received_at": timezone.now(),
        "source": "imap", "attachments": attachments or [],
    }


def test_no_mailbox_connected_is_a_no_op():
    out = StringIO()
    call_command("fetch_emails", stdout=out)
    assert "No mailbox to sync" in out.getvalue()


def test_syncs_new_messages_and_records_ok_status(account, monkeypatch):
    monkeypatch.setattr(
        "apps.emails.management.commands.fetch_emails.get_email_provider",
        lambda acc: _FakeProvider([
            _msg("m-1", attachments=[
                {"filename": "po.csv", "content_type": "text/csv", "size": 3, "content": b"a,b"},
            ]),
            _msg("m-2"),
        ]),
    )
    call_command("fetch_emails", stdout=StringIO())

    assert Email.objects.filter(user=account.user).count() == 2
    assert Email.objects.get(message_id="m-1").attachments.count() == 1
    account.refresh_from_db()
    assert account.last_sync_status == EmailAccount.SyncStatus.OK
    assert account.last_sync_at is not None


def test_duplicates_are_skipped(account, monkeypatch):
    Email.objects.create(user=account.user, message_id="m-1", subject="already here")
    monkeypatch.setattr(
        "apps.emails.management.commands.fetch_emails.get_email_provider",
        lambda acc: _FakeProvider([_msg("m-1"), _msg("m-2")]),
    )
    call_command("fetch_emails", stdout=StringIO())
    assert Email.objects.filter(user=account.user).count() == 2  # m-1 unchanged, m-2 new


def test_provider_error_is_recorded_not_raised(account, monkeypatch):
    class _Boom:
        def fetch_new_messages(self, max_results=25):
            raise RuntimeError("IMAP login failed")

    monkeypatch.setattr(
        "apps.emails.management.commands.fetch_emails.get_email_provider",
        lambda acc: _Boom(),
    )
    call_command("fetch_emails", stdout=StringIO(), stderr=StringIO())
    account.refresh_from_db()
    assert account.last_sync_status == EmailAccount.SyncStatus.ERROR
    assert "IMAP login failed" in account.last_sync_error
