"""Pipeline tests — merge of deterministic table parsing + focused AI free-text.

The AI provider is stubbed so these run offline and deterministically.
"""

import io

import pandas as pd
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.emails.models import Attachment, Email
from apps.extraction import free_text_extractor
from apps.extraction.models import Extraction
from apps.extraction.pipeline import run_extraction
from apps.records.models import Record
from apps.template.models import Template, TemplateField

pytestmark = pytest.mark.django_db


class StubProvider:
    def __init__(self, payload):
        self.payload = payload

    def extract(self, prompt):
        return dict(self.payload), None


class FailingProvider:
    def extract(self, prompt):
        return None, "Model did not return valid JSON"


@pytest.fixture
def user():
    return get_user_model().objects.create_user("emp", password="x")


@pytest.fixture
def template(user):
    tpl = Template.objects.create(user=user, name="Delivery Instruction")
    specs = [
        ("order_no", "string", True, False),
        ("cps_id", "string", True, False),
        ("style_name", "string", True, False),
        ("total_cartons", "integer", True, False),
        ("buyer_name", "string", True, True),
        ("delivery_date", "date", True, True),
        ("delivery_warehouse", "string", True, True),
    ]
    for i, (name, dtype, req, ft) in enumerate(specs):
        TemplateField.objects.create(
            template=tpl, name=name, label=name.replace("_", " ").title(),
            data_type=dtype, required=req, is_free_text=ft, display_order=i,
        )
    return tpl


def _make_email(user, **kw):
    defaults = dict(
        user=user, message_id=f"msg-{Email.objects.count()}",
        subject="Delivery Instruction / ABA FASHIONS LTD", sender="ops@vendor.test",
        body_text="", body_html="",
    )
    defaults.update(kw)
    return Email.objects.create(**defaults)


COLUMNAR_HTML = """
<p>Please arrange delivery for ABA FASHIONS LTD. Cargo must reach the
Chittagong Warehouse by 25-08-2026 16:00.</p>
<table>
  <tr><th>Order No</th><th>CPS ID</th><th>Style Name</th><th>Total Cartons</th></tr>
  <tr><td>ORD-2793757</td><td>CPS-88213</td><td>Mens Crew Tee</td><td>420</td></tr>
</table>
"""


def test_merges_table_and_free_text(user, template, monkeypatch):
    monkeypatch.setattr(
        free_text_extractor, "get_provider",
        lambda: StubProvider({
            "buyer_name": "ABA FASHIONS LTD",
            "delivery_date": "2026-08-25",
            "delivery_warehouse": "Chittagong Warehouse",
        }),
    )
    email = _make_email(user, body_html=COLUMNAR_HTML)
    record = run_extraction(email, template)

    assert record is not None
    assert record.status == Record.Status.DRAFT
    # table-derived
    assert record.data["order_no"] == "ORD-2793757"
    assert record.data["cps_id"] == "CPS-88213"
    assert record.data["style_name"] == "Mens Crew Tee"
    assert record.data["total_cartons"] == 420
    # free-text-derived
    assert record.data["buyer_name"] == "ABA FASHIONS LTD"
    assert record.data["delivery_date"] == "2026-08-25"
    assert record.data["delivery_warehouse"] == "Chittagong Warehouse"

    email.refresh_from_db()
    assert email.is_processed is True
    assert record.extraction.status == Extraction.Status.SUCCESS
    assert record.extraction.confidence == "7/7 required fields"


def test_table_values_are_never_overwritten_by_ai(user, template, monkeypatch):
    # AI (wrongly) also returns order_no — table must win.
    monkeypatch.setattr(
        free_text_extractor, "get_provider",
        lambda: StubProvider({
            "order_no": "WRONG-FROM-AI",
            "buyer_name": "ABA FASHIONS LTD",
            "delivery_date": "2026-08-25",
            "delivery_warehouse": "Chittagong Warehouse",
        }),
    )
    email = _make_email(user, body_html=COLUMNAR_HTML)
    record = run_extraction(email, template)
    assert record.data["order_no"] == "ORD-2793757"


def test_no_table_still_extracts_free_text(user, template, monkeypatch):
    monkeypatch.setattr(
        free_text_extractor, "get_provider",
        lambda: StubProvider({
            "buyer_name": "NORTH STAR APPARELS",
            "delivery_date": "2026-09-10",
            "delivery_warehouse": "Dhaka EPZ Warehouse",
        }),
    )
    email = _make_email(
        user,
        body_text=(
            "Kindly deliver the NORTH STAR APPARELS order to the Dhaka EPZ "
            "Warehouse by 10-09-2026. Table to follow separately."
        ),
    )
    record = run_extraction(email, template)
    assert record is not None
    assert record.data["buyer_name"] == "NORTH STAR APPARELS"
    assert record.data["delivery_warehouse"] == "Dhaka EPZ Warehouse"
    assert "order_no" not in record.data


