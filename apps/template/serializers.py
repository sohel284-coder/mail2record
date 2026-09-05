from rest_framework import serializers

from .models import Template, TemplateField


class TemplateFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateField
        fields = [
            "id",
            "name",
            "label",
            "data_type",
            "required",
            "description",
            "ai_instruction",
            "display_order",
        ]


class TemplateSerializer(serializers.ModelSerializer):
    fields = TemplateFieldSerializer(many=True)

    class Meta:
        model = Template
        fields = [
            "id",
            "name",
            "description",
            "source_file",
            "version",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
            "fields",
        ]
        # is_default is only ever changed via the dedicated /set-default/ action
        # so a plain save from the edit form can't accidentally clear it.
        read_only_fields = ["version", "is_default", "created_at", "updated_at"]

    def validate_fields(self, value):
        if not value:
            raise serializers.ValidationError("At least one field is required.")
        names = [f["name"] for f in value]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Field names must be unique within a template.")
        return value

    def create(self, validated_data):
        fields_data = validated_data.pop("fields")
        user = self.context["request"].user
        template = Template.objects.create(user=user, **validated_data)
        self._sync_fields(template, fields_data)
        return template

    def update(self, instance, validated_data):
        fields_data = validated_data.pop("fields", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if fields_data is not None:
            instance.fields.all().delete()
            self._sync_fields(instance, fields_data)
        return instance

    def _sync_fields(self, template, fields_data):
        TemplateField.objects.bulk_create(
            [TemplateField(template=template, **field_data) for field_data in fields_data]
        )
