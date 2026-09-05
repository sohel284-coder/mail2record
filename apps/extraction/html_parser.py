"""Parse email content deterministically before falling back to AI (SRS §10.1).

Three deterministic shapes are handled, cheapest/most-reliable first:

1. Key-value tables: label in column 1, value in column 2 (one pair per row).
2. Columnar data tables: a header row of column names followed by one or more
   data rows (e.g. the ABA FASHIONS "Delivery Instruction" email, and other
   logistics / spreadsheet-style emails).
3. Plain-text "Label: value" lines — no HTML table at all (e.g. "PO No:
   PO-45892", "Buyer: ABC Garments Ltd."), the classic SRS §10.2 example.

``parse_html_table`` auto-detects shapes 1/2. ``parse_key_value_text`` handles
shape 3. All three share the fuzzy label/column matching in
``field_matching.py``, so a template's field list works against any of them
(or a spreadsheet attachment — see ``attachment_parser.py``) without extra
configuration. Only whatever these can't resolve should go to the AI (see
``pipeline.py``).

NOTE on ``pd.read_html``: on modern pandas a bare HTML string is treated as a
path and raises ``FileNotFoundError`` / "File name too long". The string MUST be
wrapped in ``io.StringIO`` first. All calls in this module do that.
"""

import io
import re

import pandas as pd
from bs4 import BeautifulSoup

from .field_matching import clean_value, dataframe_to_records, match_label, normalize


def has_html_table(body_html: str) -> bool:
    if not body_html:
        return False
    soup = BeautifulSoup(body_html, "html.parser")
    return soup.find("table") is not None


# --------------------------------------------------------------------------- #
# shape detection
# --------------------------------------------------------------------------- #
def _rows_of(table) -> list:
    return table.find_all("tr")


def _looks_like_key_value_table(rows) -> bool:
    """Key-value tables: every row has exactly 2 cells, there are several rows,
    and the first row is not a dedicated <th> header row."""
    if len(rows) < 2:
        return False
    cell_counts = [len(r.find_all(["td", "th"])) for r in rows]
    if not all(c == 2 for c in cell_counts):
        return False
    first_cells = rows[0].find_all(["td", "th"])
    if first_cells and all(c.name == "th" for c in first_cells):
        return False  # header row present -> treat as a (2-column) columnar table
    return True


# --------------------------------------------------------------------------- #
# key-value tables
# --------------------------------------------------------------------------- #
def parse_key_value_table(table, field_names: list[str]) -> dict:
    result: dict = {}
    normalized_fields = {normalize(f): f for f in field_names}

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = normalize(cells[0].get_text(strip=True))
        value = clean_value(cells[1].get_text(strip=True))
        if value is None:
            continue

        field_name = match_label(label, normalized_fields)
        if field_name:
            result.setdefault(field_name, value)

    return result


# --------------------------------------------------------------------------- #
# plain-text "Label: value" lines — no HTML table required (SRS §10.2)
# --------------------------------------------------------------------------- #
_LABEL_VALUE_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /&.()'-]{1,60}?)\s*[:\-]\s*(.+?)\s*$")


def parse_key_value_text(body_text: str, field_names: list[str]) -> dict:
    """Scan plain email text for "Label: value" lines (also accepts "Label - value")
    and fuzzy-match labels against ``field_names`` — the same matching used for
    2-column HTML tables, just applied line-by-line instead of row-by-row.

    Deliberately conservative: a line only ever produces output if its label
    fuzzy-matches one of the *specific* field names/labels passed in, so
    unrelated prose (greetings, signatures, disclaimers) is silently ignored
    rather than misread.
    """
    if not body_text or not field_names:
        return {}

    result: dict = {}
    normalized_fields = {normalize(f): f for f in field_names}

    for raw_line in body_text.splitlines():
        match = _LABEL_VALUE_LINE_RE.match(raw_line)
        if not match:
            continue
        label = normalize(match.group(1))
        value = clean_value(match.group(2))
        if value is None:
            continue

        field_name = match_label(label, normalized_fields)
        if field_name and field_name not in result:
            result[field_name] = value

    return result


# --------------------------------------------------------------------------- #
# columnar tables
# --------------------------------------------------------------------------- #
def parse_columnar_table(
    body_html: str,
    field_names: list[str],
    column_field_map: dict[str, str] | None = None,
) -> list[dict]:
    """Return one dict per data row (usually one, sometimes several batched lines)."""
    tables = pd.read_html(io.StringIO(body_html))  # StringIO wrap is mandatory
    if not tables:
        return []

    # pick the widest table (the data table, not a layout wrapper)
    df = max(tables, key=lambda t: t.shape[1])
    return dataframe_to_records(df, field_names, column_field_map)


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def parse_html_table(
    body_html: str,
    field_names: list[str],
    column_field_map: dict | None = None,
):
    """Auto-detect the table shape and parse it.

    - ``field_names``: template field machine-keys we want to fill from the table.
    - ``column_field_map``: optional explicit {html_column_header: field_name}
      mapping for columnar tables; headers are fuzzy-matched (case / whitespace /
      hyphen insensitive). If omitted, ``field_names`` are matched against the
      headers directly.

    Returns a single ``dict`` for one data row (key-value tables always, and
    single-row columnar tables), or a ``list[dict]`` when a columnar table has
    multiple data rows (e.g. several shipment lines batched in one email).
    Returns ``{}`` when there is no table.
    """
    if not body_html:
        return {}

    soup = BeautifulSoup(body_html, "html.parser")
    table = soup.find("table")
    if table is None:
        return {}

    rows = _rows_of(table)

    if _looks_like_key_value_table(rows):
        return parse_key_value_table(table, field_names)

    records = parse_columnar_table(body_html, field_names, column_field_map)
    if not records:
        return {}
    if len(records) == 1:
        return records[0]
    return records
