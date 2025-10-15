from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels

class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="employee")
    phone_number = models.CharField(max_length=11, verbose_name="شماره تلفن")
    first_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="نام")
    last_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="نام خانوادگی")
    email = models.EmailField(max_length=254, null=True, blank=True, verbose_name="ایمیل")
    address = models.TextField(null=True, blank=True, verbose_name="آدرس")
    birth_date = jmodels.jDateField(null=True, blank=True, verbose_name="تاریخ تولد")
    hire_date = jmodels.jDateField(null=True, blank=True, verbose_name="تاریخ استخدام")
    job_title = models.CharField(max_length=100, null=True, blank=True, verbose_name="عنوان شغلی")
    is_manager = models.BooleanField(default=False, verbose_name="مدیر است")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    class Meta:
        verbose_name = "کارمند"
        verbose_name_plural = "کارمندان"
        ordering = ['-hire_date']

    
