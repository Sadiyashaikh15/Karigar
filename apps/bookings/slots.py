"""Slot generation: availability windows -> fixed-length slots, minus bookings/time-off/past."""
from datetime import datetime, time, timedelta

from django.utils import timezone


def get_free_slots(provider, service, day):
    from apps.bookings.models import Booking
    from apps.providers.models import Availability, TimeOff

    if TimeOff.objects.filter(provider=provider, date=day).exists():
        return []

    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(day, time.min), tz)
    day_end = day_start + timedelta(days=1)

    busy = list(
        Booking.objects.filter(
            provider=provider, status__in=Booking.ACTIVE_STATUSES,
            start__lt=day_end, end__gt=day_start,
        ).values_list("start", "end")
    )
    duration = timedelta(minutes=service.duration_minutes)
    now = timezone.now()
    slots = []
    for w in Availability.objects.filter(provider=provider, day_of_week=day.weekday()):
        cur = timezone.make_aware(datetime.combine(day, w.start_time), tz)
        window_end = timezone.make_aware(datetime.combine(day, w.end_time), tz)
        while cur + duration <= window_end:
            end = cur + duration
            if cur > now and not any(cur < b_end and end > b_start for b_start, b_end in busy):
                slots.append(cur)
            cur += duration
    return slots
