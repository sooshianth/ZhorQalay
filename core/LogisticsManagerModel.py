from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

class LogisticsManager(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='logistics_manager', null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True, verbose_name='نام')
    email = models.EmailField(max_length=50, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True, verbose_name='شماره تلفن')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

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