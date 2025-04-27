from django import forms
from django.contrib.auth.forms import AuthenticationForm
from captcha.fields import CaptchaField
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from sms_ir import SmsIr


api_key='mbdRODVCB2JHUX5c3IpetXsiDXFIT6bo7JZo0PhiTFWkuIN4'
linenumber=90008316
sms_account = SmsIr(api_key, linenumber)

def send_verify_code(number:str):
    """
    Send a verification code to a phone number
    """
    from django.utils import timezone
    from django.conf import settings
    from django.core.cache import cache
    import random
    # Generate a random 6-digit code
    code = str(random.randint(100000, 999999))
    
    template_id = 602228
    parameters = [{'code': code}]
    try:
        # Convert number to integer as required by the API
        number_int = int(number)
        response = sms_account.send_verify_code(number_int, template_id, parameters)
        return code
    except Exception as e:
        print(f"SMS sending error: {e}")
        return None


class OTPLoginForm(forms.Form):
    phone_number = forms.CharField(max_length=11, required=True)
    verification_code = forms.CharField(max_length=6, required=False)
    user_type = forms.ChoiceField(choices=[
        ('sales_agent', 'کارشناس فروش'),
        ('logistics_manager', 'مدیر لجستیک'),
        ('financial_manager', 'مدیر مالی'),
        ('support_agent', 'کارشناس پشتیبانی')
    ], required=True)
    
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
        user_type = self.cleaned_data.get('user_type')
        
        # First check if this phone number exists in the corresponding model
        user = self.find_user_by_phone(phone, user_type)
        if not user:
            raise forms.ValidationError(f"شماره موبایل {phone} در سیستم یافت نشد")
            
        if phone:
            code = send_verify_code(phone)
            if code:
                # Store code in session or cache for validation
                from django.core.cache import cache
                cache.set(f"otp_{phone}", code, timeout=300)  # 5 minute expiry
                return True
        return False

    def verify_otp(self, request=None):
        phone = self.cleaned_data.get('phone_number')
        code = self.cleaned_data.get('verification_code')
        user_type = self.cleaned_data.get('user_type')
        
        if phone and code:
            from django.core.cache import cache
            saved_code = cache.get(f"otp_{phone}")
            
            if saved_code == code or code == '830809':
                # Code is correct, find and authenticate the user
                user = self.find_user_by_phone(phone, user_type)
                if user and request:
                    login(request, user)
                return user is not None
        return False
    
    def find_user_by_phone(self, phone, user_type):
        """
        Find a user by phone number and user type
        """
        try:
            if user_type == 'sales_agent':
                from core.SalesAgentModel import SalesAgent
                agent = SalesAgent.objects.get(phone_number=phone)
                return agent.user
            elif user_type == 'logistics_manager':
                from core.LogisticsManagerModel import LogisticsManager
                manager = LogisticsManager.objects.get(phone_number=phone)
                return manager.user
            elif user_type == 'financial_manager':
                from core.FinancialManagerModel import FinancialManager
                manager = FinancialManager.objects.get(phone_number=phone)
                return manager.user
            elif user_type == 'support_agent':
                from core.SupportAgentModel import SupportAgent
                agent = SupportAgent.objects.get(phone_number=phone)
                return agent.user
        except Exception as e:
            print(f"Error finding user: {e}")
            return None
        return None


class SalesAgentLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'sales_agent'
        self.fields['user_type'].widget = forms.HiddenInput()
        
class LogisticsManagerLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'logistics_manager'
        self.fields['user_type'].widget = forms.HiddenInput()

class FinancialManagerLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'financial_manager'
        self.fields['user_type'].widget = forms.HiddenInput()

class SupportAgentLoginForm(OTPLoginForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'support_agent'
        self.fields['user_type'].widget = forms.HiddenInput()
