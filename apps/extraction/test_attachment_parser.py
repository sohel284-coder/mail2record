"""Attachment parsing: spreadsheets deterministically, PDFs via pdftotext,
unsupported types (images) reported cleanly rather than crashing.
"""

import io

import pandas as pd
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.emails.models import Attachment, Email
from apps.extraction.attachment_parser import parse_attachment, parse_spreadsheet_attachment

pytestmark = pytest.mark.django_db


def _csv_bytes(rows, headers):
    df = pd.DataFrame(rows, columns=headers)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf.read()


def test_parse_spreadsheet_attachment_csv_single_row():
    csv_bytes = _csv_bytes(
        [["ORD-1", "Crew Tee", 420]], ["Order No", "Style Name", "Total Cartons"]
    )
    result = parse_spreadsheet_attachment(
        io.BytesIO(csv_bytes), "order.csv", ["order_no", "style_name", "total_cartons"]
    )
    assert result == {"order_no": "ORD-1", "style_name": "Crew Tee", "total_cartons": 420}


def test_parse_spreadsheet_attachment_csv_multi_row():
    csv_bytes = _csv_bytes(
        [["ORD-1", 100], ["ORD-2", 200]], ["Order No", "Total Cartons"]
    )
    result = parse_spreadsheet_attachment(
        io.BytesIO(csv_bytes), "orders.csv", ["order_no", "total_cartons"]
    )
    assert isinstance(result, list)
    assert result[0] == {"order_no": "ORD-1", "total_cartons": 100}
    assert result[1] == {"order_no": "ORD-2", "total_cartons": 200}


def test_parse_spreadsheet_attachment_rejects_unknown_extension():
    with pytest.raises(ValueError):
        parse_spreadsheet_attachment(io.BytesIO(b"whatever"), "notes.txt", ["x"])


@pytest.fixture
def user():
    return get_user_model().objects.create_user("emp", password="x")


@pytest.fixture
def email(user):
    return Email.objects.create(user=user, message_id="m-attach-1", subject="PO")


def test_parse_attachment_routes_spreadsheet(email):
    csv_bytes = _csv_bytes([["PO-1", "ABC Garments"]], ["PO Number", "Customer Name"])
    attachment = Attachment.objects.create(
        email=email,
        filename="po.csv",
        content_type="text/csv",
        size=len(csv_bytes),
        file=SimpleUploadedFile("po.csv", csv_bytes, content_type="text/csv"),
    )
    assert attachment.kind == "spreadsheet"
    values, error = parse_attachment(attachment, ["po_number", "customer_name"])
    assert error is None
    assert values == {"po_number": "PO-1", "customer_name": "ABC Garments"}


def test_parse_attachment_reports_unsupported_image_type(email):
    attachment = Attachment.objects.create(
        email=email,
        filename="scan.jpg",
        content_type="image/jpeg",
        size=3,
        file=SimpleUploadedFile("scan.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
    )
    assert attachment.kind == "image"
    values, error = parse_attachment(attachment, ["po_number"])
    assert values == {}
    assert "OCR" in error


def test_parse_attachment_pdf_with_no_text_layer_reports_cleanly(email):
    # Not a real PDF, so pdftotext will fail to parse it -> treated as "no text".
    attachment = Attachment.objects.create(
        email=email,
        filename="scanned.pdf",
        content_type="application/pdf",
        size=3,
        file=SimpleUploadedFile("scanned.pdf", b"not a real pdf", content_type="application/pdf"),
    )
    assert attachment.kind == "pdf"
    values, error = parse_attachment(attachment, ["po_number"])
    assert values == {}
    assert error is not None
