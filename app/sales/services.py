from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from companies.models import Storage
from inventory.models import Product

from .models import ProductSale, Sale


class InsufficientStock(Exception):
    """Недостаточно остатков для продажи.

    ``availability`` — словарь вида ``{"<товар> available only": <остаток>}``
    по каждому недостающему товару.
    """

    def __init__(self, availability):
        self.availability = availability
        super().__init__("insufficient stock")


@transaction.atomic
def create_sale(*, company, buyer_name, product_sales, sale_date=None):
    """Создать продажу, проверив остатки и уменьшив количество товаров.

    ``product_sales`` — список словарей вида
    ``{"product_id": <id>, "quantity": <int>}``. Все товары должны
    принадлежать складу компании. Если хотя бы одного товара недостаточно,
    продажа не создаётся, а возвращается ошибка 400 с перечнем доступных
    количеств по каждому недостающему товару.
    """
    if not product_sales:
        raise serializers.ValidationError(
            {"detail": _("Список товаров продажи не может быть пустым.")}
        )

    product_ids = [item["product_id"] for item in product_sales]
    if len(product_ids) != len(set(product_ids)):
        raise serializers.ValidationError(
            {"detail": _("Товар не должен повторяться в одной продаже.")}
        )

    try:
        storage = company.storage
    except Storage.DoesNotExist as exc:
        raise serializers.ValidationError(
            {"detail": _("У компании ещё нет склада для продажи товаров.")}
        ) from exc

    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(
            id__in=product_ids, storage=storage
        )
    }

    missing = [pid for pid in product_ids if pid not in products]
    if missing:
        raise serializers.ValidationError(
            {
                "detail": _("Товары не найдены на складе компании."),
                "products": missing,
            }
        )

    insufficient = {}
    for item in product_sales:
        product = products[item["product_id"]]
        if product.quantity < item["quantity"]:
            insufficient[f"{product.title} available only"] = product.quantity
    if insufficient:
        raise InsufficientStock(insufficient)

    sale = Sale.objects.create(
        company=company,
        buyer_name=buyer_name,
        sale_date=sale_date or timezone.localdate(),
    )

    ProductSale.objects.bulk_create(
        [
            ProductSale(
                sale=sale,
                product=products[item["product_id"]],
                quantity=item["quantity"],
            )
            for item in product_sales
        ]
    )

    for item in product_sales:
        Product.objects.filter(pk=item["product_id"]).update(
            quantity=F("quantity") - item["quantity"]
        )

    return sale


@transaction.atomic
def delete_sale(sale):
    """Удалить продажу, вернув проданные количества на склад.

    Количества из product_sale прибавляются обратно к ``Product.quantity``,
    затем удаляются записи product_sale и сама продажа.
    """
    items = list(
        ProductSale.objects.filter(sale=sale).values("product_id", "quantity")
    )
    product_ids = [item["product_id"] for item in items]

    # Блокируем строки товаров на время восстановления остатков.
    list(Product.objects.select_for_update().filter(pk__in=product_ids))

    for item in items:
        Product.objects.filter(pk=item["product_id"]).update(
            quantity=F("quantity") + item["quantity"]
        )

    ProductSale.objects.filter(sale=sale).delete()
    sale.delete()
