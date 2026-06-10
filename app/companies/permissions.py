from rest_framework import permissions


class IsCompanyOwnerUser(permissions.BasePermission):
    """Пользователь — владелец какой-либо компании (флаг is_company_owner)."""

    message = "Действие доступно только владельцу компании."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated and getattr(user, "is_company_owner", False)
        )


class IsCompanyOwner(permissions.BasePermission):
    """Доступ только владельцу указанной компании."""

    message = "Действие доступно только владельцу компании."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        return bool(
            getattr(user, "is_company_owner", False) and getattr(obj, "owner_id", None) == user.id
        )


class IsLinkedToStorageCompany(permissions.BasePermission):
    """Просмотр склада: пользователь привязан к той же компании."""

    message = "Просмотр склада доступен только сотрудникам этой компании."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        return user.company_id is not None and user.company_id == obj.company_id


class IsCompanyOwnerForStorage(permissions.BasePermission):
    """Изменение склада: пользователь — владелец компании склада."""

    message = "Изменение склада доступно только владельцу компании."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user.is_authenticated:
            return False
        company = obj.company
        return bool(
            getattr(user, "is_company_owner", False)
            and company.owner_id == user.id
        )
