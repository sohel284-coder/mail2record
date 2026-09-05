from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.emails.models import Attachment, Email, EmailAccount
from apps.emails.providers import get_email_provider


class Command(BaseCommand):
    help = (
        "Poll every connected mailbox for new messages and store them, skipping "
        "duplicates by message_id. Mailboxes are configured per-user from the "
        "Settings page (Gmail OAuth or IMAP)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            type=str,
            help="Only sync this username's mailbox (default: every active mailbox).",
        )
        parser.add_argument("--max-results", type=int, default=25)

    def handle(self, *args, **options):
        accounts = EmailAccount.objects.filter(is_active=True).select_related("user")
        if options["user"]:
            accounts = accounts.filter(user__username=options["user"])

        if not accounts.exists():
            who = f' for "{options["user"]}"' if options["user"] else ""
            self.stdout.write(f"No mailbox to sync{who}. Connect one from Settings.")
            return

        for account in accounts:
            self._sync_account(account, options["max_results"])

    def _sync_account(self, account, max_results):
        self.stdout.write(f"Syncing {account.email_address} ({account.provider})…")
        try:
            messages = get_email_provider(account).fetch_new_messages(
                max_results=max_results
            )
        except Exception as exc:
            account.mark_synced(ok=False, error=str(exc))
            self.stderr.write(self.style.ERROR(f"  Failed: {exc}"))
            return

        created = skipped = attachments = 0
        for msg_data in messages:
            email, was_created = Email.objects.get_or_create(
                message_id=msg_data["message_id"],
                defaults={
                    "user": account.user,
                    "sender": msg_data["sender"],
                    "recipient": msg_data["recipient"],
                    "subject": msg_data["subject"],
                    "body_text": msg_data["body_text"],
                    "body_html": msg_data["body_html"],
                    "received_at": msg_data["received_at"],
                    "source": msg_data["source"],
                },
            )
            if not was_created:
                skipped += 1
                continue
            created += 1
            for att in msg_data.get("attachments", []):
                Attachment.objects.create(
                    email=email,
                    filename=att["filename"],
                    content_type=att["content_type"],
                    size=att["size"],
                    file=ContentFile(att["content"], name=att["filename"]),
                )
                attachments += 1

        account.mark_synced(ok=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"  {created} new ({attachments} attachment(s)), {skipped} duplicate(s) skipped."
            )
        )
