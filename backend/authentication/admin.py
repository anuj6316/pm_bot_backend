from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ["email", "username", "role", "is_staff"]
    fieldsets = UserAdmin.fieldsets + (
        ("Project Access", {"fields": ("projects", "role", "phone_number")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Project Access", {"fields": ("projects", "role", "phone_number")}),
    )
