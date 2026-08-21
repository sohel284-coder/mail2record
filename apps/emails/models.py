from django.conf import settings
from django.db import models


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