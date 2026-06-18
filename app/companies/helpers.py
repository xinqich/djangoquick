from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound

from .models import Company, Storage


def get_user_company(user):
    if user.company_id is None:
        raise NotFound(_("Пользователь не привязан к компании."))
    try:
        return Company.objects.get(pk=user.company_id)
    except Company.DoesNotExist as exc:
        raise NotFound(_("Компания пользователя не найдена.")) from exc


def get_user_company_storage(user):
    company = get_user_company(user)
    try:
        return Storage.objects.get(company=company)
    except Storage.DoesNotExist as exc:
        raise NotFound(_("У компании ещё нет склада.")) from exc
