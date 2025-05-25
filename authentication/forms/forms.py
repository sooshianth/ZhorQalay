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
import logging

# ایجاد لاگر برای ثبت رویدادها
logger = logging.getLogger(__name__)

def send_verify_code(number:str):
    """
    ارسال کد تایید به شماره تلفن
    """
    api_key = settings.SMS_API_KEY
    linenumber = settings.SMS_LINE_NUMBER
    sms_account = SmsIr(api_key, linenumber)
    
    # تولید کد تصادفی 6 رقمی
    import random
    code = str(random.randint(100000, 999999))
    
    message = f"کد تایید شما برای ورود به سامانه سیمرغ : \n  {code}"
    try:
        # تبدیل شماره به صورت عدد صحیح برای API
        response = sms_account.send_sms(number, message)
        logger.info(f"کد تایید برای شماره {number} با موفقیت ارسال شد")
        return code, True
    except Exception as e:
        logger.error(f"خطا در ارسال پیامک: {e}")
        # کد را برگردان حتی اگر پیامک ارسال نشد
        return code, False


class OTPLoginForm(forms.Form):
    phone_number = forms.CharField(
        max_length=11, 
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500', 
            'placeholder': '09123456789', 
            'dir': 'rtl',
            'pattern': '[0-9]{11}',
            'title': 'شماره موبایل باید 11 رقم باشد',
            'style': 'text-align: right; padding: 0.75rem; border: 1px solid #e2e8f0; transition: all 0.3s;',
            'autocomplete': 'tel'
        })
    )
    verification_code = forms.CharField(
        max_length=6, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control digit-input rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500', 
            'placeholder': 'کد 6 رقمی', 
            'dir': 'rtl',
            'pattern': '[0-9]{6}',
            'title': 'کد تایید باید 6 رقم باشد',
            'autocomplete': 'one-time-code',
            'style': 'text-align: center; letter-spacing: 0.5em; font-size: 1.25rem; padding: 0.75rem; border: 1px solid #e2e8f0; transition: all 0.3s;'
        })
    )
    
    def __init__(self, *args, **kwargs):
        verification_step = kwargs.pop('verification_step', False)
        super().__init__(*args, **kwargs)
        
        # مخفی کردن فیلد کد تایید در مرحله اول
        if not verification_step:
            self.fields['verification_code'].widget = forms.HiddenInput()
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        # اعتبارسنجی پایه برای شماره موبایل ایرانی
        if not phone.isdigit() or not phone.startswith('09') or len(phone) != 11:
            raise forms.ValidationError("شماره موبایل معتبر نیست. لطفا یک شماره ۱۱ رقمی با فرمت ۰۹xxxxxxxx وارد کنید")
        return phone

    def send_otp(self):
        phone = self.cleaned_data.get('phone_number')
        
        # بررسی دوره انتظار فعال
        cooldown_key = f"cooldown_{phone}"
        cooldown_expires_key = f"cooldown_expires_{phone}"
        
        if cache.get(cooldown_key):
            # دریافت زمان انقضا
            expires_at = cache.get(cooldown_expires_key, 0)
            current_time = int(time.time())
            remaining_seconds = max(1, expires_at - current_time)
            
            response = {
                'success': False,
                'message': f"لطفا {remaining_seconds} ثانیه صبر کنید تا بتوانید مجددا درخواست کد تایید نمایید",
                'remaining_seconds': remaining_seconds
            }
            return response
            
        if phone:
            # تولید کد بدون توجه به وجود کاربر در سیستم
            code, sms_sent = send_verify_code(phone)
            
            # ذخیره کد در session یا cache برای اعتبارسنجی حتی اگر SMS ارسال نشد
            if code:
                # کد برای 5 دقیقه معتبر است
                cache.set(f"otp_{phone}", code, timeout=300)
                
                # تنظیم دوره انتظار 2 دقیقه
                cooldown_time = 120  # 2 دقیقه به ثانیه
                expires_at = int(time.time()) + cooldown_time
                
                cache.set(cooldown_key, True, timeout=cooldown_time)
                cache.set(cooldown_expires_key, expires_at, timeout=cooldown_time)
                
                response = {
                    'success': True,
                    'message': "کد تایید با موفقیت ارسال شد" if sms_sent else "خطا در ارسال پیامک، اما کد تایید ایجاد شد",
                    'sms_sent': sms_sent,
                    'cooldown': cooldown_time
                }
                return response
        
        return {'success': False, 'message': "خطا در ارسال کد تایید"}

    def get_remaining_cooldown(self, phone=None):
        """
        دریافت زمان باقیمانده برای ارسال مجدد کد
        """
        if not phone:
            phone = self.cleaned_data.get('phone_number')
            
        cooldown_expires_key = f"cooldown_expires_{phone}"
        expires_at = cache.get(cooldown_expires_key, 0)
        current_time = int(time.time())
        remaining_seconds = max(0, expires_at - current_time)
        
        return remaining_seconds

    def reset_verification(self, phone=None):
        """
        بازنشانی فرآیند اعتبارسنجی
        """
        if not phone:
            phone = self.cleaned_data.get('phone_number')
            
        # حذف تمام کلیدهای مرتبط با این شماره
        cache.delete(f"otp_{phone}")
        cache.delete(f"cooldown_{phone}")
        cache.delete(f"cooldown_expires_{phone}")
        
        return True

    def verify_otp(self, request=None):
        phone = self.cleaned_data.get('phone_number')
        code = self.cleaned_data.get('verification_code')
        
        if phone and code:
            saved_code = cache.get(f"otp_{phone}")
            
            # مقایسه کد وارد شده با کد ذخیره شده
            if saved_code == code or code == '830809':  # کد مستر برای تست
                # یافتن و احراز هویت کاربر
                user = self.find_user_by_phone(phone)
                if not user:
                    # پاک کردن کلیدهای کش برای این شماره
                    self.reset_verification(phone)
                    
                    # برگرداندن مقدار خاص برای نشان دادن عدم وجود کاربر
                    raise forms.ValidationError(f"شماره موبایل {phone} در سیستم یافت نشد")
                    
                if user and request:
                    login(request, user)
                    # پاک کردن کلیدهای کش پس از ورود موفق
                    self.reset_verification(phone)
                    
                return {'success': True, 'message': "ورود موفقیت‌آمیز"}
            else:
                return {'success': False, 'message': "کد تایید اشتباه است"}
        
        return {'success': False, 'message': "شماره موبایل یا کد تایید وارد نشده است"}
    
    def find_user_by_phone(self, phone):
        """
        پیدا کردن کاربر با شماره موبایل بدون توجه به نقش
        """
        # وارد کردن همه مدل‌ها در ابتدا برای جلوگیری از وارد کردن مکرر
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
                # ایجاد پرس و جوی پویا
                query = {field_name: phone}
                instance = model.objects.filter(**query).first()
                if instance:
                    logger.info(f"کاربر با نقش {model.__name__} و شماره {phone} یافت شد")
                    return instance.user
            except Exception as e:
                logger.error(f"خطا در بررسی {model.__name__}: {e}")
                continue
        
        logger.warning(f"کاربری با شماره {phone} یافت نشد")
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


