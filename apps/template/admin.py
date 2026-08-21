from django.contrib import admin
from .models import Template, TemplateField


class TemplateFieldInline(admin.TabularInline):
    model = TemplateField
    extra = 1


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "version", "is_active", "created_at")
    list_filter = ("is_active",)
    inlines = [TemplateFieldInline]