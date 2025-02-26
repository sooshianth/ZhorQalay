from django.db import models
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class FinancialManager(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, related_name='financial_manager', null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=50, null=True, blank=True)
    phone_number = models.CharField(max_length=12, null=True, blank=True)
    created_at = jmodels.jDateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = jmodels.jDateTimeField(auto_now=True, null=True, blank=True)

    def clean(self):
        if not self.phone_number.isdigit() and len(str(self.phone_number)) != 11:
            raise ValidationError('شماره تلفن باید یک عدد 11 رقمی باشد')
        if not self.name:
            raise ValidationError('وارد کردن نام الزامی است')

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
    def find_manager_by_user(user):
        try:
            return FinancialManager.objects.get(user=user)
        except FinancialManager.DoesNotExist:
            return None
        
    class Meta:
        verbose_name = 'مدیر مالی'
        verbose_name_plural = 'مدیران مالی'