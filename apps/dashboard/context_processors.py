from apps.emails.models import Email, EmailAccount
from apps.records.models import Record


def sidebar_counts(request):
    if not request.user.is_authenticated:
        return {}
    account = EmailAccount.objects.filter(user=request.user).first()
    return {
        "inbox_draft_count": Email.objects.filter(
            user=request.user, is_processed=False
        ).count(),
        "review_draft_count": Record.objects.filter(
            user=request.user, status=Record.Status.DRAFT
        ).count(),
        "sidebar_mailbox": account,
    }
