"""fetch_emails: --user is required and validated (exists, active)."""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_user_is_required():
    with pytest.raises(CommandError):
        call_command("fetch_emails")


def test_unknown_user_raises_with_available_list():
    get_user_model().objects.create_user("alice", password="x")

    with pytest.raises(CommandError, match="No user named"):
        call_command("fetch_emails", user="ghost")


def test_inactive_user_is_rejected():
    get_user_model().objects.create_user("alice", password="x", is_active=False)

    with pytest.raises(CommandError, match="inactive"):
        call_command("fetch_emails", user="alice")
