def build_prompt(template, email_body: str) -> str:
    schema_lines = "\n".join(
        f"- {f.name} ({f.data_type}, {'required' if f.required else 'optional'})"
        + (f" — {f.ai_instruction}" if f.ai_instruction else "")
        for f in template.fields.all().order_by("display_order")
    )

    return f"""You extract structured data from business emails. Return ONLY a JSON object, no explanation, no markdown fences.

Fields to extract:
{schema_lines}

Rules:
- Dates must be formatted as YYYY-MM-DD.
- Numeric fields must be plain numbers, no commas or units.
- If a field is not present in the email, omit it from the JSON (don't guess).

Email:
\"\"\"
{email_body}
\"\"\"

JSON:"""