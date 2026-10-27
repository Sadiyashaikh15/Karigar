"""Business logic for bookings. Kept out of views so it is easy to test."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.providers.models import ProviderProfile

from .models import Booking
from .slots import get_free_slots


class BookingError(Exception):
    pass


class SlotUnavailable(BookingError):
    pass


@transaction.atomic
def create_booking(customer, service, start, address, notes=""):
    """Concurrency-safe: locks the provider row so two customers can't take the same slot.

    On PostgreSQL `select_for_update` takes a row lock; on SQLite writes are already
    serialised, so the same code is safe there too.
    """
    if not service.is_active:
        raise BookingError("This service is not available.")
    provider = ProviderProfile.objects.select_for_update().get(pk=service.provider_id)
    if provider.is_suspended:
        raise BookingError("This provider is currently unavailable.")
    if provider.user_id == customer.id:
        raise BookingError("You cannot book your own service.")

    day = timezone.localtime(start).date()
    if start not in get_free_slots(provider, service, day):
        raise SlotUnavailable("That slot is no longer available. Please pick another.")

    amount = service.price
    commission = (amount * Decimal(settings.COMMISSION_PERCENT) / 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return Booking.objects.create(
        customer=customer, provider=provider, service=service,
        start=start, end=start + timedelta(minutes=service.duration_minutes),
        address=address, notes=notes, amount=amount, commission=commission,
    )


def _transition(booking_id, allowed_from, new_status, actor_check):
    with transaction.atomic():
        booking = Booking.objects.select_for_update().select_related(
            "provider__user", "customer", "service"
        ).get(pk=booking_id)
        if not actor_check(booking):
            raise PermissionError("You are not allowed to do this.")
        if booking.status not in allowed_from:
            raise BookingError(f"Cannot do this when booking is '{booking.status}'.")
        booking.status = new_status
        return booking


def accept(booking_id, user):
    b = _transition(booking_id, ["requested"], "accepted", lambda b: b.provider.user_id == user.id)
    b.accepted_at = timezone.now()
    b.save(update_fields=["status", "accepted_at", "updated_at"])
    return b


def reject(booking_id, user):
    b = _transition(booking_id, ["requested"], "rejected", lambda b: b.provider.user_id == user.id)
    b.save(update_fields=["status", "updated_at"])
    return b


def start_job(booking_id, user):
    b = _transition(booking_id, ["paid"], "in_progress", lambda b: b.provider.user_id == user.id)
    b.save(update_fields=["status", "updated_at"])
    return b


def complete(booking_id, user):
    from apps.payments.services import release_payout

    b = _transition(booking_id, ["in_progress"], "completed", lambda b: b.provider.user_id == user.id)
    b.save(update_fields=["status", "updated_at"])
    ProviderProfile.objects.filter(pk=b.provider_id).update(
        completed_jobs=F("completed_jobs") + 1
    )
    release_payout(b)
    return b


def cancel(booking_id, user):
    from apps.payments.services import refund_payment

    def allowed(b):
        return user.id in (b.customer_id, b.provider.user_id)

    b = _transition(booking_id, ["requested", "accepted", "paid"], "cancelled", allowed)
    b.save(update_fields=["status", "updated_at"])
    if b.provider.user_id == user.id and b.accepted_at:
        ProviderProfile.objects.filter(pk=b.provider_id).update(
            cancelled_jobs=F("cancelled_jobs") + 1
        )
    refund_payment(b)  # no-op unless it was paid
    return b


def expire_stale_bookings():
    """Cancel bookings that were never accepted / never paid. Run via cron or `manage.py expire_bookings`."""
    now = timezone.now()
    pay_deadline = now - timedelta(minutes=settings.PAYMENT_WINDOW_MINUTES)
    unpaid = Booking.objects.filter(status="accepted", accepted_at__lt=pay_deadline)
    stale_requests = Booking.objects.filter(
        status="requested", created_at__lt=now - timedelta(hours=24)
    )
    n1 = unpaid.update(status="cancelled")
    n2 = stale_requests.update(status="cancelled")
    return n1 + n2
