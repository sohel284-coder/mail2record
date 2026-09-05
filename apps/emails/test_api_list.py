"""GET /api/emails/ — ordering. received_at is null on some rows (manually
created / legacy); those must not float to the top ahead of genuinely recent
emails just because Postgres sorts NULL first on a bare DESC order."""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.emails.models import Email

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    user = get_user_model().objects.create_user("emp", password="x")
    c = APIClient()
    c.force_authenticate(user)
    c.user = user
    return c


def test_recent_email_sorts_above_an_older_one_with_no_received_at(client):
    now = timezone.now()

    # An old test/manually-created row that never got a received_at (the
    # realistic case this fix targets) — backdate its created_at too, since
    # auto_now_add would otherwise stamp it as "just now".
    no_date = Email.objects.create(
        user=client.user, message_id="no-date-at-all", subject="No received_at set",
    )
    Email.objects.filter(pk=no_date.pk).update(created_at=now - timezone.timedelta(days=30))

    recent = Email.objects.create(
        user=client.user, message_id="new-with-date", subject="Genuinely recent",
        received_at=now,
    )

    resp = client.get("/api/emails/")
    subjects = [row["subject"] for row in resp.json()["results"]]

    assert subjects[0] == recent.subject
    assert subjects.index(recent.subject) < subjects.index(no_date.subject)
