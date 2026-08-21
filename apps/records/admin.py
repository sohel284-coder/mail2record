from django.contrib import admin
from .models import Record


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("id", "template", "status", "user", "approved_by", "created_at")
    list_filter = ("status", "template")