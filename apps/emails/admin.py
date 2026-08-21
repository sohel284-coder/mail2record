from django.contrib import admin
from .models import Email


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender", "received_at", "is_processed")
    list_filter = ("is_processed", "source")
    search_fields = ("subject", "sender", "message_id")