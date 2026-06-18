from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Supplier(models.Model):
    title = models.CharField(_("Название"), max_length=255, unique=True)
    inn = models.CharField(_("ИНН"), max_length=12, unique=True)
    company = models.ForeignKey(
        "companies.Company",
        verbose_name=_("Компания"),
        on_delete=models.CASCADE,
        related_name="suppliers",
    )

    class Meta:
        verbose_name = _("Поставщик")
        verbose_name_plural = _("Поставщики")

    def __str__(self):
        return self.title


class Product(models.Model):
    title = models.CharField(_("Название"), max_length=255)
    purchase_price = models.DecimalField(
        _("Закупочная цена"), max_digits=12, decimal_places=2
    )
    sale_price = models.DecimalField(
        _("Цена продажи"), max_digits=12, decimal_places=2
    )
    quantity = models.PositiveIntegerField(_("Количество"), default=0)
    storage = models.ForeignKey(
        "companies.Storage",
        verbose_name=_("Склад"),
        on_delete=models.CASCADE,
        related_name="products",
    )

    class Meta:
        verbose_name = _("Товар")
        verbose_name_plural = _("Товары")

    def __str__(self):
        return self.title


class Supply(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        verbose_name=_("Поставщик"),
        on_delete=models.CASCADE,
        related_name="supplies",
    )
    delivery_date = models.DateField(_("Дата поставки"), default=timezone.localdate)
    products = models.ManyToManyField(
        Product,
        verbose_name=_("Товары"),
        through="SupplyProduct",
        related_name="supplies",
    )

    class Meta:
        verbose_name = _("Поставка")
        verbose_name_plural = _("Поставки")

    def __str__(self):
        return f"{self.supplier_id}: {self.delivery_date}"


class SupplyProduct(models.Model):
    supply = models.ForeignKey(
        Supply,
        verbose_name=_("Поставка"),
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        verbose_name=_("Товар"),
        on_delete=models.CASCADE,
        related_name="supply_items",
    )
    quantity = models.PositiveIntegerField(_("Количество"))

    class Meta:
        verbose_name = _("Товар в поставке")
        verbose_name_plural = _("Товары в поставке")

    def __str__(self):
        return f"{self.supply_id} / {self.product_id}: {self.quantity}"
