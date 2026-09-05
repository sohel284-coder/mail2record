"""Records API: edit-draft / approve / reject transitions and export flattening."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.emails.models import Email
from apps.exports.exporters import build_table, get_records
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
def draft(user):
    tpl = Template.objects.create(user=user, name="Delivery Instruction")
    for i, (n, dt, req) in enumerate(
        [("order_no", "string", True), ("total_cartons", "integer", True),
         ("buyer_name", "string", True)]
    ):
        TemplateField.objects.create(
            template=tpl, name=n, label=n.title(), data_type=dt,
            required=req, display_order=i,
        )
    email = Email.objects.create(
        user=user, message_id="m1", subject="DI / ABA", sender="v@x.test",
    )
    extraction = Extraction.objects.create(
        email=email, template=tpl, status=Extraction.Status.SUCCESS,
        confidence="3/3 required fields",
    )
    return Record.objects.create(
        user=user, email=email, template=tpl, extraction=extraction,
        data={"order_no": "ORD-1", "total_cartons": 420, "buyer_name": "ABA"},
        status=Record.Status.DRAFT,
    )


def test_list_and_review_indicator(client, draft):
    resp = client.get("/api/records/")
    assert resp.status_code == 200
    row = resp.json()["results"][0]
    assert row["review"]["ready"] is True
    assert row["confidence"] == "3/3 required fields"
    assert [f["name"] for f in row["field_schema"]] == ["order_no", "total_cartons", "buyer_name"]


def test_patch_updates_data_of_draft(client, draft):
    resp = client.patch(
        f"/api/records/{draft.id}/",
        {"data": {"order_no": "ORD-1", "total_cartons": 999, "buyer_name": "ABA FASHIONS LTD"}},
        format="json",
    )
    assert resp.status_code == 200
    draft.refresh_from_db()
    assert draft.data["total_cartons"] == 999
    assert draft.data["buyer_name"] == "ABA FASHIONS LTD"


def test_approve_sets_approver_and_blocks_further_edits(client, draft, user):
    resp = client.post(f"/api/records/{draft.id}/approve/")
    assert resp.status_code == 200
    draft.refresh_from_db()
    assert draft.status == Record.Status.APPROVED
    assert draft.approved_by == user
    assert draft.approved_at is not None

    # second approve -> conflict
    assert client.post(f"/api/records/{draft.id}/approve/").status_code == 409
    # edit after approve -> rejected
    assert client.patch(
        f"/api/records/{draft.id}/", {"data": {}}, format="json"
    ).status_code == 400


def test_reject(client, draft):
    assert client.post(f"/api/records/{draft.id}/reject/").status_code == 200
    draft.refresh_from_db()
    assert draft.status == Record.Status.REJECTED


def test_user_cannot_see_other_users_records(draft):
    other = get_user_model().objects.create_user("other", password="x")
    c = APIClient()
    c.force_authenticate(other)
    assert c.get(f"/api/records/{draft.id}/").status_code == 404


def test_export_table_flattens_json_data(user, draft):
    headers, rows = build_table(get_records(user, status="DRAFT"))
    assert "Order_No" in headers  # TemplateField.label
    assert headers[:3] == ["record_id", "template", "status"]
    assert len(rows) == 1
    assert "ORD-1" in [str(c) for c in rows[0]]
    assert 420 in rows[0]
