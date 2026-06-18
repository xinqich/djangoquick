import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from authenticate.models import User
from inventory.models import Product, Supplier, Supply, SupplyProduct


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


# --------------------------------------------------------------------------- #
# Поставщики                                                                   #
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_supplier_crud_and_company_scoped(api_client, owner):
    make_company(api_client, owner)

    created = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО Поставка", "inn": "111111111111"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    sup_id = created.data["id"]
    owner.refresh_from_db()
    assert Supplier.objects.get(pk=sup_id).company_id == owner.company_id

    listed = api_client.get(reverse("supplier-list"))
    assert listed.status_code == status.HTTP_200_OK
    assert len(listed.data) == 1

    patched = api_client.patch(
        reverse("supplier-detail", args=[sup_id]),
        {"title": "ООО Поставка Плюс"},
        format="json",
    )
    assert patched.status_code == status.HTTP_200_OK
    assert patched.data["title"] == "ООО Поставка Плюс"

    deleted = api_client.delete(reverse("supplier-detail", args=[sup_id]))
    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert not Supplier.objects.filter(pk=sup_id).exists()


@pytest.mark.django_db
def test_supplier_title_and_inn_unique(api_client, owner, outsider):
    make_company(api_client, owner)
    assert (
        api_client.post(
            reverse("supplier-list"),
            {"title": "ООО Уникальный", "inn": "555555555555"},
            format="json",
        ).status_code
        == status.HTTP_201_CREATED
    )

    # тот же ИНН — отклоняется
    dup_inn = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО Другое имя", "inn": "555555555555"},
        format="json",
    )
    assert dup_inn.status_code == status.HTTP_400_BAD_REQUEST

    # то же название — отклоняется (в т.ч. для другой компании)
    make_company(api_client, outsider, inn="7707083894", title="ООО Б")
    auth(api_client, outsider.email)
    dup_title = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО Уникальный", "inn": "666666666666"},
        format="json",
    )
    assert dup_title.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_supplier_available_to_employee(api_client, owner, employee):
    make_company(api_client, owner)
    attach_employee(api_client, owner, employee)

    auth(api_client, employee.email)
    created = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО Сотруднический", "inn": "222222222222"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED
    assert api_client.get(reverse("supplier-list")).status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_supplier_not_visible_across_companies(api_client, owner, outsider):
    make_company(api_client, owner)
    sup_id = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО А", "inn": "333333333333"},
        format="json",
    ).data["id"]

    make_company(api_client, outsider, inn="7707083894", title="ООО Б")
    auth(api_client, outsider.email)
    assert api_client.get(reverse("supplier-list")).data == []
    assert (
        api_client.get(reverse("supplier-detail", args=[sup_id])).status_code
        == status.HTTP_404_NOT_FOUND
    )


@pytest.mark.django_db
def test_supplier_requires_company(api_client, owner):
    auth(api_client, owner.email)
    assert (
        api_client.get(reverse("supplier-list")).status_code
        == status.HTTP_404_NOT_FOUND
    )


