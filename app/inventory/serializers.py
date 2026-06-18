from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from django.utils.translation import gettext_lazy as _

from .models import Product, Supplier, Supply, SupplyProduct


class QuantityNotEditable(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _(
        "Количество товара нельзя изменять через этот эндпоинт. "
        "Оно меняется только через поставки и продажи."
    )
    default_code = "quantity_not_editable"


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = ("id", "title", "inn", "company")
        read_only_fields = ("id", "company")


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "purchase_price",
            "sale_price",
            "quantity",
            "storage",
        )
        # Количество нельзя менять напрямую через API товара — только через
        # поставки/продажи. Склад определяется автоматически по компании.
        read_only_fields = ("id", "quantity", "storage")

    def validate(self, attrs):
        # При обновлении (PUT/PATCH) попытка изменить количество отклоняется
        # явной ошибкой, а не молча игнорируется.
        if self.instance is not None and "quantity" in self.initial_data:
            try:
                requested = int(self.initial_data["quantity"])
            except (TypeError, ValueError):
                requested = None
            if requested != self.instance.quantity:
                raise QuantityNotEditable()
        return attrs


class ProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "title", "quantity", "purchase_price", "sale_price")
        read_only_fields = fields


class SupplyItemSerializer(serializers.Serializer):
    """Входной элемент поставки: id товара и количество."""

    id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class SupplyProductReadSerializer(serializers.ModelSerializer):
    product = serializers.IntegerField(source="product_id", read_only=True)
    product_title = serializers.CharField(source="product.title", read_only=True)

    class Meta:
        model = SupplyProduct
        fields = ("product", "product_title", "quantity")
        read_only_fields = fields


class SupplySerializer(serializers.ModelSerializer):
    supplier_title = serializers.CharField(source="supplier.title", read_only=True)
    items = SupplyProductReadSerializer(many=True, read_only=True)

    class Meta:
        model = Supply
        fields = ("id", "supplier", "supplier_title", "delivery_date", "items")
        read_only_fields = fields
