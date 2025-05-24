from django.db import models

class Barbary(models.Model):
    name = models.CharField(max_length=50, verbose_name='نام', blank=True, null=True)
    phone_number = models.CharField(max_length=11, verbose_name='شماره تماس', blank=True, null=True)
    email = models.EmailField(max_length=50, verbose_name='ایمیل', blank=True, null=True)
    
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'باربری'
        verbose_name_plural = 'باربری ها'
