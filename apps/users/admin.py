from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active")
    fieldsets = UserAdmin.fieldsets + (("Marketplace", {"fields": ("role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Marketplace", {"fields": ("email", "role", "phone")}),
    )
