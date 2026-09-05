from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.emails.gmail_client import fetch_new_messages, get_gmail_service
from apps.emails.models import Attachment, Email


class Command(BaseCommand):
    help = "Poll Gmail for new messages and store them, skipping duplicates by message_id."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            required=True,
            help="Username to associate fetched emails with, e.g. --user admin.",
        )
        parser.add_argument("--max-results", type=int, default=25)

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["user"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            available = ", ".join(
                User.objects.filter(is_active=True).values_list("username", flat=True)
            ) or "(none)"
            raise CommandError(f'No user named "{username}". Available: {available}')
        if not user.is_active:
            raise CommandError(f'User "{username}" is inactive.')

        self.stdout.write("Connecting to Gmail…")
        service = get_gmail_service()

        self.stdout.write("Fetching messages…")
        messages = fetch_new_messages(service, max_results=options["max_results"])

        created_count = 0
        skipped_count = 0

        attachment_count = 0

        for msg_data in messages:
            email, created = Email.objects.get_or_create(
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
                for att in msg_data.get("attachments", []):
                    Attachment.objects.create(
                        email=email,
                        filename=att["filename"],
                        content_type=att["content_type"],
                        size=att["size"],
                        file=ContentFile(att["content"], name=att["filename"]),
                    )
                    attachment_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created_count} new email(s) saved ({attachment_count} attachment(s)), "
                f"{skipped_count} duplicate(s) skipped."
            )
        )
