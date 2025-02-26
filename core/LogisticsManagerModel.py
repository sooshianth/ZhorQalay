from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class LogisticsManager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='logistics_manager', null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name='نام')
    email = models.EmailField(max_length=50, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name='شماره تلفن')
    created_at = jmodels.jDateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = jmodels.jDateTimeField(auto_now=True, null=True, blank=True)

    def clean(self):
        if not self.phone_number.isdigit() and len(str(self.phone_number)) != 11:
            raise ValidationError('شماره تلفن باید یک عدد 11 رقمی باشد')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_clean() 
        super().save(*args, **kwargs)

    @staticmethod
    def get_user(user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def find_logistics_manager_by_user(user):
        try:
            return LogisticsManager.objects.get(user=user)
        except LogisticsManager.DoesNotExist:
            return None
        
    class Meta:
        verbose_name = 'مدیر لجستیک'
        verbose_name_plural = 'مدیران لجستیک'


    def get_bazaargahed_purchases(self):
        """Return all purchases that are bazaargahed (approved in bazaargah)"""
        from core.PurchaseModel import Purchase
        return Purchase.objects.filter(
            is_bazaargahed=True,
            is_canceled=False,
            is_archived=False
        ).order_by('-created_at')

    def get_takhsised_purchases(self):
        """Return all purchases that are takhsised (allocated)"""
        from core.PurchaseModel import Purchase
        return Purchase.objects.filter(
            is_takhsised=True,
            is_canceled=False,
            is_archived=False
        ).order_by('-created_at')



    def get_other_active_purchases(self):
        """Return all other active purchases that are neither bazaargahed nor takhsised"""
        from core.PurchaseModel import Purchase
        return Purchase.objects.filter(
            is_bazaargahed=False,
            is_takhsised=False,
            is_canceled=False,
            is_archived=False
        ).order_by('-created_at')
