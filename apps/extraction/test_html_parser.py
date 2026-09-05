"""Tests for the deterministic HTML table parser (SRS §10.1)."""

from apps.extraction.html_parser import has_html_table, parse_html_table, parse_key_value_text

PLAIN_TEXT_EMAIL = """Dear Team,

Please find below the shipment details for the upcoming booking.

PO No: PO-45892
Buyer: ABC Garments Ltd.
Product: Cotton Shirt
Quantity: 15,000 PCS
Vessel: MSC Aurora
ETD: 20 September 2026
ETA: 27 September 2026
Port of Loading: Shanghai
Destination: Chittagong
Container: 3 x 40HC

Please confirm receipt.

Best regards,
Shipping Team"""

KEY_VALUE_HTML = """
<table>
  <tr><td>PO Number:</td><td>PO-45892</td></tr>
  <tr><td>Customer Name</td><td>ABC Garments</td></tr>
  <tr><td>Quantity</td><td>15000</td></tr>
  <tr><td>Destination</td><td>Chittagong</td></tr>
</table>
"""

COLUMNAR_ONE_ROW_HTML = """
<table>
  <tr>
    <th>Order No</th><th>CPS ID</th><th>Special Code</th><th>Style Name</th>
    <th>Assorted Qty</th><th>Unassorted Qty</th><th>Total Cartons</th><th>Final Destination</th>
  </tr>
  <tr>
    <td>ORD-2793757</td><td>CPS-88213</td><td>SC-09</td><td>Mens Crew Tee</td>
    <td>12000</td><td>500</td><td>420</td><td>Hamburg</td>
  </tr>
</table>
"""

COLUMNAR_MULTI_ROW_HTML = """
<table>
  <tr><th>Order No</th><th>Style Name</th><th>Total Cartons</th></tr>
  <tr><td>ORD-1</td><td>Crew Tee</td><td>100</td></tr>
  <tr><td>ORD-2</td><td>Pique Polo</td><td>250</td></tr>
</table>
"""

DI_FIELDS = [
    "order_no", "cps_id", "special_code", "style_name", "assorted_qty",
    "unassorted_qty", "total_cartons", "final_destination",
]


def test_has_html_table():
    assert has_html_table("<div><table><tr><td>x</td></tr></table></div>") is True
    assert has_html_table("<p>just text</p>") is False
    assert has_html_table("") is False


def test_key_value_table_returns_single_dict():
    result = parse_html_table(
        KEY_VALUE_HTML, ["po_number", "customer_name", "quantity", "destination"]
    )
    assert result == {
        "po_number": "PO-45892",
        "customer_name": "ABC Garments",
        "quantity": "15000",
        "destination": "Chittagong",
    }


def test_columnar_single_row_returns_single_dict():
    result = parse_html_table(COLUMNAR_ONE_ROW_HTML, DI_FIELDS)
    assert result["order_no"] == "ORD-2793757"
    assert result["cps_id"] == "CPS-88213"
    assert result["style_name"] == "Mens Crew Tee"
    assert result["total_cartons"] == 420  # native int, not numpy
    assert isinstance(result["total_cartons"], int)
    assert result["final_destination"] == "Hamburg"


def test_columnar_multi_row_returns_list():
    result = parse_html_table(COLUMNAR_MULTI_ROW_HTML, ["order_no", "style_name", "total_cartons"])
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["order_no"] == "ORD-1"
    assert result[1]["style_name"] == "Pique Polo"


def test_columnar_with_explicit_column_field_map_fuzzy():
    html = """
    <table>
      <tr><th>ORDER-NO.</th><th>C.P.S. Id</th><th>Ctns</th></tr>
      <tr><td>ORD-9</td><td>CPS-9</td><td>50</td></tr>
    </table>
    """
    result = parse_html_table(
        html,
        ["order_no", "cps_id", "total_cartons"],
        column_field_map={"Order No": "order_no", "CPS ID": "cps_id", "Ctns": "total_cartons"},
    )
    assert result == {"order_no": "ORD-9", "cps_id": "CPS-9", "total_cartons": 50}


def test_assorted_qty_not_stolen_by_unassorted_qty_field():
    """Regression: when only 'Assorted Qty' is present, the 'unassorted_qty'
    field must not fuzzy-match and overwrite it."""
    html = """
    <table>
      <tr><th>Order No</th><th>Assorted Qty</th><th>Total Cartons</th></tr>
      <tr><td>ORD-7</td><td>6,300</td><td>178</td></tr>
    </table>
    """
    result = parse_html_table(html, ["order_no", "assorted_qty", "unassorted_qty", "total_cartons"])
    assert result["assorted_qty"] == 6300
    assert "unassorted_qty" not in result


def test_no_table_returns_empty_dict():
    assert parse_html_table("<p>No table here at all.</p>", ["x"]) == {}
    assert parse_html_table("", ["x"]) == {}


def test_missing_columns_are_simply_absent():
    result = parse_html_table(COLUMNAR_ONE_ROW_HTML, ["order_no", "not_a_column"])
    assert result == {"order_no": "ORD-2793757"}


def test_parse_key_value_text_resolves_plain_text_email_without_any_table():
    """Regression: an email with no HTML table at all (the common case per the
    SRS's own example) must still be resolvable deterministically wherever the
    field name/label matches the text's own label."""
    fields = [
        "po_number", "customer_name", "product", "quantity", "vessel_name",
        "etd", "eta", "port_of_loading", "destination", "container",
    ]
    result = parse_key_value_text(PLAIN_TEXT_EMAIL, fields)
    assert result["product"] == "Cotton Shirt"
    assert result["quantity"] == "15,000 PCS"
    assert result["vessel_name"] == "MSC Aurora"
    assert result["etd"] == "20 September 2026"
    assert result["eta"] == "27 September 2026"
    assert result["port_of_loading"] == "Shanghai"
    assert result["destination"] == "Chittagong"
    assert result["container"] == "3 x 40HC"
    # "PO No" / "Buyer" don't textually resemble "po_number" / "customer_name" —
    # those two are expected to fall through to the AI step, not silently vanish.
    assert "po_number" not in result
    assert "customer_name" not in result


def test_parse_key_value_text_ignores_unrelated_prose():
    assert parse_key_value_text("Dear Team,\nBest regards,\nShipping Team", ["po_number"]) == {}
    assert parse_key_value_text("", ["po_number"]) == {}
    assert parse_key_value_text("PO No: PO-1", []) == {}
