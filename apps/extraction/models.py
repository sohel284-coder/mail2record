from django.db import models
from apps.emails.models import Email
from apps.template.models import Template


class Extraction(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"

    email = models.ForeignKey(
        Email, on_delete=models.CASCADE, related_name="extractions"
    )
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="extractions"
    )
    raw_output = models.JSONField(default=dict, blank=True)
    confidence = models.CharField(max_length=50, blank=True)  # e.g. "8/8 fields"
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Extraction #{self.id} [{self.status}]"