from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .column_detection import detect_columns
from .models import Template
from .serializers import TemplateSerializer


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Template.objects.filter(user=self.request.user).prefetch_related("fields")

    def destroy(self, request, *args, **kwargs):
        """
        Block deleting a template that already has records — `Record.template`
        is `on_delete=CASCADE`, so a hard delete here would silently wipe out
        approved records too (violates SRS §17: never lose final data).
        Deactivating (is_active=False, via PUT/PATCH) is the safe alternative.
        """
        instance = self.get_object()
        if instance.records.exists():
            return Response(
                {
                    "detail": (
                        "This template has records against it and can't be deleted. "
                        "Deactivate it instead (Active checkbox on the edit form)."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        template = self.get_object()
        if not template.is_active:
            return Response(
                {"detail": "Activate this template before making it the default."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        template.is_default = True
        template.save(update_fields=["is_default"])  # unsets any other default too
        return Response(self.get_serializer(template).data)

    @action(detail=True, methods=["post"], url_path="unset-default")
    def unset_default(self, request, pk=None):
        template = self.get_object()
        template.is_default = False
        template.save(update_fields=["is_default"])
        return Response(self.get_serializer(template).data)


class DetectColumnsView(APIView):
    """
    POST /api/templates/detect-columns/  (multipart, field name: file)
    Returns detected columns without saving anything.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "No file uploaded. Use form field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            columns = detect_columns(uploaded_file)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"filename": uploaded_file.name, "columns": columns})
