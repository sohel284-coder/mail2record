"""
Phase 4 Stage A: AI Extraction Spike.
Standalone script — NOT part of the Django app yet. Run directly with:
    uv run python spike/run_spike.py
"""

import json
import re
from pathlib import Path

import ollama

MODEL_NAME = "Qwen2.5:7B"  # swap for whatever you pulled in Phase 0
EVAL_FILE = Path(__file__).parent / "eval_emails.json"

TEMPLATE_SCHEMAS = {
    "CSB": [
        ("po_number", "string", True),
        ("customer_name", "string", True),
        ("product", "string", True),
        ("quantity", "integer", True),
        ("vessel_name", "string", False),
        ("etd", "date", False),
        ("eta", "date", False),
        ("destination", "string", True),
    ],
}


def build_prompt(template_name, email_body):
    schema = TEMPLATE_SCHEMAS[template_name]
    schema_lines = "\n".join(
        f"- {name} ({dtype}, {'required' if required else 'optional'})"
        for name, dtype, required in schema
    )
    return f"""You extract structured data from business emails. Return ONLY a JSON object, no explanation, no markdown fences.

Fields to extract:
{schema_lines}

Rules:
- Dates must be formatted as YYYY-MM-DD (assume year 2026 if not stated).
- Quantity must be a plain integer, no commas or units.
- If a field is not present in the email, omit it from the JSON (don't guess).

Email:
\"\"\"
{email_body}
\"\"\"

JSON:"""


def extract(template_name, email_body):
    prompt = build_prompt(template_name, email_body)
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    raw = response["message"]["content"].strip()
    # Strip markdown fences if the model adds them despite instructions
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        print(json.loads(raw))
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse failed: {e} | raw output: {raw[:200]}"


def score(expected, actual):
    if actual is None:
        return 0, len(expected), list(expected.keys())
    correct = 0
    missing = []
    for key, expected_val in expected.items():
        actual_val = actual.get(key)
        if actual_val is not None and str(actual_val).strip().lower() == str(expected_val).strip().lower():
            correct += 1
        else:
            missing.append(f"{key}: expected={expected_val!r} got={actual_val!r}")
    return correct, len(expected), missing


def main():
    cases = json.loads(EVAL_FILE.read_text())
    total_fields = 0
    total_correct = 0
    failures = []

    print(f"Running spike against {len(cases)} email(s) using model: {MODEL_NAME}\n")

    for case in cases:
        actual, error = extract(case["template"], case["email_body"])
        print(actual)
        if error:
            failures.append((case["id"], error))
            total_fields += len(case["expected"])
            continue

        correct, field_count, mismatches = score(case["expected"], actual)
        total_correct += correct
        total_fields += field_count

        status = "✓" if correct == field_count else "✗"
        print(f"{status} {case['id']}: {correct}/{field_count} fields correct")
        if mismatches:
            for m in mismatches:
                print(f"    - {m}")

    print(f"\n{'='*50}")
    print(f"OVERALL: {total_correct}/{total_fields} fields correct "
          f"({100 * total_correct / total_fields:.1f}%)")
    if failures:
        print(f"\n{len(failures)} email(s) failed to produce valid JSON:")
        for case_id, err in failures:
            print(f"  - {case_id}: {err}")


if __name__ == "__main__":
    main()