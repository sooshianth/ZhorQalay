from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels

class SupportAgent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='support_agent')
    name = models.CharField(max_length=50, verbose_name='نام', blank=True, null=True)
    email = models.EmailField(max_length=50, verbose_name='ایمیل', blank=True, null=True)
    phone_number = models.CharField(max_length=11, verbose_name='شماره تماس', blank=True, null=True)
    message = models.TextField(verbose_name='پیام', blank=True, null=True)
    created_at = jmodels.jDateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')
    updated_at = jmodels.jDateTimeField(auto_now=True, verbose_name='تاریخ ویرایش')
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if not self.name:
            raise ValidationError('نام الزامی است')
        if not self.phone_number:
            raise ValidationError('شماره تماس الزامی است')

    @staticmethod
    def get_user(user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def find_support_agent_by_user(user):
        try:
            return SupportAgentModel.objects.get(user=user)
        except SupportAgentModel.DoesNotExist:
            return None

    class Meta:
        verbose_name = 'کارشناس پشتیبانی'
        verbose_name_plural = 'کارشناسان پشتیبانی'

    def get_all_support_agents(self):
        return SupportAgentModel.objects.all()

    def get_support_agent_by_id(self, id):
        return SupportAgentModel.objects.get(id=id)

    def get_support_agent_by_user(self, user):
        return SupportAgentModel.objects.get(user=user)


        

        

        

        

        
        
        
        
        
        
        









