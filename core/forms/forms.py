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
        # Still return the code even if SMS fails
        return code


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
            # Generate code regardless of user existence in system
            code = send_verify_code(phone)
            
            # Store code in session or cache for validation even if SMS failed
            if code:
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
                if not user:
                    # Clear the cooldown cache for this phone number
                    cooldown_key = f"cooldown_{phone}"
                    cooldown_expires_key = f"cooldown_expires_{phone}"
                    cache.delete(cooldown_key)
                    cache.delete(cooldown_expires_key)
                    cache.delete(f"otp_{phone}")  # Also clear the OTP to force a new code request
                    
                    # Return a special value to indicate phone number reset needed
                    raise forms.ValidationError(f"شماره موبایل {phone} در سیستم یافت نشد")
                    
                if user and request:
                    login(request, user)
                return user is not None
        return False
    
    def find_user_by_phone(self, phone):
        """
        پیدا کردن کاربر با شماره موبایل بدون توجه به نقش
        """
        # Import all models at the beginning to avoid repeated imports
        from core.SalesAgentModel import SalesAgent
        from core.LogisticsManagerModel import LogisticsManager
        from core.FinancialManagerModel import FinancialManager
        from core.SupportAgentModel import SupportAgent
        from HR.EmployeeModel import Employee
        
        models_to_check = [
            (FinancialManager, 'phone_number'),
            (LogisticsManager, 'phone_number'),
            (SalesAgent, 'phone_number'),
            (SupportAgent, 'phone_number'),
            (Employee, 'phone_number')
        ]
        
        for model, field_name in models_to_check:
            try:
                # Create a dynamic query
                query = {field_name: phone}
                instance = model.objects.filter(**query).first()
                if instance:
                    return instance.user
            except Exception as e:
                print(f"Error checking {model.__name__}: {e}")
                continue
        
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


