from django.contrib import admin

from .models import Product, Supplier, Supply, SupplyProduct


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "inn", "company")
    list_display_links = ("id", "title")
    list_select_related = ("company",)
    search_fields = ("title", "inn", "company__title")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "quantity",
        "purchase_price",
        "sale_price",
        "storage",
    )
    list_display_links = ("id", "title")
    list_select_related = ("storage",)
    search_fields = ("title",)


class SupplyProductInline(admin.TabularInline):
    model = SupplyProduct
    extra = 0


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    list_display = ("id", "supplier", "delivery_date")
    list_display_links = ("id",)
    list_select_related = ("supplier",)
    inlines = (SupplyProductInline,)


@admin.register(SupplyProduct)
class SupplyProductAdmin(admin.ModelAdmin):
    list_display = ("id", "supply", "product", "quantity")
    list_select_related = ("supply", "product")
