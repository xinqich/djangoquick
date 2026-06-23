import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from authenticate.models import User
from inventory.models import Product
from sales.models import ProductSale, Sale


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def owner(db):
    return User.objects.create_user(email="owner@example.com", password="secretpass12")


@pytest.fixture
def employee(db):
    return User.objects.create_user(email="emp@example.com", password="secretpass12")


@pytest.fixture
def outsider(db):
    return User.objects.create_user(email="out@example.com", password="secretpass12")


def auth(client: APIClient, email: str, password: str = "secretpass12") -> None:
    resp = client.post(
        reverse("auth-login"), {"email": email, "password": password}, format="json"
    )
    assert resp.status_code == status.HTTP_200_OK
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")


def make_company(client, owner, *, inn="7707083893", title="ООО Тест", with_storage=True):
    auth(client, owner.email)
    company = client.post(
        reverse("company-list"), {"inn": inn, "title": title}, format="json"
    ).data
    if with_storage:
        client.post(reverse("storage"), {"address": "СПб, ул. Тестовая, 1"}, format="json")
    return company


def attach_employee(client, owner, employee):
    auth(client, owner.email)
    client.post(
        reverse("company-attach-user-to-company"),
        {"user_id": employee.id},
        format="json",
    )


def make_product(client, *, title, purchase="100.00", sale="150.00"):
    return client.post(
        reverse("product-list"),
        {"title": title, "purchase_price": purchase, "sale_price": sale},
        format="json",
    ).data["id"]


def supply(client, supplier_id, items):
    return client.post(
        reverse("supplier-supplies", args=[supplier_id]), items, format="json"
    )


def setup_stock(api_client, owner):
    """Компания + поставщик + два товара с остатками 100 и 50."""
    make_company(api_client, owner)
    supplier_id = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО Поставщик", "inn": "444444444444"},
        format="json",
    ).data["id"]
    p1 = make_product(api_client, title="Монитор")
    p2 = make_product(api_client, title="Кейс")
    supply(api_client, supplier_id, [{"id": p1, "quantity": 100}, {"id": p2, "quantity": 50}])
    return p1, p2


