from django.conf import settings
from django.db import models
from apps.emails.models import Email
from apps.extraction.models import Extraction
from apps.template.models import Template


class Record(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="records"
    )
    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name="records")
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="records"
    )
    extraction = models.ForeignKey(
        Extraction, on_delete=models.SET_NULL, null=True, related_name="records"
    )
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_records",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Record #{self.id} [{self.status}]"