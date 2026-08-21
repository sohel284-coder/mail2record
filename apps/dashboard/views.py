from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.emails.models import Email
from apps.records.models import Record
from apps.template.models import Template


@login_required
def index(request):
    user = request.user
    context = {
        "active_page": "overview",
        "emails_total": Email.objects.filter(user=user).count(),
        "drafts_count": Record.objects.filter(user=user, status=Record.Status.DRAFT).count(),
        "approved_count": Record.objects.filter(user=user, status=Record.Status.APPROVED).count(),
        "active_templates": Template.objects.filter(user=user, is_active=True),
        "recent_drafts": Record.objects.filter(
            user=user, status=Record.Status.DRAFT
        ).select_related("email", "template").order_by("-created_at")[:3],
    }
    return render(request, "dashboard/index.html", context)


@login_required
def settings_page(request):
    return render(request, "dashboard/settings.html", {"active_page": "settings"})