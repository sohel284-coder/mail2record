from rest_framework import serializers

from apps.emails.models import Attachment, Email, EmailAccount


class EmailAccountSerializer(serializers.ModelSerializer):
    """Safe view of a mailbox connection — never exposes credentials or the
    raw config blob."""

    imap_host = serializers.SerializerMethodField()

    class Meta:
        model = EmailAccount
        fields = [
            "provider", "email_address", "is_active", "imap_host",
            "last_sync_at", "last_sync_status", "last_sync_error",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_imap_host(self, obj):
        if obj.provider != EmailAccount.Provider.IMAP:
            return None
        return (obj.config or {}).get("host")


class AttachmentSerializer(serializers.ModelSerializer):
    kind = serializers.CharField(read_only=True)

    class Meta:
        model = Attachment
        fields = ["id", "filename", "content_type", "size", "kind", "created_at"]


class EmailSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    record_id = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Email
        fields = [
            "id", "sender", "recipient", "subject", "body_text", "body_html",
            "received_at", "source", "is_processed", "status", "record_id",
            "attachments", "message_id", "created_at",
        ]

    def get_status(self, obj):
        return "done" if obj.is_processed else "draft"

    def get_record_id(self, obj):
        record = obj.records.order_by("-created_at").first()
        return record.id if record else None
