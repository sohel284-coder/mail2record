from django.utils import timezone

from apps.records.models import Record
from .html_parser import has_html_table, parse_html_table
from .models import Extraction
from .prompt_builder import build_prompt
from .providers import get_provider
from .validation import validate_extraction


def run_extraction(email, template):
    """
    Runs the full extraction pipeline for one email against one template.
    Creates an Extraction row and a linked DRAFT Record. Returns the Record.
    """
    extraction = Extraction.objects.create(
        email=email, template=template, status=Extraction.Status.PROCESSING
    )

    field_names = list(template.fields.values_list("name", flat=True))
    deterministic_values = {}

    # Step 1: deterministic HTML table parsing first (SRS §10.1/§18)
    if has_html_table(email.body_html):
        deterministic_values = parse_html_table(email.body_html, field_names)

    # Step 2: AI extraction for whatever wasn't found deterministically
    provider = get_provider()
    body_for_ai = email.body_text or email.body_html or ""
    prompt = build_prompt(template, body_for_ai)
    ai_output, error = provider.extract(prompt)

    if error and not deterministic_values:
        extraction.status = Extraction.Status.FAILED
        extraction.error_message = error
        extraction.processed_at = timezone.now()
        extraction.save()
        return None

    merged = {**(ai_output or {}), **deterministic_values}  # deterministic wins on overlap
    validated_dict, errors, stats = validate_extraction(template, merged)

    extraction.raw_output = merged
    extraction.status = Extraction.Status.SUCCESS if not errors else Extraction.Status.SUCCESS
    extraction.confidence = f"{stats['required_found']}/{stats['required_total']} required fields"
    extraction.processed_at = timezone.now()
    extraction.save()

    record = Record.objects.create(
        user=email.user,
        email=email,
        template=template,
        extraction=extraction,
        data=validated_dict,
        status=Record.Status.DRAFT,
    )

    email.is_processed = True
    email.save(update_fields=["is_processed"])

    return record