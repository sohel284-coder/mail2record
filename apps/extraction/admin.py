from django.contrib import admin
from .models import Extraction


@admin.register(Extraction)
class ExtractionAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "template", "status", "confidence", "created_at")
    list_filter = ("status",)