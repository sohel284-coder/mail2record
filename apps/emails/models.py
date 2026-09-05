from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .crypto import decrypt_dict, encrypt_dict


class EmailAccount(models.Model):
    """One mailbox connection per user, configured from the Settings UI.

    Credentials (an OAuth token bundle for Gmail, or an app password for IMAP)
    are encrypted at rest — see ``crypto.py``. Nothing here is ever sent back
    to the frontend except the provider name, the address, and sync status.
    """

    class Provider(models.TextChoices):
        GMAIL = "gmail", "Gmail"
        IMAP = "imap", "IMAP (Outlook, Yahoo, other)"

    class SyncStatus(models.TextChoices):
        NEVER = "", "Never synced"
        OK = "ok", "OK"
        ERROR = "error", "Error"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_account"
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    email_address = models.EmailField()
    config = models.JSONField(default=dict, blank=True)  # imap host/port/username/mailbox
    credentials_encrypted = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=20, choices=SyncStatus.choices, blank=True, default=SyncStatus.NEVER
    )
    last_sync_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email_address} ({self.provider})"

    @property
    def credentials(self) -> dict:
        return decrypt_dict(self.credentials_encrypted)

    @credentials.setter
    def credentials(self, value):
        self.credentials_encrypted = encrypt_dict(value or {})

    def mark_synced(self, ok: bool, error: str = ""):
        from django.utils import timezone

        self.last_sync_status = self.SyncStatus.OK if ok else self.SyncStatus.ERROR
        self.last_sync_error = error
        self.last_sync_at = timezone.now()
        self.save(
            update_fields=[
                "last_sync_status", "last_sync_error", "last_sync_at", "updated_at",
            ]
        )


class Email(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emails"
    )
    message_id = models.CharField(max_length=500, unique=True)
    sender = models.CharField(max_length=255, blank=True)
    recipient = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=998, blank=True)
    body_text = models.TextField(blank=True)
    body_html = models.TextField(blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, blank=True)  # e.g. "gmail"
    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.subject} ({self.sender})"


def attachment_upload_path(instance, filename):
    return f"attachments/{instance.email.user_id}/{instance.email_id}/{filename}"


class Attachment(models.Model):
    """A file attached to a collected email (SRS §10.1 — Phase 2 attachment support).

    Stored on disk (or whatever DEFAULT_FILE_STORAGE points at) rather than in
    the database — extraction reads the file when a user explicitly picks this
    attachment as the data source for a run (see ``apps.extraction.pipeline``).
    """

    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name="attachments")
    filename = models.CharField(max_length=500)
    content_type = models.CharField(max_length=200, blank=True)
    size = models.PositiveIntegerField(default=0)
    file = models.FileField(upload_to=attachment_upload_path)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.filename} ({self.email_id})"

    @property
    def kind(self) -> str:
        """Coarse type used to pick a parser: 'spreadsheet' / 'pdf' / 'image' / 'other'."""
        name = self.filename.lower()
        if name.endswith((".csv", ".xlsx", ".xls")):
            return "spreadsheet"
        if name.endswith(".pdf"):
            return "pdf"
        if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff")):
            return "image"
        return "other"


@receiver(post_delete, sender=Attachment)
def _delete_attachment_file(sender, instance, **kwargs):
    """Deleting an Email cascades to its Attachment rows; this makes sure the
    underlying file on disk goes with it instead of becoming an orphan under
    media/. post_delete fires for every row in a cascade, not just direct
    Attachment.delete() calls, so this covers both paths."""
    if instance.file:
        instance.file.delete(save=False)
