from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductViewSet, SupplierViewSet, SupplyViewSet

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"products", ProductViewSet, basename="product")
router.register(r"supplies", SupplyViewSet, basename="supply")

urlpatterns = [
    path("", include(router.urls)),
]
