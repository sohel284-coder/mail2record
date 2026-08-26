from datetime import date, datetime

from pydantic import BaseModel, ValidationError, create_model, field_validator


def build_validation_model(template):
    """Dynamically build a Pydantic model matching the template's field schema."""
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "date": date,
        "boolean": bool,
    }

    field_defs = {}
    for f in template.fields.all():
        py_type = type_map.get(f.data_type, str)
        default = ... if f.required else None
        field_defs[f.name] = (py_type | None if not f.required else py_type, default)

    model = create_model(f"Template{template.id}Validator", **field_defs)
    return model


def validate_extraction(template, raw_output: dict):
    """
    Returns (validated_dict, error_list, stats_dict).
    stats_dict has required_found / required_total / error_count for the
    confidence indicator (SRS §21).
    """
    model_cls = build_validation_model(template)
    required_fields = [f.name for f in template.fields.filter(required=True)]

    errors = []
    try:
        validated = model_cls(**raw_output)
        validated_dict = validated.model_dump(mode="json")
    except ValidationError as exc:
        validated_dict = raw_output  # keep what we have for human review
        errors = [f"{e['loc'][0]}: {e['msg']}" for e in exc.errors()]

    required_found = sum(
        1 for f in required_fields if raw_output.get(f) not in (None, "")
    )

    stats = {
        "required_found": required_found,
        "required_total": len(required_fields),
        "error_count": len(errors),
    }
    return validated_dict, errors, stats