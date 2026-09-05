from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.template.models import Template

from .models import Record


@login_required
def review_queue(request):
    drafts = (
        Record.objects.filter(user=request.user, status=Record.Status.DRAFT)
        .select_related("email", "template")
        .order_by("-created_at")
    )
    return render(
        request,
        "records/review_queue.html",
        {"active_page": "review", "drafts": drafts, "draft_count": drafts.count()},
    )


def _bound_fields(record):
    """Template fields in display order, each paired with its current value."""
    rows = []
    for f in record.template.fields.all().order_by("display_order", "id"):
        if f.data_type == "date":
            input_type = "date"
        elif f.data_type in ("integer", "number"):
            input_type = "number"
        else:
            input_type = "text"
        rows.append(
            {
                "name": f.name,
                "label": f.label or f.name,
                "data_type": f.data_type,
                "required": f.required,
                "is_free_text": f.is_free_text,
                "ai_instruction": f.ai_instruction,
                "value": record.data.get(f.name, ""),
                "input_type": input_type,
            }
        )
    return rows


@login_required
def review_detail(request, pk):
    record = get_object_or_404(
        Record.objects.select_related("email", "template", "extraction").prefetch_related(
            "template__fields"
        ),
        pk=pk,
        user=request.user,
    )
    return render(
        request,
        "records/review_detail.html",
        {"active_page": "review", "record": record, "fields": _bound_fields(record)},
    )


@login_required
def record_list(request):
    return render(
        request,
        "records/list.html",
        {
            "active_page": "records",
            "templates": Template.objects.filter(user=request.user).order_by("name"),
        },
    )


@login_required
def record_detail(request, pk):
    record = get_object_or_404(
        Record.objects.select_related(
            "email", "template", "extraction", "approved_by"
        ).prefetch_related("template__fields"),
        pk=pk,
        user=request.user,
    )
    return render(
        request,
        "records/detail.html",
        {"active_page": "records", "record": record, "fields": _bound_fields(record)},
    )
