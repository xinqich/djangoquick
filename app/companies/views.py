from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .helpers import get_user_company, get_user_company_storage, get_user_owned_company
from .models import Company, Storage
from .permissions import IsCompanyOwnerUser
from .serializers import (
    CompanySerializer,
    EmployeeBriefSerializer,
    LinkEmployeeSerializer,
    StorageSerializer,
)

User = get_user_model()


class CompanyViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        if self.action == "retrieve":
            return [permissions.IsAuthenticated()]
        if self.action == "me":
            return [permissions.IsAuthenticated()]
        if self.action == "attach_user_to_company":
            return [permissions.IsAuthenticated()]
        if self.action == "detach_user_from_company":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        methods=["PUT", "PATCH"],
        request=CompanySerializer,
        responses={200: CompanySerializer},
        summary="Обновить компанию текущего пользователя",
        description="Только владелец. Компания определяется по привязке пользователя.",
    )
    @extend_schema(
        methods=["DELETE"],
        summary="Удалить компанию текущего пользователя",
        description="Только владелец. Компания определяется по привязке пользователя.",
        responses={204: None},
    )
    @action(detail=False, methods=["put", "patch", "delete"], url_path="me")
    def me(self, request):
        company = get_user_owned_company(request.user)

        if request.method == "DELETE":
            company.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        partial = request.method == "PATCH"
        serializer = self.get_serializer(
            company,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(
        methods=["GET"],
        responses={200: EmployeeBriefSerializer(many=True)},
        summary="Список сотрудников компании",
        description="Только владелец компании. Компания определяется по привязке пользователя. Владелец в списке не отображается.",
    )
    @extend_schema(
        methods=["POST"],
        request=LinkEmployeeSerializer,
        responses={201: EmployeeBriefSerializer},
        summary="Привязать пользователя к компании",
        description="Укажите `user_id` или `email` (ровно одно из полей). Только владелец компании.",
    )
    @action(
        detail=False,
        methods=["get", "post"],
        url_path="attach-user-to-company",
        url_name="attach-user-to-company",
    )
    def attach_user_to_company(self, request):
        company = get_user_owned_company(request.user)
        if request.method == "GET":
            qs = (
                User.objects.filter(company_id=company.id)
                .exclude(pk=company.owner_id)
                .order_by("id")
            )
            return Response(
                EmployeeBriefSerializer(
                    qs, many=True, context={"request": request}
                ).data
            )

        serializer = LinkEmployeeSerializer(
            data=request.data,
            context={**self.get_serializer_context(), "company": company},
        )
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        return Response(
            EmployeeBriefSerializer(employee, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Отвязать сотрудника от компании",
        description="Только владелец компании. Компания определяется по привязке пользователя. Владельца отвязать нельзя.",
    )
    @action(
        detail=False,
        methods=["delete"],
        url_path=r"detach-user-from-company/(?P<employee_pk>\d+)",
        url_name="detach-user-from-company",
    )
    def detach_user_from_company(self, request, employee_pk=None):
        company = get_user_owned_company(request.user)
        try:
            target_pk = int(employee_pk)
        except (TypeError, ValueError):
            return Response(status=status.HTTP_404_NOT_FOUND)

        if target_pk == company.owner_id:
            return Response(
                {
                    "detail": _(
                        "Нельзя отвязать владельца компании через удаление сотрудника."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            employee = (
                User.objects.select_for_update()
                .filter(pk=target_pk, company_id=company.id)
                .exclude(pk=company.owner_id)
                .first()
            )
            if employee is None:
                return Response(status=status.HTTP_404_NOT_FOUND)
            employee.company = None
            employee.save(update_fields=("company",))

        return Response(status=status.HTTP_204_NO_CONTENT)


class StorageAPIView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsCompanyOwnerUser()]

    @extend_schema(
        responses={200: StorageSerializer},
        summary="Склад компании текущего пользователя",
        description="Доступен пользователям, привязанным к компании. 404, если склада ещё нет.",
    )
    def get(self, request):
        storage = get_user_company_storage(request.user)
        return Response(StorageSerializer(storage, context={"request": request}).data)

    @extend_schema(
        request=StorageSerializer,
        responses={201: StorageSerializer},
        summary="Создать склад для компании",
        description="Только владелец компании.",
    )
    def post(self, request):
        serializer = StorageSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        storage = serializer.save()
        return Response(
            StorageSerializer(storage, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        request=StorageSerializer,
        responses={200: StorageSerializer},
        summary="Обновить склад компании",
        description="Только владелец компании. 404, если склада ещё нет.",
    )
    def put(self, request):
        return self._update(request, partial=False)

    @extend_schema(
        request=StorageSerializer,
        responses={200: StorageSerializer},
        summary="Частично обновить склад компании",
        description="Только владелец компании. 404, если склада ещё нет.",
    )
    def patch(self, request):
        return self._update(request, partial=True)

    @extend_schema(
        summary="Удалить склад компании",
        description="Только владелец компании. 404, если склада ещё нет.",
        responses={204: None},
    )
    def delete(self, request):
        storage = get_user_company_storage(request.user)
        company = get_user_company(request.user)
        if company.owner_id != request.user.id:
            self.permission_denied(
                request,
                message=_("Изменение склада доступно только владельцу компании."),
            )
        storage.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _update(self, request, partial):
        storage = get_user_company_storage(request.user)
        company = get_user_company(request.user)
        if company.owner_id != request.user.id:
            self.permission_denied(
                request,
                message=_("Изменение склада доступно только владельцу компании."),
            )
        serializer = StorageSerializer(
            storage,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
