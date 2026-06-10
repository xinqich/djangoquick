from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CompanyViewSet, StorageAPIView

router = DefaultRouter()
router.register(r"companies", CompanyViewSet, basename="company")

urlpatterns = [
    path("storages/", StorageAPIView.as_view(), name="storage"),
    path("", include(router.urls)),
]
