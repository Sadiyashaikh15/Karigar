from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=8, blank=True, default="🛠️")

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProviderProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="provider_profile"
    )
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    city = models.CharField(max_length=80, blank=True)
    latitude = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.FloatField(
        null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    service_radius_km = models.PositiveSmallIntegerField(default=10)
    is_verified = models.BooleanField(default=False, help_text="Verified by admin")
    is_suspended = models.BooleanField(default=False)
    avg_rating = models.FloatField(default=0)
    rating_count = models.PositiveIntegerField(default=0)
    completed_jobs = models.PositiveIntegerField(default=0)
    cancelled_jobs = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Provider<{self.user.username}>"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def completion_rate(self):
        total = self.completed_jobs + self.cancelled_jobs
        return 1.0 if total == 0 else self.completed_jobs / total


class Service(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="services")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="services")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(1)])
    duration_minutes = models.PositiveSmallIntegerField(
        default=60, validators=[MinValueValidator(15), MaxValueValidator(480)]
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.provider.user.username})"


class Availability(models.Model):
    DAYS = [(0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri"), (5, "Sat"), (6, "Sun")]
    provider = models.ForeignKey(
        ProviderProfile, on_delete=models.CASCADE, related_name="availability"
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["day_of_week", "start_time"]
        verbose_name_plural = "availability"

    def __str__(self):
        return f"{self.provider} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class TimeOff(models.Model):
    provider = models.ForeignKey(ProviderProfile, on_delete=models.CASCADE, related_name="time_off")
    date = models.DateField()
    reason = models.CharField(max_length=120, blank=True)

    class Meta:
        unique_together = ("provider", "date")
        ordering = ["date"]
