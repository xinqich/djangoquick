import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from authenticate.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(email="a@example.com", password="secretpass12")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(email="b@example.com", password="secretpass12")


def auth(client: APIClient, email: str, password: str) -> None:
    url = reverse("auth-login")
    resp = client.post(url, {"email": email, "password": password}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    access = resp.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")


@pytest.mark.django_db
def test_about_me(api_client, user_a):
    url = reverse("auth-about-me")
    assert api_client.get(url).status_code == status.HTTP_401_UNAUTHORIZED

    auth(api_client, user_a.email, "secretpass12")
    r = api_client.get(url)
    assert r.status_code == status.HTTP_200_OK
    assert r.data["email"] == user_a.email
    assert r.data["company"] is None

    api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Я"},
        format="json",
    )
    r2 = api_client.get(url)
    assert r2.status_code == status.HTTP_200_OK
    assert r2.data["email"] == user_a.email
    assert r2.data["company"] is not None
    assert r2.data["company"]["title"] == "ООО Я"
    assert r2.data["company"]["inn"] == "7707083893"


@pytest.mark.django_db
def test_register_login_refresh(api_client):
    reg_url = reverse("auth-register")
    r = api_client.post(
        reg_url,
        {
            "email": "new@example.com",
            "password": "longpassword1",
            "password_confirm": "longpassword1",
        },
        format="json",
    )
    assert r.status_code == status.HTTP_201_CREATED
    assert User.objects.filter(email="new@example.com").exists()

    auth(api_client, "new@example.com", "longpassword1")
    refresh_url = reverse("auth-token-refresh")
    login = api_client.post(
        reverse("auth-login"),
        {"email": "new@example.com", "password": "longpassword1"},
        format="json",
    )
    refresh = login.data["refresh"]
    out = api_client.post(refresh_url, {"refresh": refresh}, format="json")
    assert out.status_code == status.HTTP_200_OK
    assert "access" in out.data


@pytest.mark.django_db
def test_company_create_and_second_forbidden(api_client, user_a):
    auth(api_client, user_a.email, "secretpass12")
    url = reverse("company-list")
    r = api_client.post(
        url, {"inn": "7707083893", "title": "ООО Тест"}, format="json"
    )
    assert r.status_code == status.HTTP_201_CREATED
    user_a.refresh_from_db()
    assert user_a.is_company_owner is True
    assert user_a.company_id is not None

    r2 = api_client.post(
        url, {"inn": "7707083894", "title": "ООО Другая"}, format="json"
    )
    assert r2.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_company_owner_crud_and_any_auth_retrieve(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    create = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Альфа"},
        format="json",
    )
    company_id = create.data["id"]

    auth(api_client, user_b.email, "secretpass12")
    get_other = api_client.get(reverse("company-detail", args=[company_id]))
    assert get_other.status_code == status.HTTP_200_OK

    user_b.company_id = company_id
    user_b.save(update_fields=["company_id"])
    patch_other = api_client.patch(
        reverse("company-me"),
        {"title": "Взлом"},
        format="json",
    )
    assert patch_other.status_code == status.HTTP_403_FORBIDDEN

    auth(api_client, user_a.email, "secretpass12")
    patch_ok = api_client.patch(
        reverse("company-me"),
        {"title": "ООО Альфа Плюс"},
        format="json",
    )
    assert patch_ok.status_code == status.HTTP_200_OK
    assert patch_ok.data["title"] == "ООО Альфа Плюс"


@pytest.mark.django_db
def test_storage_owner_only_and_member_retrieve(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Склад"},
        format="json",
    ).data
    addr = "Санкт-Петербург, Смольная ул., 18, пом. 5"
    st = api_client.post(
        reverse("storage"), {"address": addr}, format="json"
    )
    assert st.status_code == status.HTTP_201_CREATED

    auth(api_client, user_b.email, "secretpass12")
    create_st = api_client.post(
        reverse("storage"), {"address": "Другой"}, format="json"
    )
    assert create_st.status_code == status.HTTP_403_FORBIDDEN

    user_b.company_id = company["id"]
    user_b.save(update_fields=["company_id"])
    get_st = api_client.get(reverse("storage"))
    assert get_st.status_code == status.HTTP_200_OK
    assert get_st.data["address"] == addr

    patch_st = api_client.patch(
        reverse("storage"),
        {"address": "Новый адрес"},
        format="json",
    )
    assert patch_st.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_one_storage_per_company(api_client, user_a):
    auth(api_client, user_a.email, "secretpass12")
    api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Дубль склад"},
        format="json",
    )
    first = api_client.post(
        reverse("storage"),
        {"address": "Адрес 1"},
        format="json",
    )
    assert first.status_code == status.HTTP_201_CREATED
    second = api_client.post(
        reverse("storage"),
        {"address": "Адрес 2"},
        format="json",
    )
    assert second.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_storage_not_found_without_company_or_storage(api_client, user_a):
    auth(api_client, user_a.email, "secretpass12")
    assert api_client.get(reverse("storage")).status_code == status.HTTP_404_NOT_FOUND

    api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Без склада"},
        format="json",
    )
    assert api_client.get(reverse("storage")).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_company_me_not_found_without_company(api_client, user_a):
    auth(api_client, user_a.email, "secretpass12")
    assert (
        api_client.patch(reverse("company-me"), {"title": "X"}, format="json").status_code
        == status.HTTP_404_NOT_FOUND
    )


@pytest.fixture
def user_c(db):
    return User.objects.create_user(email="c@example.com", password="secretpass12")


