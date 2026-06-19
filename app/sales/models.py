from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from inventory.models import Product


class Sale(models.Model):
    buyer_name = models.CharField(_("Покупатель"), max_length=255)
    sale_date = models.DateField(_("Дата продажи"), default=timezone.localdate)
    company = models.ForeignKey(
        "companies.Company",
        verbose_name=_("Компания"),
        on_delete=models.CASCADE,
        related_name="sales",
    )
    products = models.ManyToManyField(
        Product,
        verbose_name=_("Товары"),
        through="ProductSale",
        related_name="sales",
    )

    class Meta:
        verbose_name = _("Продажа")
        verbose_name_plural = _("Продажи")

    def __str__(self):
        return f"{self.buyer_name}: {self.sale_date}"


class ProductSale(models.Model):
    sale = models.ForeignKey(
        Sale,
        verbose_name=_("Продажа"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        verbose_name=_("Товар"),
        on_delete=models.CASCADE,
        related_name="sale_items",
    )
    quantity = models.PositiveIntegerField(_("Количество"))

    class Meta:
        verbose_name = _("Товар в продаже")
        verbose_name_plural = _("Товары в продаже")

    def __str__(self):
        return f"{self.sale_id} / {self.product_id}: {self.quantity}"
