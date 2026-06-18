from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from companies.helpers import get_user_company, get_user_company_storage
from companies.permissions import HasUserCompany

from .models import Product, Supplier, Supply
from .serializers import (
    ProductListSerializer,
    ProductSerializer,
    SupplierSerializer,
    SupplyItemSerializer,
    SupplySerializer,
)
from .services import create_supply


class SupplierViewSet(viewsets.ModelViewSet):
    """CRUD по поставщикам компании. Доступно всем пользователям компании."""

    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, HasUserCompany]
    queryset = Supplier.objects.all()

    def get_queryset(self):
        return Supplier.objects.filter(
            company_id=self.request.user.company_id
        ).order_by("id")

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        serializer.save(company=company)

    @extend_schema(
        request=SupplyItemSerializer(many=True),
        responses={201: SupplySerializer},
        summary="Создать поставку от поставщика",
        description=(
            "Принимает список товаров `[{\"id\": int, \"quantity\": int}]`. "
            "Создаёт поставку, записи SupplyProduct и увеличивает остатки товаров. "
            "Доступно всем пользователям компании."
        ),
    )
    @action(detail=True, methods=["post"], url_path="supplies")
    def supplies(self, request, pk=None):
        supplier = self.get_object()
        items = SupplyItemSerializer(data=request.data, many=True)
        items.is_valid(raise_exception=True)
        supply = create_supply(supplier=supplier, items=items.validated_data)
        return Response(
            SupplySerializer(supply).data, status=status.HTTP_201_CREATED
        )


class ProductViewSet(viewsets.ModelViewSet):
    """CRUD по товарам склада компании. Количество через API не меняется.
    Доступно всем пользователям компании."""

    permission_classes = [permissions.IsAuthenticated, HasUserCompany]
    queryset = Product.objects.all()

    def get_queryset(self):
        return Product.objects.filter(
            storage__company_id=self.request.user.company_id
        ).order_by("id")

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        return ProductSerializer

    def perform_create(self, serializer):
        storage = get_user_company_storage(self.request.user)
        serializer.save(storage=storage)


class SupplyViewSet(viewsets.ReadOnlyModelViewSet):
    """Просмотр поставок компании."""

    serializer_class = SupplySerializer
    permission_classes = [permissions.IsAuthenticated, HasUserCompany]
    queryset = Supply.objects.all()

    def get_queryset(self):
        return (
            Supply.objects.filter(
                supplier__company_id=self.request.user.company_id
            )
            .select_related("supplier")
            .prefetch_related("items__product")
            .order_by("id")
        )
