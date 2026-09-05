from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .models import Record
from .serializers import RecordSerializer


class RecordViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Records are created by the extraction pipeline, never POSTed directly.
    Supported here: list / retrieve / PATCH (edit the `data` blob of a draft)
    plus /approve/ and /reject/ actions (SRS §12.6).
    """

    serializer_class = RecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options", "post"]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "template"]
    search_fields = ["email__subject", "email__sender", "data"]
    ordering_fields = ["created_at", "updated_at", "approved_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = (
            Record.objects.filter(user=self.request.user)
            .select_related("email", "template", "extraction", "approved_by")
            .prefetch_related("template__fields")
        )
        created_after = self.request.query_params.get("created_after")
        created_before = self.request.query_params.get("created_before")
        if created_after:
            qs = qs.filter(created_at__date__gte=created_after)
        if created_before:
            qs = qs.filter(created_at__date__lte=created_before)
        return qs

    def _transition(self, request, target_status):
        record = self.get_object()
        if record.status != Record.Status.DRAFT:
            return Response(
                {"detail": f"Record is already {record.get_status_display().lower()}."},
                status=status.HTTP_409_CONFLICT,
            )
        record.status = target_status
        if target_status == Record.Status.APPROVED:
            record.approved_by = request.user
            record.approved_at = timezone.now()
        record.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        return Response(self.get_serializer(record).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._transition(request, Record.Status.APPROVED)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._transition(request, Record.Status.REJECTED)
