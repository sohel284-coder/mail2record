from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import Email


@login_required
def inbox(request):
    context = {
        "active_page": "inbox",
        "total_count": Email.objects.filter(user=request.user).count(),
    }
    return render(request, "emails/inbox.html", context)