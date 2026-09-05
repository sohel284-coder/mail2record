from django.contrib import admin

from .models import Attachment, Email, EmailAccount


@admin.register(EmailAccount)
class EmailAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "email_address", "is_active", "last_sync_status")
    list_filter = ("provider", "is_active", "last_sync_status")
    readonly_fields = ("credentials_encrypted", "last_sync_at", "created_at", "updated_at")


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
