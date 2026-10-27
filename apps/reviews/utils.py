import re
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

# Minimal demo list - replace with a proper library / moderation API in production
BAD_WORDS = {"fuck", "shit", "bastard", "bitch", "asshole", "madarchod", "bhenchod", "chutiya"}


def contains_profanity(text: str) -> bool:
    words = set(re.findall(r"[a-zA-Z]+", (text or "").lower()))
    return bool(words & BAD_WORDS)


def recompute_provider_rating(provider):
    """Weighted average: reviews from the last 90 days count 1.5x."""
    from .models import Review

    cutoff = timezone.now() - timedelta(days=90)
    rows = Review.objects.filter(booking__provider=provider, is_hidden=False).values_list(
        "rating", "created_at"
    )
    total_w = total = 0.0
    n = 0
    for rating, created in rows:
        w = 1.5 if created >= cutoff else 1.0
        total += rating * w
        total_w += w
        n += 1
    provider.avg_rating = round(total / total_w, 2) if total_w else 0
    provider.rating_count = n
    provider.save(update_fields=["avg_rating", "rating_count"])
