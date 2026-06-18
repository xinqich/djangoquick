from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    AboutMeSerializer,
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
)


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"detail": _("Регистрация прошла успешно.")},
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    pass


@extend_schema(
    summary="Текущий пользователь",
    description="Электронная почта и компания (если пользователь к ней привязан).",
    responses={200: AboutMeSerializer},
)
class AboutMeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = AboutMeSerializer(request.user, context={"request": request})
        return Response(serializer.data)
