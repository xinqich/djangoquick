from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from companies.helpers import get_user_company
from companies.permissions import HasUserCompany

from .models import Sale
from .serializers import (
    SaleCreateSerializer,
    SaleSerializer,
    SaleUpdateSerializer,
)
from .services import InsufficientStock, create_sale, delete_sale


class SalePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


@extend_schema(tags=["sales"])
class SaleViewSet(viewsets.ModelViewSet):
    """Продажи компании. Доступно всем пользователям компании.

    Создание и удаление меняют остатки товаров. Редактировать можно только
    имя покупателя и дату продажи — количество проданных товаров неизменно.
    """

    permission_classes = [permissions.IsAuthenticated, HasUserCompany]
    pagination_class = SalePagination
    queryset = Sale.objects.all()
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return SaleCreateSerializer
        if self.action in ("update", "partial_update"):
            return SaleUpdateSerializer
        return SaleSerializer

    def get_queryset(self):
        qs = (
            Sale.objects.filter(company_id=self.request.user.company_id)
            .prefetch_related("items__product")
            .order_by("-sale_date", "-id")
        )
        date_from = self.request.query_params.get("date_from")
        if date_from:
            parsed = parse_date(date_from)
            if parsed is not None:
                qs = qs.filter(sale_date__gte=parsed)
        date_to = self.request.query_params.get("date_to")
        if date_to:
            parsed = parse_date(date_to)
            if parsed is not None:
                qs = qs.filter(sale_date__lte=parsed)
        return qs

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="date_from",
                type=str,
                description="Начало периода (YYYY-MM-DD), фильтр по дате продажи.",
            ),
            OpenApiParameter(
                name="date_to",
                type=str,
                description="Конец периода (YYYY-MM-DD), фильтр по дате продажи.",
            ),
        ],
        responses={200: SaleSerializer(many=True)},
        summary="Список продаж компании",
        description=(
            "Постранично. Опционально фильтруется по периоду через "
            "`date_from` и `date_to`. Доступно всем пользователям компании."
        ),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=SaleCreateSerializer,
        responses={201: SaleSerializer},
        summary="Создать продажу",
        description=(
            "Проверяет остатки товаров, при достаточном количестве создаёт "
            "продажу и уменьшает остатки. При нехватке возвращает 400 с "
            "доступным количеством по каждому недостающему товару."
        ),
    )
    def create(self, request, *args, **kwargs):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = get_user_company(request.user)
        try:
            sale = create_sale(
                company=company,
                buyer_name=serializer.validated_data["buyer_name"],
                product_sales=serializer.validated_data["product_sales"],
                sale_date=serializer.validated_data.get("sale_date"),
            )
        except InsufficientStock as exc:
            return Response(exc.availability, status=status.HTTP_400_BAD_REQUEST)
        return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=SaleUpdateSerializer,
        responses={200: SaleSerializer},
        summary="Изменить продажу",
        description=(
            "Разрешено менять только имя покупателя и дату продажи "
            "(не позже текущей даты). Количество проданных товаров изменить нельзя."
        ),
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SaleUpdateSerializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        instance.refresh_from_db()
        return Response(SaleSerializer(instance).data)

    @extend_schema(
        summary="Удалить продажу",
        description=(
            "Возвращает проданные количества на склад, удаляет записи "
            "product_sale и саму продажу."
        ),
        responses={204: None},
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_sale(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
