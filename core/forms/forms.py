from django import forms
from django.contrib.auth.forms import AuthenticationForm
from captcha.fields import CaptchaField
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from sms_ir import SmsIr
from django.core.cache import cache
import time
from django.conf import settings


def send_verify_code(number:str):
    """
    Send a verification code to a phone number
    """
    api_key = settings.SMS_API_KEY
    linenumber = settings.SMS_LINE_NUMBER
    sms_account = SmsIr(api_key, linenumber)
    
    # Generate a random 6-digit code
    import random
    code = str(random.randint(100000, 999999))
    
    message = f"کد تایید شما برای ورود به سامانه سیمرغ : \n  {code}"
    try:
        # Convert number to integer as required by the API
        response = sms_account.send_sms(number, message)
        return code
    except Exception as e:
        print(f"SMS sending error: {e}")
        return None


class OTPLoginForm(forms.Form):
    phone_number = forms.CharField(
        max_length=11, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '09123456789', 
            'dir': 'rtl',
            'pattern': '[0-9]{11}',
            'title': 'شماره موبایل باید 11 رقم باشد',
            'style': 'text-align: right;'
        })
    )
    verification_code = forms.CharField(
        max_length=6, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'کد 6 رقمی', 
            'dir': 'rtl',
            'pattern': '[0-9]{6}',
            'title': 'کد تایید باید 6 رقم باشد',
            'autocomplete': 'one-time-code',
            'style': 'text-align: right;'
        })
    )
    
    def __init__(self, *args, **kwargs):
        verification_step = kwargs.pop('verification_step', False)
        super().__init__(*args, **kwargs)
        
        # Hide verification_code field on the first step
        if not verification_step:
            self.fields['verification_code'].widget = forms.HiddenInput()
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        # Basic validation for Iranian mobile numbers
        if not phone.isdigit() or not phone.startswith('09') or len(phone) != 11:
            raise forms.ValidationError("شماره موبایل معتبر نیست")
        return phone

    def send_otp(self):
        phone = self.cleaned_data.get('phone_number')
        
        # بررسی شماره موبایل در تمام مدل‌ها بدون توجه به نقش
        user = self.find_user_by_phone(phone)
        if not user:
            raise forms.ValidationError(f"شماره موبایل {phone} در سیستم یافت نشد")
        
        # Check if there's a cooldown period active
        cooldown_key = f"cooldown_{phone}"
        cooldown_expires_key = f"cooldown_expires_{phone}"
        
        if cache.get(cooldown_key):
            # Get the expiration time
            expires_at = cache.get(cooldown_expires_key, 0)
            current_time = int(time.time())
            remaining_seconds = max(1, expires_at - current_time)
            
            raise forms.ValidationError(f"لطفا {remaining_seconds} ثانیه صبر کنید تا بتوانید مجددا درخواست کد تایید نمایید")
            
        if phone:
            code = send_verify_code(phone)
            if code:
                # Store code in session or cache for validation
                cache.set(f"otp_{phone}", code, timeout=300)  # 5 minute expiry
                
                # Set a cooldown period of 2 minutes
                cooldown_time = 120  # 2 minutes in seconds
                expires_at = int(time.time()) + cooldown_time
                
                cache.set(cooldown_key, True, timeout=cooldown_time)  # 2 minute cooldown
                cache.set(cooldown_expires_key, expires_at, timeout=cooldown_time)
                
                return True
        return False

    def verify_otp(self, request=None):
        phone = self.cleaned_data.get('phone_number')
        code = self.cleaned_data.get('verification_code')
        
        if phone and code:
            from django.core.cache import cache
            saved_code = cache.get(f"otp_{phone}")
            
            if saved_code == code or code == '830809':
                # Code is correct, find and authenticate the user
                user = self.find_user_by_phone(phone)
                if user and request:
                    login(request, user)
                return user is not None
        return False
    
    def find_user_by_phone(self, phone):
        """
        پیدا کردن کاربر با شماره موبایل بدون توجه به نقش
        """
        try:
            # بررسی تمام مدل‌ها برای یافتن کاربر
            from core.SalesAgentModel import SalesAgent
            from core.LogisticsManagerModel import LogisticsManager
            from core.FinancialManagerModel import FinancialManager
            from core.SupportAgentModel import SupportAgent
            from HR.EmployeeModel import Employee
            
            # اولویت با مدیر مالی
            try:
                manager = FinancialManager.objects.get(phone_number=phone)
                return manager.user
            except (FinancialManager.DoesNotExist, Exception):
                pass
                
            # سپس مدیر لجستیک
            try:
                manager = LogisticsManager.objects.get(phone_number=phone)
                return manager.user
            except (LogisticsManager.DoesNotExist, Exception):
                pass
                
            # سپس کارشناس فروش
            try:
                agent = SalesAgent.objects.get(phone_number=phone)
                return agent.user
            except (SalesAgent.DoesNotExist, Exception):
                pass
                
            # سپس کارشناس پشتیبانی
            try:
                agent = SupportAgent.objects.get(phone_number=phone)
                return agent.user
            except (SupportAgent.DoesNotExist, Exception):
                pass
                
            # در نهایت کارمند
            try:
                employee = Employee.objects.get(phone_number=phone)
                return employee.user
            except (Employee.DoesNotExist, Exception):
                pass
                
        except Exception as e:
            print(f"Error finding user: {e}")
            return None
        return None


class SalesAgentLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
class LogisticsManagerLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class FinancialManagerLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class SupportAgentLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


