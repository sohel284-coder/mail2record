from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from .models import Email
from .serializers import EmailSerializer


class EmailViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only: emails are created by the fetch_emails polling command,
    not directly through the API.
    """
    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_processed"]
    search_fields = ["sender", "subject", "message_id"]

    def get_queryset(self):
        return Email.objects.filter(user=self.request.user).order_by("-received_at")