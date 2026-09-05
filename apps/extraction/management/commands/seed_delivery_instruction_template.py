"""Seed the "Delivery Instruction" template.

Modelled on the real ABA FASHIONS "Delivery Instruction / #QID" email:
a columnar HTML data table (header row + one data row) plus three values that
appear only in the free-text paragraph (buyer, delivery date, warehouse) and
are therefore marked ``is_free_text=True`` so the pipeline routes them to the
focused AI extractor instead of the deterministic table parser.

Usage:
    uv run python manage.py seed_delivery_instruction_template
    uv run python manage.py seed_delivery_instruction_template --user admin
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.template.models import Template, TemplateField

TEMPLATE_NAME = "Delivery Instruction"

# name, label, data_type, required, is_free_text, ai_instruction
FIELDS = [
    # --- columns present in the email's HTML data table --------------------- #
    ("order_no", "Order No", "string", True, False,
     "The order / PO reference for this shipment line."),
    ("cps_id", "CPS ID", "string", True, False,
     "The CPS identifier from the data table."),
    ("special_code", "Special Code", "string", False, False, ""),
    ("style_name", "Style Name", "string", True, False,
     "The garment style / product description."),
    ("assorted_qty", "Assorted Qty", "integer", False, False,
     "Assorted quantity as a plain integer."),
    ("unassorted_qty", "Unassorted Qty", "integer", False, False,
     "Unassorted quantity as a plain integer."),
    ("total_cartons", "Total Cartons", "integer", True, False,
     "Total number of cartons as a plain integer."),
    ("final_destination", "Final Destination", "string", False, False,
     "Final destination port / country from the table."),
    ("delivery_place_of_vendor", "Delivery Place of Vendor", "string", False, False, ""),
    ("target_shipment", "Target Shipment", "string", False, False,
     "Target shipment date or week as written in the table."),
    ("shipment_route", "Shipment Route", "string", False, False, ""),
    ("lc_ref_no", "LC Ref No", "string", False, False,
     "Letter-of-credit reference number."),
    ("lc_ref_bank", "LC Ref Bank", "string", False, False,
     "Bank that issued the letter of credit."),
    ("delivery_location", "Delivery Location", "string", False, False, ""),
    ("vehicle_type", "Vehicle Type", "string", False, False,
     "Requested transport / vehicle type (e.g. covered van, trailer)."),
    ("gtip", "GTIP", "string", False, False,
     "GTIP / HS customs tariff code."),
    # --- values that appear only in the free-text paragraph ---------------- #
    ("buyer_name", "Buyer Name", "string", True, True,
     "The buyer / customer company the goods are being produced for "
     "(named in the greeting or opening sentence, NOT in the table)."),
    ("delivery_date", "Delivery Date", "date", True, True,
     "The date the cargo must be delivered / must reach the warehouse. "
     "Format YYYY-MM-DD; drop any time-of-day component."),
    ("delivery_warehouse", "Delivery Warehouse", "string", True, True,
     "The destination warehouse / delivery point named in the free text "
     "(e.g. 'Chittagong Warehouse'), NOT the final shipping destination."),
]


class Command(BaseCommand):
    help = "Create (or refresh) the 'Delivery Instruction' template for a user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Username to own the template (defaults to the first superuser).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        if options.get("user"):
            try:
                user = User.objects.get(username=options["user"])
            except User.DoesNotExist as exc:
                raise CommandError(f"No user named {options['user']!r}") from exc
        else:
            user = User.objects.filter(is_superuser=True).order_by("id").first()
            if user is None:
                raise CommandError("No superuser exists; create one or pass --user.")

        template, created = Template.objects.get_or_create(
            user=user,
            name=TEMPLATE_NAME,
            defaults={
                "description": (
                    "Vendor delivery-instruction emails (columnar data table + "
                    "free-text delivery date / warehouse / buyer)."
                ),
                "source_file": "ABA FASHIONS LTD delivery instruction (sample)",
            },
        )

        if not created:
            template.fields.all().delete()
            template.version += 1
            template.save(update_fields=["version"])

        for order, (name, label, dtype, required, is_free_text, hint) in enumerate(FIELDS):
            TemplateField.objects.create(
                template=template,
                name=name,
                label=label,
                data_type=dtype,
                required=required,
                is_free_text=is_free_text,
                ai_instruction=hint,
                display_order=order,
            )

        verb = "Created" if created else f"Refreshed (v{template.version})"
        table_n = sum(1 for f in FIELDS if not f[4])
        free_n = sum(1 for f in FIELDS if f[4])
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} template {TEMPLATE_NAME!r} for user {user.username!r} "
                f"— {len(FIELDS)} fields ({table_n} table, {free_n} free-text)."
            )
        )
