from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import Company, Storage

User = get_user_model()


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "inn", "title", "owner")
        read_only_fields = ("id", "owner")

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if self.instance is not None:
            return attrs
        if user and user.is_authenticated:
            if getattr(user, "company_id", None):
                raise serializers.ValidationError(
                    {"detail": _("Пользователь уже привязан к компании.")}
                )
            if Company.objects.filter(owner=user).exists():
                raise serializers.ValidationError(
                    {"detail": _("Пользователь уже владеет компанией.")}
                )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user
        with transaction.atomic():
            company = Company.objects.create(owner=user, **validated_data)
            user.company = company
            user.is_company_owner = True
            user.save(update_fields=("company", "is_company_owner"))
        return company


class StorageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Storage
        fields = ("id", "company", "address")
        read_only_fields = ("id", "company")

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if self.instance is not None:
            return attrs
        if not user or not user.is_authenticated:
            return attrs
        if not getattr(user, "is_company_owner", False):
            raise serializers.ValidationError(
                {"detail": _("Создание склада доступно только владельцу компании.")}
            )
        company = Company.objects.filter(owner=user).first()
        if company is None:
            raise serializers.ValidationError(
                {"detail": _("У пользователя нет компании для привязки склада.")}
            )
        if Storage.objects.filter(company=company).exists():
            raise serializers.ValidationError(
                {"detail": _("У компании уже есть склад.")}
            )
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        company = Company.objects.get(owner=request.user)
        return Storage.objects.create(company=company, **validated_data)


class EmployeeBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "company")
        read_only_fields = fields


class LinkEmployeeSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(required=False)
    email = serializers.EmailField(required=False)

    def validate(self, attrs):
        data = getattr(self, "initial_data", {}) or {}
        has_id = "user_id" in data and data["user_id"] is not None
        has_email = "email" in data and data.get("email") not in (None, "")

        if has_id and has_email:
            raise serializers.ValidationError(
                {"detail": _("Укажите либо user_id, либо email, но не оба.")}
            )
        if not has_id and not has_email:
            raise serializers.ValidationError(
                {"detail": _("Нужно указать user_id или email.")}
            )

        company = self.context.get("company")
        request = self.context.get("request")
        if company is None or request is None:
            raise serializers.ValidationError(
                {"detail": _("Некорректный контекст запроса.")}
            )

        if has_id:
            try:
                target = User.objects.get(pk=data["user_id"])
            except User.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"user_id": _("Пользователь с таким id не найден.")}
                ) from exc
        else:
            email_raw = str(data["email"]).strip()
            try:
                target = User.objects.get(email__iexact=email_raw)
            except User.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"email": _("Пользователь с таким email не найден.")}
                ) from exc

        if target.pk == request.user.pk:
            raise serializers.ValidationError(
                {"detail": _("Нельзя привязать самого себя через этот метод.")}
            )

        if getattr(target, "is_company_owner", False):
            raise serializers.ValidationError(
                {
                    "detail": _(
                        "Владелец компании не может быть добавлен сотрудником в другую компанию."
                    )
                }
            )

        if getattr(target, "company_id", None) is not None:
            raise serializers.ValidationError(
                {"detail": _("Пользователь уже привязан к компании.")}
            )

        attrs["target_user"] = target
        return attrs

    def create(self, validated_data):
        company = self.context["company"]
        target = validated_data["target_user"]
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=target.pk)
            if locked.is_company_owner:
                raise serializers.ValidationError(
                    {
                        "detail": _(
                            "Владелец компании не может быть добавлен сотрудником в другую компанию."
                        )
                    }
                )
            if locked.company_id is not None:
                raise serializers.ValidationError(
                    {"detail": _("Пользователь уже привязан к компании.")}
                )
            locked.company = company
            locked.save(update_fields=("company",))
        return locked
