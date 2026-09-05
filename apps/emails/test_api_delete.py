"""DELETE /api/emails/<id>/ — blocked once a record exists, attachment files
are cleaned up from storage when the email (and its attachments) are deleted.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.emails.models import Attachment, Email
from apps.extraction.models import Extraction
from apps.records.models import Record
from apps.template.models import Template

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user("emp", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_delete_unprocessed_email_succeeds(client, user):
    email = Email.objects.create(user=user, message_id="m1", subject="Newsletter")
    resp = client.delete(f"/api/emails/{email.id}/")
    assert resp.status_code == 204
    assert not Email.objects.filter(id=email.id).exists()


def test_delete_is_blocked_once_a_record_exists(client, user):
    tpl = Template.objects.create(user=user, name="PO Info")
    email = Email.objects.create(user=user, message_id="m2", subject="Booking")
    extraction = Extraction.objects.create(
        email=email, template=tpl, status=Extraction.Status.SUCCESS
    )
    Record.objects.create(user=user, email=email, template=tpl, extraction=extraction, data={})

    resp = client.delete(f"/api/emails/{email.id}/")
    assert resp.status_code == 409
    assert Email.objects.filter(id=email.id).exists()


def test_delete_removes_attachment_file_from_storage(client, user):
    email = Email.objects.create(user=user, message_id="m3", subject="With attachment")
    attachment = Attachment.objects.create(
        email=email, filename="order.csv", content_type="text/csv", size=3,
        file=SimpleUploadedFile("order.csv", b"a,b"),
    )
    storage = attachment.file.storage
    stored_name = attachment.file.name
    assert storage.exists(stored_name)

    resp = client.delete(f"/api/emails/{email.id}/")
    assert resp.status_code == 204
    assert not storage.exists(stored_name)


def test_user_cannot_delete_another_users_email(user):
    other = get_user_model().objects.create_user("other", password="x")
    email = Email.objects.create(user=other, message_id="m4", subject="Not yours")

    c = APIClient()
    c.force_authenticate(user)
    resp = c.delete(f"/api/emails/{email.id}/")
    assert resp.status_code == 404
    assert Email.objects.filter(id=email.id).exists()