# --------------------------------------------------------------------------- #
# Создание продажи                                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_sale_creation_decreases_quantity(api_client, owner):
    p1, p2 = setup_stock(api_client, owner)

    r = api_client.post(
        reverse("sale-list"),
        {
            "buyer_name": "John Doe",
            "product_sales": [
                {"product_id": p1, "quantity": 30},
                {"product_id": p2, "quantity": 8},
            ],
        },
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED
    assert Product.objects.get(pk=p1).quantity == 70
    assert Product.objects.get(pk=p2).quantity == 42

    sale = Sale.objects.get(pk=r.data["id"])
    assert sale.buyer_name == "John Doe"
    assert sale.company_id == owner.owned_company.id
    assert ProductSale.objects.filter(sale=sale).count() == 2


@pytest.mark.django_db
def test_sale_insufficient_stock_rejected(api_client, owner):
    p1, p2 = setup_stock(api_client, owner)

    r = api_client.post(
        reverse("sale-list"),
        {
            "buyer_name": "John Doe",
            "product_sales": [
                {"product_id": p1, "quantity": 150},
                {"product_id": p2, "quantity": 8},
            ],
        },
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.data["Монитор available only"] == 100
    assert "Кейс available only" not in r.data
    # ничего не создано и остатки не изменились
    assert not Sale.objects.exists()
    assert Product.objects.get(pk=p1).quantity == 100
    assert Product.objects.get(pk=p2).quantity == 50


@pytest.mark.django_db
def test_sale_lists_all_insufficient_products(api_client, owner):
    p1, p2 = setup_stock(api_client, owner)
    r = api_client.post(
        reverse("sale-list"),
        {
            "buyer_name": "John Doe",
            "product_sales": [
                {"product_id": p1, "quantity": 150},
                {"product_id": p2, "quantity": 80},
            ],
        },
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert r.data["Монитор available only"] == 100
    assert r.data["Кейс available only"] == 50


@pytest.mark.django_db
def test_sale_creation_allowed_for_employee(api_client, owner, employee):
    p1, _ = setup_stock(api_client, owner)
    attach_employee(api_client, owner, employee)

    auth(api_client, employee.email)
    r = api_client.post(
        reverse("sale-list"),
        {"buyer_name": "Buyer", "product_sales": [{"product_id": p1, "quantity": 5}]},
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED
    assert Product.objects.get(pk=p1).quantity == 95


@pytest.mark.django_db
def test_sale_rejects_foreign_product(api_client, owner, outsider):
    p1, _ = setup_stock(api_client, owner)

    make_company(api_client, outsider, inn="7707083894", title="ООО Б")
    foreign_pid = make_product(api_client, title="Чужой", purchase="1.00", sale="2.00")

    auth(api_client, owner.email)
    r = api_client.post(
        reverse("sale-list"),
        {"buyer_name": "X", "product_sales": [{"product_id": foreign_pid, "quantity": 1}]},
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert not Sale.objects.exists()


# --------------------------------------------------------------------------- #
# Список продаж                                                                #
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_sale_list_paginated_and_scoped(api_client, owner, outsider):
    p1, _ = setup_stock(api_client, owner)
    api_client.post(
        reverse("sale-list"),
        {"buyer_name": "A", "product_sales": [{"product_id": p1, "quantity": 1}]},
        format="json",
    )
    listed = api_client.get(reverse("sale-list"))
    assert listed.status_code == status.HTTP_200_OK
    assert set(listed.data.keys()) >= {"count", "results"}
    assert listed.data["count"] == 1
    assert listed.data["results"][0]["buyer_name"] == "A"

    # другая компания своих продаж не видит
    make_company(api_client, outsider, inn="7707083894", title="ООО Б")
    auth(api_client, outsider.email)
    other = api_client.get(reverse("sale-list"))
    assert other.data["count"] == 0


@pytest.mark.django_db
def test_sale_list_period_filter(api_client, owner):
    p1, _ = setup_stock(api_client, owner)
    s_old = Sale.objects.create(
        company_id=owner.owned_company.id, buyer_name="old", sale_date="2020-01-01"
    )
    ProductSale.objects.create(sale=s_old, product_id=p1, quantity=1)
    s_new = Sale.objects.create(
        company_id=owner.owned_company.id, buyer_name="new", sale_date="2024-06-01"
    )
    ProductSale.objects.create(sale=s_new, product_id=p1, quantity=1)

    filtered = api_client.get(
        reverse("sale-list"), {"date_from": "2024-01-01", "date_to": "2024-12-31"}
    )
    assert filtered.data["count"] == 1
    assert filtered.data["results"][0]["buyer_name"] == "new"


# --------------------------------------------------------------------------- #
# Редактирование продажи                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_sale_edit_buyer_and_date(api_client, owner):
    p1, _ = setup_stock(api_client, owner)
    sale_id = api_client.post(
        reverse("sale-list"),
        {"buyer_name": "Old", "product_sales": [{"product_id": p1, "quantity": 10}]},
        format="json",
    ).data["id"]

    r = api_client.patch(
        reverse("sale-detail", args=[sale_id]),
        {"buyer_name": "New", "sale_date": "2024-01-15"},
        format="json",
    )
    assert r.status_code == status.HTTP_200_OK
    sale = Sale.objects.get(pk=sale_id)
    assert sale.buyer_name == "New"
    assert str(sale.sale_date) == "2024-01-15"
    # остатки не тронуты
    assert Product.objects.get(pk=p1).quantity == 90


@pytest.mark.django_db
def test_sale_edit_future_date_rejected(api_client, owner):
    p1, _ = setup_stock(api_client, owner)
    sale_id = api_client.post(
        reverse("sale-list"),
        {"buyer_name": "B", "product_sales": [{"product_id": p1, "quantity": 1}]},
        format="json",
    ).data["id"]

    future = (timezone.localdate() + timezone.timedelta(days=5)).isoformat()
    r = api_client.patch(
        reverse("sale-detail", args=[sale_id]),
        {"sale_date": future},
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_sale_edit_cannot_change_quantities(api_client, owner):
    p1, _ = setup_stock(api_client, owner)
    sale_id = api_client.post(
        reverse("sale-list"),
        {"buyer_name": "B", "product_sales": [{"product_id": p1, "quantity": 10}]},
        format="json",
    ).data["id"]

    r = api_client.patch(
        reverse("sale-detail", args=[sale_id]),
        {"product_sales": [{"product_id": p1, "quantity": 99}]},
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert ProductSale.objects.get(sale_id=sale_id).quantity == 10
    assert Product.objects.get(pk=p1).quantity == 90


# --------------------------------------------------------------------------- #
# Удаление продажи                                                             #
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_sale_delete_restores_quantity(api_client, owner):
    p1, p2 = setup_stock(api_client, owner)
    sale_id = api_client.post(
        reverse("sale-list"),
        {
            "buyer_name": "B",
            "product_sales": [
                {"product_id": p1, "quantity": 30},
                {"product_id": p2, "quantity": 8},
            ],
        },
        format="json",
    ).data["id"]
    assert Product.objects.get(pk=p1).quantity == 70

    r = api_client.delete(reverse("sale-detail", args=[sale_id]))
    assert r.status_code == status.HTTP_204_NO_CONTENT
    assert not Sale.objects.filter(pk=sale_id).exists()
    assert not ProductSale.objects.filter(sale_id=sale_id).exists()
    assert Product.objects.get(pk=p1).quantity == 100
    assert Product.objects.get(pk=p2).quantity == 50


@pytest.mark.django_db
def test_sale_requires_company(api_client, owner):
    auth(api_client, owner.email)
    r = api_client.get(reverse("sale-list"))
    assert r.status_code == status.HTTP_404_NOT_FOUND
