from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.emails.gmail_client import fetch_new_messages, get_gmail_service
from apps.emails.models import Email


class Command(BaseCommand):
    help = "Poll Gmail for new messages and store them, skipping duplicates by message_id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Username to associate fetched emails with (defaults to first superuser).",
        )
        parser.add_argument("--max-results", type=int, default=25)

    def handle(self, *args, **options):
        User = get_user_model()
        if options["user"]:
            user = User.objects.get(username=options["user"])
        else:
            user = User.objects.filter(is_superuser=True).first()

        if not user:
            self.stderr.write("No user found to associate emails with.")
            return

        self.stdout.write("Connecting to Gmail…")
        service = get_gmail_service()

        self.stdout.write("Fetching messages…")
        messages = fetch_new_messages(service, max_results=options["max_results"])

        created_count = 0
        skipped_count = 0

        for msg_data in messages:
            _, created = Email.objects.get_or_create(
                message_id=msg_data["message_id"],
                defaults={
                    "user": user,
                    "sender": msg_data["sender"],
                    "recipient": msg_data["recipient"],
                    "subject": msg_data["subject"],
                    "body_text": msg_data["body_text"],
                    "body_html": msg_data["body_html"],
                    "received_at": msg_data["received_at"],
                    "source": msg_data["source"],
                },
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created_count} new email(s) saved, {skipped_count} duplicate(s) skipped."
            )
        )