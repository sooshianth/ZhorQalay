from django.db import models
from django.contrib.auth.models import AbstractUser
from django_jalali.db import models as jmodels
from django.contrib.auth.models import User
class UserPhoneNumber(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=11, unique=True)
    is_verified = models.BooleanField(default=True)
    created_at = jmodels.jDateTimeField(auto_now_add=True)
    updated_at = jmodels.jDateTimeField(auto_now=True)

    def __str__(self):
        return self.phone_number
    
    class Meta:
        verbose_name = 'شماره تلفن کاربر'
        verbose_name_plural = 'شماره تلفن کاربران'


