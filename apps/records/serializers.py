from rest_framework import serializers

from apps.template.models import TemplateField

from .models import Record


class RecordFieldSchemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateField
        fields = [
            "name", "label", "data_type", "required",
            "is_free_text", "description", "ai_instruction", "display_order",
        ]


class RecordSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    email_subject = serializers.CharField(source="email.subject", read_only=True)
    email_sender = serializers.CharField(source="email.sender", read_only=True)
    email_id = serializers.IntegerField(source="email.id", read_only=True)
    email_message_id = serializers.CharField(source="email.message_id", read_only=True)
    email_received_at = serializers.DateTimeField(source="email.received_at", read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.username", read_only=True, default=None
    )
    confidence = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()
    field_schema = serializers.SerializerMethodField()

    class Meta:
        model = Record
        fields = [
            "id", "status", "data",
            "template", "template_name",
            "email_id", "email_subject", "email_sender",
            "email_message_id", "email_received_at",
            "confidence", "review", "field_schema",
            "approved_by_name", "approved_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "status", "template", "approved_by_name", "approved_at",
            "created_at", "updated_at",
        ]

    def get_confidence(self, obj):
        return obj.extraction.confidence if obj.extraction_id else ""

    def get_review(self, obj):
        """SRS §10.4 — a practical review indicator, not a fake accuracy %."""
        schema = obj.template.fields.all()
        required = [f.name for f in schema if f.required]
        missing = [f for f in required if obj.data.get(f) in (None, "")]
        errors = ""
        if obj.extraction_id:
            errors = obj.extraction.error_message or ""
        return {
            "required_total": len(required),
            "required_found": len(required) - len(missing),
            "missing_fields": missing,
            "has_validation_errors": bool(errors),
            "ready": not missing,
        }

    def get_field_schema(self, obj):
        return RecordFieldSchemaSerializer(
            obj.template.fields.all().order_by("display_order", "id"), many=True
        ).data

    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("`data` must be a JSON object.")
        return value

    def update(self, instance, validated_data):
        # Only the `data` blob is editable, and only while still a draft.
        if instance.status != Record.Status.DRAFT:
            raise serializers.ValidationError(
                "Only draft records can be edited."
            )
        if "data" in validated_data:
            instance.data = validated_data["data"]
            instance.save(update_fields=["data", "updated_at"])
        return instance
