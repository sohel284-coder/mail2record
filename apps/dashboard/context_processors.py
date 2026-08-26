from apps.emails.models import Email
from apps.records.models import Record


def sidebar_counts(request):
    if not request.user.is_authenticated:
        return {}
    return {
        "inbox_draft_count": Email.objects.filter(user=request.user, is_processed=False).count(),
        "review_draft_count": Record.objects.filter(user=request.user, status=Record.Status.DRAFT).count(),
    }