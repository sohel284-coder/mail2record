from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.emails.models import Email
from apps.extraction.pipeline import run_extraction
from apps.template.models import Template


class Command(BaseCommand):
    help = "Run extraction on all unprocessed emails against a given template."

    def add_arguments(self, parser):
        parser.add_argument("--template", type=str, required=True, help="Template name, e.g. CSB")
        parser.add_argument("--user", type=str, help="Username (defaults to first superuser)")

    def handle(self, *args, **options):
        User = get_user_model()
        user = User.objects.get(username=options["user"]) if options["user"] else User.objects.filter(is_superuser=True).first()

        template = Template.objects.get(user=user, name=options["template"])
        emails = Email.objects.filter(user=user, is_processed=False)

        if not emails.exists():
            self.stdout.write("No unprocessed emails found.")
            return

        for email in emails:
            self.stdout.write(f"Processing: {email.subject!r}...")
            record = run_extraction(email, template)
            if record:
                self.stdout.write(self.style.SUCCESS(f"  → Draft record #{record.id} created ({record.data})"))
            else:
                self.stdout.write(self.style.ERROR(f"  → Extraction failed for {email.subject!r}"))