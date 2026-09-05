from django.conf import settings
from django.db import models, transaction


class Template(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="templates"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_file = models.CharField(max_length=500, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Pre-selected template for one-click extraction from the inbox.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} (v{self.version})"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_default:
                Template.objects.filter(user_id=self.user_id, is_default=True).exclude(
                    pk=self.pk
                ).update(is_default=False)

class DataType(models.TextChoices):
    STRING = "string", "String"
    INTEGER = "integer", "Integer"
    NUMBER = "number", "Number"
    DATE = "date", "Date"
    BOOLEAN = "boolean", "Boolean"


class TemplateField(models.Model):
    template = models.ForeignKey(
        Template, on_delete=models.CASCADE, related_name="fields"
    )
    name = models.CharField(max_length=100)  # machine key, e.g. po_number
    label = models.CharField(max_length=255)  # human label, e.g. "PO Number"
    data_type = models.CharField(
        max_length=20, choices=DataType.choices, default=DataType.STRING
    )
    required = models.BooleanField(default=False)
    is_free_text = models.BooleanField(
        default=False,
        help_text="True if this field is NOT derivable from an HTML table and must "
        "be extracted from the email's free-text body by the AI.",
    )
    description = models.TextField(blank=True)
    ai_instruction = models.TextField(
        blank=True, help_text="Extra hint given to the LLM for this field"
    )
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "id"]
        unique_together = ("template", "name")

    def __str__(self):
        return f"{self.template.name} → {self.label}"
