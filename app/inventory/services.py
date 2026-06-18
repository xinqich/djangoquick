from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from companies.models import Storage

from .models import Product, Supply, SupplyProduct


@transaction.atomic
def create_supply(*, supplier, items):
    """Создать поставку, записать SupplyProduct и увеличить остатки товаров.

    ``items`` — список словарей вида ``{"id": <product_id>, "quantity": <int>}``.
    Все товары должны принадлежать складу компании поставщика.
    """
    if not items:
        raise serializers.ValidationError(
            {"detail": _("Список товаров поставки не может быть пустым.")}
        )

    product_ids = [item["id"] for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise serializers.ValidationError(
            {"detail": _("Товар не должен повторяться в одной поставке.")}
        )

    try:
        storage = supplier.company.storage
    except Storage.DoesNotExist as exc:
        raise serializers.ValidationError(
            {"detail": _("У компании ещё нет склада для поставки товаров.")}
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

    supply = Supply.objects.create(
        supplier=supplier, delivery_date=timezone.localdate()
    )

    SupplyProduct.objects.bulk_create(
        [
            SupplyProduct(
                supply=supply,
                product=products[item["id"]],
                quantity=item["quantity"],
            )
            for item in items
        ]
    )

    for item in items:
        Product.objects.filter(pk=item["id"]).update(
            quantity=F("quantity") + item["quantity"]
        )

    return supply
