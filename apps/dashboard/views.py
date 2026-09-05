from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.emails.models import Email, EmailAccount
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
    user = request.user
    context = {
        "active_page": "settings",
        "ai_provider": settings.AI_PROVIDER,
        "ai_model": getattr(settings, "OLLAMA_MODEL", ""),
        "email_account": EmailAccount.objects.filter(user=user).first(),
        "gmail_oauth_enabled": settings.GMAIL_OAUTH_ENABLED,
        "template_count": Template.objects.filter(user=user).count(),
        "record_count": Record.objects.filter(user=user).count(),
        "approved_count": Record.objects.filter(user=user, status=Record.Status.APPROVED).count(),
    }
    return render(request, "dashboard/settings.html", context)
