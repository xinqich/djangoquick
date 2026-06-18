from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("id", "email", "is_company_owner", "company", "is_active", "is_staff")
    list_display_links = ("id", "email")
    search_fields = ("email",)
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Права доступа"),
            {"fields": ("is_active", "is_staff", "is_superuser", "is_company_owner")},
        ),
        (_("Компания"), {"fields": ("company",)}),
        (_("Даты"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )
