from django.contrib.auth import get_user_model
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Company


@receiver(pre_delete, sender=Company)
def clear_users_company_on_company_delete(sender, instance, **kwargs):
    User = get_user_model()
    User.objects.filter(company=instance).update(company=None, is_company_owner=False)
