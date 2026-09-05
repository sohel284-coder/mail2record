"""POST /api/emails/<id>/extract/ — template selection + optional attachment override."""

import io

import pandas as pd
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.emails.models import Attachment, Email
from apps.extraction import free_text_extractor
from apps.template.models import Template, TemplateField

pytestmark = pytest.mark.django_db


class StubProvider:
    def extract(self, prompt):
        return {}, None


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
    tpl = Template.objects.create(user=user, name="PO Info")
    TemplateField.objects.create(
        template=tpl, name="po_number", label="PO Number", data_type="string",
        required=True, display_order=0,
    )
    return tpl


@pytest.fixture
def email(user):
    return Email.objects.create(
        user=user, message_id="m-extract-1", subject="Booking",
        body_text="PO No: PO-1", is_processed=False,
    )


def test_extract_requires_template(client, email, monkeypatch):
    monkeypatch.setattr(free_text_extractor, "get_provider", lambda: StubProvider())
    resp = client.post(f"/api/emails/{email.id}/extract/", {}, format="json")
    assert resp.status_code == 400


def test_extract_rejects_unknown_template(client, email, monkeypatch):
    monkeypatch.setattr(free_text_extractor, "get_provider", lambda: StubProvider())
    resp = client.post(f"/api/emails/{email.id}/extract/", {"template": 999}, format="json")
    assert resp.status_code == 404


def test_extract_rejects_unknown_attachment(client, email, template, monkeypatch):
    monkeypatch.setattr(free_text_extractor, "get_provider", lambda: StubProvider())
    resp = client.post(
        f"/api/emails/{email.id}/extract/",
        {"template": template.id, "attachment": 999},
        format="json",
    )
    assert resp.status_code == 404
    assert "Attachment" in resp.json()["detail"]


def test_extract_with_selected_attachment_reports_which_file_was_used(
    client, email, template, monkeypatch
):
    monkeypatch.setattr(free_text_extractor, "get_provider", lambda: StubProvider())

    df = pd.DataFrame([["PO-77"]], columns=["PO Number"])
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    attachment = Attachment.objects.create(
        email=email, filename="po.csv", content_type="text/csv",
        size=len(buf.getvalue()),
        file=SimpleUploadedFile("po.csv", buf.getvalue(), content_type="text/csv"),
    )

    resp = client.post(
        f"/api/emails/{email.id}/extract/",
        {"template": template.id, "attachment": attachment.id},
        format="json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["used_attachment"] == "po.csv"
    assert body["data"]["po_number"] == "PO-77"
