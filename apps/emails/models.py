from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


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
