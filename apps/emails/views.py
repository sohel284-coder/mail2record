from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.template.models import Template

from .models import Email


@login_required
def inbox(request):
    active_templates = Template.objects.filter(
        user=request.user, is_active=True
    ).order_by("name")

    default_template = active_templates.filter(is_default=True).first()
    default_is_fallback = False
    if default_template is None:
        # No default chosen yet — fall back to the first active template so
        # the extract dialog still has something sensible pre-selected.
        default_template = active_templates.first()
        default_is_fallback = default_template is not None

    context = {
        "active_page": "inbox",
        "total_count": Email.objects.filter(user=request.user).count(),
        "templates": active_templates,
        "default_template": default_template,
        "default_is_fallback": default_is_fallback,
    }
    return render(request, "emails/inbox.html", context)


@login_required
def email_detail(request, pk):
    email = get_object_or_404(
        Email.objects.prefetch_related("records", "attachments"), pk=pk, user=request.user
    )
    return render(
        request,
        "emails/detail.html",
        {
            "active_page": "inbox",
            "email": email,
            "record": email.records.order_by("-created_at").first(),
        },
    )