# --------------------------------------------------------------------------- #
# Товары                                                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
def test_product_create_defaults_quantity_zero(api_client, owner):
    make_company(api_client, owner)
    r = api_client.post(
        reverse("product-list"),
        {"title": "Монитор", "purchase_price": "1200.00", "sale_price": "1500.00", "quantity": 99},
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED
    assert r.data["quantity"] == 0  # количество игнорируется при создании
    assert Product.objects.get(pk=r.data["id"]).quantity == 0


@pytest.mark.django_db
def test_product_quantity_not_editable(api_client, owner):
    make_company(api_client, owner)
    pid = api_client.post(
        reverse("product-list"),
        {"title": "Кейс", "purchase_price": "10.00", "sale_price": "20.00"},
        format="json",
    ).data["id"]
    Product.objects.filter(pk=pid).update(quantity=5)

    # попытка изменить количество через PATCH — явная ошибка 400
    patched = api_client.patch(
        reverse("product-detail", args=[pid]),
        {"quantity": 999, "title": "Кейс v2"},
        format="json",
    )
    assert patched.status_code == status.HTTP_400_BAD_REQUEST
    p = Product.objects.get(pk=pid)
    assert p.quantity == 5  # не изменилось
    assert p.title == "Кейс"  # запрос отклонён целиком

    # PUT тоже отклоняется при попытке изменить количество
    put = api_client.put(
        reverse("product-detail", args=[pid]),
        {
            "title": "Кейс v3",
            "purchase_price": "10.00",
            "sale_price": "20.00",
            "quantity": 7,
        },
        format="json",
    )
    assert put.status_code == status.HTTP_400_BAD_REQUEST

    # обновление без изменения количества проходит (даже если прислать то же значение)
    ok = api_client.patch(
        reverse("product-detail", args=[pid]),
        {"title": "Кейс v4", "quantity": 5},
        format="json",
    )
    assert ok.status_code == status.HTTP_200_OK
    assert Product.objects.get(pk=pid).title == "Кейс v4"


@pytest.mark.django_db
def test_product_list_shape(api_client, owner):
    make_company(api_client, owner)
    api_client.post(
        reverse("product-list"),
        {"title": "Товар 1", "purchase_price": "1200.00", "sale_price": "1500.00"},
        format="json",
    )
    listed = api_client.get(reverse("product-list"))
    assert listed.status_code == status.HTTP_200_OK
    assert set(listed.data[0].keys()) == {
        "id",
        "title",
        "quantity",
        "purchase_price",
        "sale_price",
    }


@pytest.mark.django_db
def test_product_company_scoped(api_client, owner, outsider):
    make_company(api_client, owner)
    pid = api_client.post(
        reverse("product-list"),
        {"title": "Чужой", "purchase_price": "1.00", "sale_price": "2.00"},
        format="json",
    ).data["id"]

    make_company(api_client, outsider, inn="7707083894", title="ООО Б")
    auth(api_client, outsider.email)
    assert api_client.get(reverse("product-list")).data == []
    assert (
        api_client.get(reverse("product-detail", args=[pid])).status_code
        == status.HTTP_404_NOT_FOUND
    )


# --------------------------------------------------------------------------- #
# Поставки                                                                     #
# --------------------------------------------------------------------------- #
def _setup_supplier_and_products(api_client, owner):
    make_company(api_client, owner)
    supplier_id = api_client.post(
        reverse("supplier-list"),
        {"title": "ООО Поставщик", "inn": "444444444444"},
        format="json",
    ).data["id"]
    p1 = api_client.post(
        reverse("product-list"),
        {"title": "Монитор", "purchase_price": "100.00", "sale_price": "150.00"},
        format="json",
    ).data["id"]
    p2 = api_client.post(
        reverse("product-list"),
        {"title": "Кейс", "purchase_price": "5.00", "sale_price": "9.00"},
        format="json",
    ).data["id"]
    return supplier_id, p1, p2


@pytest.mark.django_db
def test_supply_creation_increases_quantity(api_client, owner):
    supplier_id, p1, p2 = _setup_supplier_and_products(api_client, owner)

    r = api_client.post(
        reverse("supplier-supplies", args=[supplier_id]),
        [{"id": p1, "quantity": 10}, {"id": p2, "quantity": 50}],
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED
    assert Product.objects.get(pk=p1).quantity == 10
    assert Product.objects.get(pk=p2).quantity == 50

    supply = Supply.objects.get(pk=r.data["id"])
    assert supply.supplier_id == supplier_id
    assert SupplyProduct.objects.filter(supply=supply).count() == 2

    # повторная поставка добавляет к остатку
    api_client.post(
        reverse("supplier-supplies", args=[supplier_id]),
        [{"id": p1, "quantity": 3}],
        format="json",
    )
    assert Product.objects.get(pk=p1).quantity == 13


@pytest.mark.django_db
def test_supply_rejects_negative_quantity(api_client, owner):
    supplier_id, p1, _ = _setup_supplier_and_products(api_client, owner)
    r = api_client.post(
        reverse("supplier-supplies", args=[supplier_id]),
        [{"id": p1, "quantity": -5}],
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert Product.objects.get(pk=p1).quantity == 0
    assert not Supply.objects.exists()


@pytest.mark.django_db
def test_supply_rejects_foreign_product(api_client, owner, outsider):
    supplier_id, p1, _ = _setup_supplier_and_products(api_client, owner)

    make_company(api_client, outsider, inn="7707083894", title="ООО Б")
    foreign_pid = api_client.post(
        reverse("product-list"),
        {"title": "Чужой", "purchase_price": "1.00", "sale_price": "2.00"},
        format="json",
    ).data["id"]

    auth(api_client, owner.email)
    r = api_client.post(
        reverse("supplier-supplies", args=[supplier_id]),
        [{"id": foreign_pid, "quantity": 5}],
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    assert not Supply.objects.exists()


@pytest.mark.django_db
def test_supply_list(api_client, owner):
    supplier_id, p1, p2 = _setup_supplier_and_products(api_client, owner)
    api_client.post(
        reverse("supplier-supplies", args=[supplier_id]),
        [{"id": p1, "quantity": 10}, {"id": p2, "quantity": 5}],
        format="json",
    )
    listed = api_client.get(reverse("supply-list"))
    assert listed.status_code == status.HTTP_200_OK
    assert len(listed.data) == 1
    assert listed.data[0]["supplier"] == supplier_id
    assert len(listed.data[0]["items"]) == 2


@pytest.mark.django_db
def test_supply_creation_allowed_for_employee(api_client, owner, employee):
    supplier_id, p1, _ = _setup_supplier_and_products(api_client, owner)
    attach_employee(api_client, owner, employee)

    auth(api_client, employee.email)
    r = api_client.post(
        reverse("supplier-supplies", args=[supplier_id]),
        [{"id": p1, "quantity": 7}],
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED
    assert Product.objects.get(pk=p1).quantity == 7
