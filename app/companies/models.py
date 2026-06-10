from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    inn = models.CharField(_("ИНН"), max_length=12, unique=True)
    title = models.CharField(_("Название"), max_length=255, unique=True)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Владелец"),
        on_delete=models.PROTECT,
        related_name="owned_company",
    )

    class Meta:
        verbose_name = _("Компания")
        verbose_name_plural = _("Компании")

    def __str__(self):
        return self.title


class Storage(models.Model):
    company = models.OneToOneField(
        Company,
        verbose_name=_("Компания"),
        on_delete=models.CASCADE,
        related_name="storage",
    )
    address = models.CharField(_("Адрес"), max_length=500)

    class Meta:
        verbose_name = _("Склад")
        verbose_name_plural = _("Склады")

    def __str__(self):
        return f"{self.company_id}: {self.address[:50]}"
