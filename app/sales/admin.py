from django.contrib import admin

from .models import ProductSale, Sale


class ProductSaleInline(admin.TabularInline):
    model = ProductSale
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer_name", "sale_date", "company")
    list_display_links = ("id", "buyer_name")
    list_select_related = ("company",)
    search_fields = ("buyer_name", "company__title")
    inlines = (ProductSaleInline,)
