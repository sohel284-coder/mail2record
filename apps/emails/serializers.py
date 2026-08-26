from rest_framework import serializers
from apps.emails.models import Email


class EmailSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Email
        fields = [
            "id", "sender", "recipient", "subject", "body_text", "body_html",
            "received_at", "source", "is_processed", "status", "message_id", "created_at",
        ]

    def get_status(self, obj):
        return "done" if obj.is_processed else "draft"