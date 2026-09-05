"""Template API: delete is allowed only when the template has no records."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.emails.models import Email
from apps.extraction.models import Extraction
from apps.records.models import Record
from apps.template.models import Template, TemplateField

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user("emp", password="x")


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def template(user):
    tpl = Template.objects.create(user=user, name="CSB")
    TemplateField.objects.create(
        template=tpl, name="po_number", label="PO Number", data_type="string",
        required=True, display_order=1,
    )
    return tpl


def test_delete_template_with_no_records(client, template):
    resp = client.delete(f"/api/templates/{template.id}/")
    assert resp.status_code == 204
    assert not Template.objects.filter(id=template.id).exists()


def test_delete_template_with_records_is_blocked(client, template, user):
    email = Email.objects.create(
        user=user, message_id="m1", subject="DI / ABA", sender="v@x.test",
    )
    extraction = Extraction.objects.create(
        email=email, template=template, status=Extraction.Status.SUCCESS,
        confidence="1/1 required fields",
    )
    Record.objects.create(
        user=user, email=email, template=template, extraction=extraction,
        data={"po_number": "PO-1"}, status=Record.Status.APPROVED,
    )

    resp = client.delete(f"/api/templates/{template.id}/")
    assert resp.status_code == 409
    assert Template.objects.filter(id=template.id).exists()
    assert Record.objects.filter(template=template).exists()


def test_user_cannot_delete_other_users_template(template):
    other = get_user_model().objects.create_user("other", password="x")
    c = APIClient()
    c.force_authenticate(other)
    assert c.delete(f"/api/templates/{template.id}/").status_code == 404
    assert Template.objects.filter(id=template.id).exists()
