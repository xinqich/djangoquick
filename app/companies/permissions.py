from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from rest_framework.exceptions import NotFound

from .models import Company


class HasUserCompany(permissions.BasePermission):
    """Пользователь привязан к компании."""

    message = _("Пользователь не привязан к компании.")

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.company_id is None:
            raise NotFound(_("Пользователь не привязан к компании."))
        return True


class IsOwner(permissions.BasePermission):
    """Владелец компании, к которой привязан пользователь."""

    message = _("Действие доступно только владельцу компании.")

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.company_id is None:
            return False
        if not getattr(user, "is_company_owner", False):
            return False
        return Company.objects.filter(pk=user.company_id, owner_id=user.id).exists()
