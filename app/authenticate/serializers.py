from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from companies.models import Company

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, label=_("Пароль"))
    password_confirm = serializers.CharField(
        write_only=True, min_length=8, label=_("Подтверждение пароля")
    )

    class Meta:
        model = User
        fields = ("id", "email", "password", "password_confirm")
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": _("Пароли не совпадают.")}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD


class CompanyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "title", "inn")
        read_only_fields = fields


class AboutMeSerializer(serializers.ModelSerializer):
    company = CompanyBriefSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "company")
        read_only_fields = fields
