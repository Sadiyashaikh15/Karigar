from django.core.management.base import BaseCommand

from apps.bookings.services import expire_stale_bookings


class Command(BaseCommand):
    help = "Cancel unpaid / unanswered bookings (run every few minutes via cron)."

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS(f"Expired {expire_stale_bookings()} booking(s)"))
