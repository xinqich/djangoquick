from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import ProductSale, Sale


class ProductSaleItemSerializer(serializers.Serializer):
    """Входной элемент продажи: id товара и количество."""

    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)


class SaleCreateSerializer(serializers.Serializer):
    """Тело запроса на создание продажи."""

    buyer_name = serializers.CharField(max_length=255)
    sale_date = serializers.DateField(required=False)
    product_sales = ProductSaleItemSerializer(many=True)

    def validate_product_sales(self, value):
        if not value:
            raise serializers.ValidationError(
                _("Список товаров продажи не может быть пустым.")
            )
        return value

    def validate_sale_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(
                _("Дата продажи не может быть позже текущей даты.")
            )
        return value


class ProductSaleReadSerializer(serializers.ModelSerializer):
    product = serializers.IntegerField(source="product_id", read_only=True)
    product_title = serializers.CharField(source="product.title", read_only=True)

    class Meta:
        model = ProductSale
        fields = ("product", "product_title", "quantity")
        read_only_fields = fields


class SaleSerializer(serializers.ModelSerializer):
    items = ProductSaleReadSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ("id", "buyer_name", "sale_date", "company", "items")
        read_only_fields = fields


class SaleUpdateSerializer(serializers.ModelSerializer):
    """Редактирование продажи: разрешены только покупатель и дата продажи.

    Количество проданных товаров менять нельзя — для этого продажу нужно
    удалить (вернув товары на склад) и создать заново.
    """

    items = ProductSaleReadSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ("id", "buyer_name", "sale_date", "company", "items")
        read_only_fields = ("id", "company", "items")

    def validate(self, attrs):
        if "product_sales" in self.initial_data or "items" in self.initial_data:
            raise serializers.ValidationError(
                {
                    "detail": _(
                        "Изменение проданных товаров и их количества запрещено. "
                        "Удалите продажу и создайте новую."
                    )
                }
            )
        return attrs

    def validate_sale_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(
                _("Дата продажи не может быть позже текущей даты.")
            )
        return value
