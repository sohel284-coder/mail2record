from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.extraction.pipeline import run_extraction
from apps.template.models import Template

from .models import Attachment, Email, EmailAccount
from .providers import get_email_provider, guess_imap_host
from .serializers import EmailAccountSerializer, EmailSerializer


class EmailViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Emails are created by the fetch_emails polling command, never POSTed
    through the API — only list/retrieve/delete plus the /extract/ action,
    which runs the extraction pipeline for a chosen template (SRS §4.2 —
    "Template selected → AI extraction").
    """

    serializer_class = EmailSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["is_processed"]
    search_fields = ["sender", "subject", "message_id"]

    def get_queryset(self):
        # received_at is null for a handful of manually-created/legacy rows;
        # a bare "-received_at" puts those NULLs first in Postgres (NULLS
        # FIRST is the default for DESC), which shoves old test emails above
        # genuinely recent ones. Fall back to created_at so "most recent" is
        # always what actually shows at the top.
        return (
            Email.objects.filter(user=self.request.user)
            .prefetch_related("records", "attachments")
            .annotate(sort_date=Coalesce("received_at", "created_at"))
            .order_by("-sort_date")
        )

    def destroy(self, request, *args, **kwargs):
        """
        Deleting an email is only safe while nothing depends on it yet — once
        a Record exists (draft, approved, or rejected) the email is that
        record's permanent source-of-truth reference (SRS §17) and must stay,
        the same guard already used for templates with records against them.
        """
        instance = self.get_object()
        if instance.records.exists():
            return Response(
                {
                    "detail": (
                        "This email has a record against it and can't be deleted. "
                        "Reject the record first if you no longer want it."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def extract(self, request, pk=None):
        email = self.get_object()
        template_id = request.data.get("template")
        if not template_id:
            return Response(
                {"detail": "Provide a `template` id to extract against."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            template = Template.objects.get(id=template_id, user=request.user)
        except (Template.DoesNotExist, ValueError, TypeError):
            return Response(
                {"detail": "Template not found."}, status=status.HTTP_404_NOT_FOUND
            )

        attachment = None
        attachment_id = request.data.get("attachment")
        if attachment_id:
            try:
                attachment = email.attachments.get(id=attachment_id)
            except (Attachment.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"detail": "Attachment not found on this email."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        record = run_extraction(email, template, attachment=attachment)
        if record is None:
            return Response(
                {"detail": "Extraction failed — see the extraction log."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response(
            {
                "record_id": record.id,
                "status": record.status,
                "data": record.data,
                "used_attachment": attachment.filename if attachment else None,
            },
            status=status.HTTP_201_CREATED,
        )


class EmailAccountView(APIView):
    """The current user's single mailbox connection (Settings page)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        account = EmailAccount.objects.filter(user=request.user).first()
        if account is None:
            suggested = None
            addr = request.query_params.get("email_address")
            if addr:
                host, port = guess_imap_host(addr)
                suggested = {"host": host, "port": port}
            return Response({"connected": False, "suggested_imap": suggested})
        return Response({"connected": True, **EmailAccountSerializer(account).data})

    def delete(self, request):
        EmailAccount.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImapConnectView(APIView):
    """Connect (or replace) the user's mailbox via IMAP — tests the login
    before saving, and stores the app password encrypted."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        email_address = (request.data.get("email_address") or "").strip()
        password = request.data.get("password") or ""
        host = (request.data.get("host") or "").strip()
        port = request.data.get("port")

        if not email_address or not password:
            return Response(
                {"detail": "Email address and password are both required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not host:
            host, port = guess_imap_host(email_address)
        if not host:
            return Response(
                {"detail": "Couldn't work out the IMAP server for this address — "
                           "enter it manually."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        account = EmailAccount(
            user=request.user,
            provider=EmailAccount.Provider.IMAP,
            email_address=email_address,
            config={
                "host": host,
                "port": int(port or 993),
                "username": email_address,
                "mailbox": "INBOX",
            },
            is_active=True,
        )
        account.credentials = {"password": password}

        try:
            get_email_provider(account).test_connection()
        except Exception as exc:  # imaplib raises several distinct error types
            return Response(
                {"detail": f"Couldn't connect: {exc}"}, status=status.HTTP_400_BAD_REQUEST
            )

        EmailAccount.objects.filter(user=request.user).delete()
        account.save()
        return Response(
            {"connected": True, **EmailAccountSerializer(account).data},
            status=status.HTTP_201_CREATED,
        )


class EmailAccountTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        account = EmailAccount.objects.filter(user=request.user).first()
        if account is None:
            return Response(
                {"detail": "No mailbox connected."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            get_email_provider(account).test_connection()
        except Exception as exc:
            account.mark_synced(ok=False, error=str(exc))
            return Response(
                {"ok": False, "detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )

        account.mark_synced(ok=True)
        return Response({"ok": True})
