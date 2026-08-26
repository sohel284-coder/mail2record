"""Parse HTML tables deterministically before falling back to AI.

Handles two table shapes found in real business emails:
1. Key-value tables: label in column 1, value in column 2 (one pair per row)
2. Columnar data tables: header row of field names, one or more data rows
   (e.g. logistics/shipment notifications, spreadsheet-style emails)
"""

import pandas as pd
from bs4 import BeautifulSoup


def has_html_table(body_html: str) -> bool:
    if not body_html:
        return False
    soup = BeautifulSoup(body_html, "html.parser")
    return soup.find("table") is not None


def _normalize(text: str) -> str:
    return text.strip().lower().replace("_", " ").replace("-", " ")


def _looks_like_key_value_table(rows) -> bool:
    """Heuristic: key-value tables have exactly 2 cells per row, many rows,
    and no distinct header row (all rows look like data)."""
    if not rows:
        return False
    cell_counts = [len(r.find_all(["td", "th"])) for r in rows]
    return all(c == 2 for c in cell_counts) and len(rows) >= 2


def parse_key_value_table(table, field_names: list[str]) -> dict:
    result = {}
    normalized_fields = {_normalize(f): f for f in field_names}

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = _normalize(cells[0].get_text(strip=True).rstrip(":"))
        value = cells[1].get_text(strip=True)

        for norm_label, field_name in normalized_fields.items():
            if norm_label in label or label in norm_label:
                result[field_name] = value
                break

    return result


def parse_columnar_table(html: str, field_map: dict[str, str]) -> list[dict]:
    """
    field_map: {html_column_header: template_field_name}
    Returns one dict per data row (usually just one row for a single-shipment email,
    but some emails batch multiple shipments in one table).
    """
    tables = pd.read_html(html)
    if not tables:
        return []

    df = tables[0]
    normalized_columns = {_normalize(str(c)): c for c in df.columns}

    records = []
    for _, row in df.iterrows():
        record = {}
        for html_header, field_name in field_map.items():
            norm_header = _normalize(html_header)
            matched_col = normalized_columns.get(norm_header)
            if matched_col is not None:
                value = row[matched_col]
                if pd.notna(value):
                    record[field_name] = value
        records.append(record)

    return records


def parse_html_table(body_html: str, field_names: list[str], column_field_map: dict | None = None):
    """
    Auto-detects table shape and parses accordingly.
    - column_field_map: optional explicit {html_column_header: field_name} mapping
      for columnar tables. If not given, falls back to fuzzy-matching field_names
      directly against column headers.
    Returns a dict (key-value case, or single-row columnar) or a list of dicts
    (multi-row columnar, e.g. multiple shipment lines in one email).
    """
    soup = BeautifulSoup(body_html, "html.parser")
    table = soup.find("table")
    if not table:
        return {}

    rows = table.find_all("tr")

    if _looks_like_key_value_table(rows):
        return parse_key_value_table(table, field_names)

    # Columnar table
    field_map = column_field_map or {f: f for f in field_names}
    records = parse_columnar_table(body_html, field_map)

    if len(records) == 1:
        return records[0]
    return records