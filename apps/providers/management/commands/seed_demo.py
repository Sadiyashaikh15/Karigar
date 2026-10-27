"""python manage.py seed_demo  -> creates demo categories, providers, customer & admin (Pune area)."""
from datetime import time

from django.core.management.base import BaseCommand

from apps.providers.models import Availability, Category, ProviderProfile, Service
from apps.users.models import User

CATEGORIES = [
    ("Electrician", "electrician", "⚡"), ("Plumber", "plumber", "🚰"),
    ("Home Tutor", "tutor", "📚"), ("Tailor", "tailor", "🧵"),
    ("Mechanic", "mechanic", "🔧"), ("AC Repair", "ac-repair", "❄️"),
    ("Cleaning", "cleaning", "🧹"), ("Carpenter", "carpenter", "🪚"),
]

# username, full name, city, lat, lng, category slug, title, price, minutes, rating, count, verified, bio
PROVIDERS = [
    ("ramesh_elec", "Ramesh Patil", "Kothrud, Pune", 18.5074, 73.8077, "electrician",
     "Home wiring & fan/light repair", 350, 60, 4.6, 48, True, "12 years experience. Switchboards, MCB, inverter wiring."),
    ("sunita_tutor", "Sunita Kulkarni", "Aundh, Pune", 18.5590, 73.8077, "tutor",
     "Maths & Science (Class 8-10)", 500, 60, 4.8, 32, True, "B.Ed with 8 years of teaching experience. CBSE & State board."),
    ("imran_plumber", "Imran Shaikh", "Hadapsar, Pune", 18.5089, 73.9260, "plumber",
     "Leak fixing & tap installation", 300, 45, 4.2, 21, False, "Quick response, same-day service."),
    ("meena_tailor", "Meena Joshi", "Shivajinagar, Pune", 18.5308, 73.8475, "tailor",
     "Blouse stitching & alterations", 250, 30, 4.9, 77, True, "Boutique-quality stitching at home-service rates."),
    ("vijay_mech", "Vijay Jadhav", "Wakad, Pune", 18.5981, 73.7600, "mechanic",
     "Two-wheeler service at your doorstep", 400, 90, 4.4, 39, True, "Authorised-service trained mechanic."),
    ("anil_ac", "Anil More", "Baner, Pune", 18.5590, 73.7868, "ac-repair",
     "AC service & gas refill", 700, 90, 4.5, 56, True, "All brands. 90-day service warranty."),
]


class Command(BaseCommand):
    help = "Seed demo data"

    def handle(self, *args, **opts):
        cats = {}
        for name, slug, icon in CATEGORIES:
            cats[slug], _ = Category.objects.get_or_create(slug=slug, defaults={"name": name, "icon": icon})

        for (uname, full, city, lat, lng, slug, title, price, mins, rating, count, ver, bio) in PROVIDERS:
            first, last = full.split(" ", 1)
            user, created = User.objects.get_or_create(
                username=uname,
                defaults={"email": f"{uname}@example.com", "first_name": first, "last_name": last,
                          "role": "provider"},
            )
            if created:
                user.set_password("demo123")
                user.save()
            prof, _ = ProviderProfile.objects.get_or_create(user=user)
            prof.bio, prof.city, prof.latitude, prof.longitude = bio, city, lat, lng
            prof.is_verified, prof.avg_rating, prof.rating_count = ver, rating, count
            prof.experience_years = 5 + count % 8
            prof.completed_jobs = count
            prof.save()
            if not prof.services.exists():
                Service.objects.create(provider=prof, category=cats[slug], title=title,
                                       price=price, duration_minutes=mins,
                                       description=f"{title} by {full}.")
            if not prof.availability.exists():
                for d in range(0, 6):  # Mon-Sat
                    Availability.objects.create(provider=prof, day_of_week=d,
                                                start_time=time(9, 0), end_time=time(18, 0))

        if not User.objects.filter(username="customer").exists():
            User.objects.create_user("customer", "customer@example.com", "demo123",
                                     first_name="Demo", last_name="Customer", role="customer")
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin123")

        self.stdout.write(self.style.SUCCESS(
            "Seeded! Logins -> customer/demo123 | ramesh_elec/demo123 (provider) | admin/admin123"))