@pytest.mark.django_db
def test_owner_links_employee_by_id(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Кадры"},
        format="json",
    ).data["id"]
    url = reverse("company-attach-user-to-company")

    r = api_client.post(url, {"user_id": user_b.id}, format="json")
    assert r.status_code == status.HTTP_201_CREATED
    assert r.data["email"] == user_b.email
    assert r.data["company"] == company_id
    user_b.refresh_from_db()
    assert user_b.company_id == company_id
    assert user_b.is_company_owner is False


@pytest.mark.django_db
def test_owner_links_employee_by_email(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Почта"},
        format="json",
    ).data["id"]
    url = reverse("company-attach-user-to-company")
    r = api_client.post(url, {"email": user_b.email}, format="json")
    assert r.status_code == status.HTTP_201_CREATED
    user_b.refresh_from_db()
    assert user_b.company_id == company_id


@pytest.mark.django_db
def test_link_employee_forbidden_for_non_owner(api_client, user_a, user_b, user_c):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Охрана"},
        format="json",
    ).data["id"]
    url = reverse("company-attach-user-to-company")

    user_b.company_id = company_id
    user_b.save(update_fields=["company_id"])
    auth(api_client, user_b.email, "secretpass12")
    r = api_client.post(url, {"user_id": user_c.id}, format="json")
    assert r.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_link_employee_rejects_already_linked(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Полный"},
        format="json",
    ).data["id"]
    url = reverse("company-attach-user-to-company")
    assert api_client.post(url, {"user_id": user_b.id}, format="json").status_code == 201
    r2 = api_client.post(url, {"email": user_b.email}, format="json")
    assert r2.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_link_employee_rejects_company_owner_target(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_a = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО А"},
        format="json",
    ).data["id"]

    auth(api_client, user_b.email, "secretpass12")
    api_client.post(
        reverse("company-list"),
        {"inn": "7707083894", "title": "ООО Б"},
        format="json",
    )

    auth(api_client, user_a.email, "secretpass12")
    url = reverse("company-attach-user-to-company")
    r = api_client.post(url, {"user_id": user_b.id}, format="json")
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_list_employees_excludes_owner(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Список"},
        format="json",
    ).data["id"]
    base = reverse("company-attach-user-to-company")
    assert api_client.get(base).data == []

    api_client.post(base, {"user_id": user_b.id}, format="json")
    listed = api_client.get(base)
    assert listed.status_code == status.HTTP_200_OK
    assert len(listed.data) == 1
    assert listed.data[0]["id"] == user_b.id
    assert listed.data[0]["email"] == user_b.email


@pytest.mark.django_db
def test_list_employees_forbidden_for_non_owner(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Список2"},
        format="json",
    ).data["id"]
    base = reverse("company-attach-user-to-company")

    user_b.company_id = company_id
    user_b.save(update_fields=["company_id"])
    auth(api_client, user_b.email, "secretpass12")
    assert api_client.get(base).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_remove_employee_success(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Увольнение"},
        format="json",
    ).data["id"]
    base = reverse("company-attach-user-to-company")
    api_client.post(base, {"user_id": user_b.id}, format="json")

    del_url = reverse(
        "company-detach-user-from-company",
        kwargs={"employee_pk": user_b.id},
    )
    r = api_client.delete(del_url)
    assert r.status_code == status.HTTP_204_NO_CONTENT
    user_b.refresh_from_db()
    assert user_b.company_id is None
    assert api_client.get(base).data == []


@pytest.mark.django_db
def test_remove_owner_forbidden(api_client, user_a):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Владелец"},
        format="json",
    ).data["id"]
    user_a.refresh_from_db()
    del_url = reverse(
        "company-detach-user-from-company",
        kwargs={"employee_pk": user_a.id},
    )
    assert api_client.delete(del_url).status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_remove_employee_not_found(api_client, user_a, user_b, user_c):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО 404"},
        format="json",
    ).data["id"]
    api_client.post(
        reverse("company-attach-user-to-company"),
        {"user_id": user_b.id},
        format="json",
    )
    del_url = reverse(
        "company-detach-user-from-company",
        kwargs={"employee_pk": user_c.id},
    )
    assert api_client.delete(del_url).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_remove_employee_forbidden_non_owner(api_client, user_a, user_b, user_c):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Чужой"},
        format="json",
    ).data["id"]
    api_client.post(
        reverse("company-attach-user-to-company"),
        {"user_id": user_b.id},
        format="json",
    )
    del_url = reverse(
        "company-detach-user-from-company",
        kwargs={"employee_pk": user_b.id},
    )
    auth(api_client, user_b.email, "secretpass12")
    assert api_client.delete(del_url).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_link_employee_id_and_email_validation(api_client, user_a, user_b):
    auth(api_client, user_a.email, "secretpass12")
    company_id = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Валидация"},
        format="json",
    ).data["id"]
    url = reverse("company-attach-user-to-company")

    r = api_client.post(
        url, {"user_id": user_b.id, "email": user_b.email}, format="json"
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    r2 = api_client.post(url, {}, format="json")
    assert r2.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_company_delete_clears_user_company(api_client, user_a):
    auth(api_client, user_a.email, "secretpass12")
    cid = api_client.post(
        reverse("company-list"),
        {"inn": "7707083893", "title": "ООО Удаление"},
        format="json",
    ).data["id"]
    user_a.refresh_from_db()
    assert user_a.company_id == cid
    del_resp = api_client.delete(reverse("company-me"))
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT
    user_a.refresh_from_db()
    assert user_a.company_id is None
    assert user_a.is_company_owner is False
