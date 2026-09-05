"""Focused AI extraction for fields that are NOT present in an email's HTML table.

Some template fields (e.g. a delivery date, a destination warehouse, a buyer
name mentioned only in a greeting sentence) live in the free-text body of the
email, never in the structured table. Asking the LLM to re-derive the whole
schema is slower and noisier than asking it for just those few fields, so this
module builds a small, targeted prompt for the ``is_free_text`` fields only.

Uses the shared ``AIProvider`` interface (``providers.get_provider``) — the
provider already strips markdown fences and parses JSON.
"""

import json
import re

from .providers import get_provider

_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)


def _loads_lenient(raw: str) -> dict | None:
    """Best-effort JSON parse: strip fences, then fall back to the first {...} block."""
    if not raw:
        return None
    cleaned = _FENCE_RE.sub("", raw).strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def build_free_text_prompt(body: str, fields) -> str:
    """``fields``: iterable of TemplateField (or any object with
    ``name`` / ``data_type`` / ``required`` / ``label`` / ``ai_instruction``)."""
    schema_lines = "\n".join(
        f"- {f.name} ({f.data_type}, {'required' if f.required else 'optional'})"
        + (f" — {f.label}" if getattr(f, 'label', '') and f.label != f.name else "")
        + (f" — {f.ai_instruction}" if getattr(f, "ai_instruction", "") else "")
        for f in fields
    )
    return f"""You extract a FEW specific values from a business email's free text.
Return ONLY a JSON object with exactly these keys, no explanation, no markdown fences.

Extract ONLY these fields (ignore everything else in the email, including any tables):
{schema_lines}

Rules:
- Dates must be formatted as YYYY-MM-DD (drop any time-of-day component).
  Accept any input format: "25-08-2026 16:00", "02 September 2026", "15/09/2026",
  "05.09.2026", "2026-08-26T10:00" all map to a plain YYYY-MM-DD date.
- Numeric fields must be plain numbers, no commas or units.
- Use the exact company / place name as written in the email, unchanged.
- A buyer / customer company name may appear WITHOUT the word "Buyer". It is the
  garment/apparel company named right after phrases like "for", "delivery
  instruction for", "delivery note for", "consignment for", or in the greeting
  ("Dear <COMPANY> team"). It is NOT the sender/vendor, a bank, a port, or a
  warehouse. Extract it even when it is not explicitly labelled.
- If a field is genuinely not stated anywhere in the text, set its value to null
  (do not invent one).

Email text:
\"\"\"
{body}
\"\"\"

JSON:"""


def extract_free_text_fields(body: str, fields) -> tuple[dict, str | None]:
    """Extract only the given free-text fields from ``body``.

    Returns ``(values_dict, error_message)``. ``values_dict`` only contains keys
    that belong to ``fields`` and have a non-empty value.
    """
    fields = list(fields)
    if not fields:
        return {}, None
    if not body or not body.strip():
        return {}, "no free-text body to extract from"

    prompt = build_free_text_prompt(body, fields)
    provider = get_provider()
    output, error = provider.extract(prompt)

    if output is None:
        # provider failed to parse — try one more lenient pass on its raw text
        raw = error.split("raw output:")[-1] if error and "raw output:" in error else ""
        output = _loads_lenient(raw)
        if output is None:
            return {}, error or "AI returned no parseable JSON for free-text fields"

    allowed = {f.name for f in fields}
    cleaned = {}
    for key, value in output.items():
        if key not in allowed:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value or value.lower() in {"null", "none", "n/a", "-"}:
                continue
        cleaned[key] = value

    return cleaned, None
