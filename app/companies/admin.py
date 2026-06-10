from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Company, Storage


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "inn", "owner")
    list_display_links = ("id", "title")
    search_fields = ("title", "inn", "owner__email")


@admin.register(Storage)
class StorageAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "address_short")
    list_select_related = ("company",)

    @admin.display(description=_("Адрес (начало)"))
    def address_short(self, obj):
        return obj.address[:80] + ("…" if len(obj.address) > 80 else "")