def test_multi_row_table_keeps_first_line_and_preserves_all(user, template, monkeypatch):
    monkeypatch.setattr(
        free_text_extractor, "get_provider",
        lambda: StubProvider({"buyer_name": "ABA FASHIONS LTD"}),
    )
    html = """
    <table>
      <tr><th>Order No</th><th>Style Name</th><th>Total Cartons</th></tr>
      <tr><td>ORD-1</td><td>Crew Tee</td><td>100</td></tr>
      <tr><td>ORD-2</td><td>Pique Polo</td><td>250</td></tr>
    </table>
    """
    email = _make_email(user, body_html=html)
    record = run_extraction(email, template)
    assert record.data["order_no"] == "ORD-1"
    assert record.extraction.raw_output["_table_rows"][1]["order_no"] == "ORD-2"


def test_total_failure_returns_none(user, template, monkeypatch):
    monkeypatch.setattr(free_text_extractor, "get_provider", lambda: FailingProvider())
    email = _make_email(user, body_text="Totally unrelated newsletter content.")
    record = run_extraction(email, template)
    assert record is None
    assert Extraction.objects.latest("id").status == Extraction.Status.FAILED


@pytest.fixture
def csb_template(user):
    """Mirrors 'Expo Test Template' / 'PO Info' in the field report: every
    field is_free_text=False (the default a template author gets from the
    column-detection upload), and the target email has no HTML table at all."""
    tpl = Template.objects.create(user=user, name="CSB")
    names = ["po_number", "customer_name", "product", "quantity", "vessel_name",
             "etd", "eta", "port_of_loading", "destination", "container"]
    for i, name in enumerate(names):
        TemplateField.objects.create(
            template=tpl, name=name, label=name.replace("_", " ").title(),
            data_type="string", required=(name in ("po_number", "customer_name")),
            is_free_text=False, display_order=i,
        )
    return tpl


def test_plain_text_email_with_no_free_text_fields_no_longer_fails(user, csb_template, monkeypatch):
    """Regression for the reported bug: a plain-text 'Label: value' email
    against a template where nothing is flagged is_free_text used to fail
    outright (0 table fields x 0 free-text fields = 422). The text-line pass
    must resolve most fields with zero AI calls; only the two whose label
    doesn't textually match the field name (PO No -> po_number, Buyer ->
    customer_name) should reach the AI stub."""
    ai_calls = []

    def fake_extract(body, fields):
        ai_calls.append([f.name for f in fields])
        return {"po_number": "PO-45892", "customer_name": "ABC Garments Ltd."}, None

    monkeypatch.setattr("apps.extraction.pipeline.extract_free_text_fields", fake_extract)

    email = _make_email(
        user,
        body_text=(
            "Dear Team,\n\nPlease find below the shipment details.\n\n"
            "PO No: PO-45892\nBuyer: ABC Garments Ltd.\nProduct: Cotton Shirt\n"
            "Quantity: 15,000 PCS\nVessel: MSC Aurora\nETD: 20 September 2026\n"
            "ETA: 27 September 2026\nPort of Loading: Shanghai\n"
            "Destination: Chittagong\nContainer: 3 x 40HC\n\n"
            "Best regards,\nShipping Team"
        ),
    )
    record = run_extraction(email, csb_template)

    assert record is not None
    assert record.status == Record.Status.DRAFT
    # resolved deterministically, zero AI cost
    assert record.data["product"] == "Cotton Shirt"
    assert record.data["vessel_name"] == "MSC Aurora"
    assert record.data["destination"] == "Chittagong"
    # only the two unmatched labels were ever sent to the AI
    assert ai_calls == [["po_number", "customer_name"]]
    assert record.data["po_number"] == "PO-45892"
    assert record.data["customer_name"] == "ABC Garments Ltd."


def test_extraction_uses_only_the_explicitly_selected_attachment(
    user, template, monkeypatch
):
    """The 'email has 3 files, use only file 1' scenario: a spreadsheet
    attachment passed as ``attachment=`` must be used as the structured source
    — and the OTHER attachments on the email must never be touched at all."""
    monkeypatch.setattr(
        free_text_extractor, "get_provider",
        lambda: StubProvider({
            "buyer_name": "ABA FASHIONS LTD",
            "delivery_date": "2026-08-25",
            "delivery_warehouse": "Chittagong Warehouse",
        }),
    )

    df = pd.DataFrame(
        [["ORD-9", "CPS-9", "Tee", 300]],
        columns=["Order No", "CPS ID", "Style Name", "Total Cartons"],
    )
    buf = io.BytesIO()
    df.to_csv(buf, index=False)

    email = _make_email(user, body_html="<p>See the three attached files.</p>")
    wanted = Attachment.objects.create(
        email=email, filename="file1_orders.csv", content_type="text/csv",
        size=len(buf.getvalue()),
        file=SimpleUploadedFile("file1_orders.csv", buf.getvalue(), content_type="text/csv"),
    )
    # decoys — must never be opened/parsed by this run
    for name in ("file2_packing_list.pdf", "file3_photo.jpg"):
        Attachment.objects.create(
            email=email, filename=name, content_type="application/octet-stream",
            size=0, file=SimpleUploadedFile(name, b"\x00\x01"),
        )

    record = run_extraction(email, template, attachment=wanted)

    assert record is not None
    assert record.data["order_no"] == "ORD-9"
    assert record.data["cps_id"] == "CPS-9"
    assert record.data["style_name"] == "Tee"
    assert record.data["total_cartons"] == 300
    assert record.data["buyer_name"] == "ABA FASHIONS LTD"
