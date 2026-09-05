from django.contrib import admin

from .models import Attachment, Email


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ("filename", "content_type", "size", "created_at")


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender", "received_at", "is_processed")
    list_filter = ("is_processed", "source")
    search_fields = ("subject", "sender", "message_id")
    inlines = [AttachmentInline]


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ("filename", "email", "content_type", "size", "created_at")
    search_fields = ("filename", "email__subject")
