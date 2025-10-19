from django.contrib.auth import logout
from django.utils import timezone
from django.shortcuts import redirect
from datetime import timedelta
from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.urls import reverse, reverse_lazy
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from core.logging_filters import set_log_context
from time import time
import logging

# ایجاد لاگر برای middleware امنیتی
security_logger = logging.getLogger('security')
logger = logging.getLogger('core.middleware')


class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_time = timezone.now()
            
            # Get the last activity time from the session
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                # Convert string time to datetime object if stored as string
                if isinstance(last_activity, str):
                    last_activity = timezone.datetime.fromisoformat(last_activity)
                
                # Calculate inactivity duration
                inactive_time = current_time - last_activity
                
                # Check if user has been inactive longer than the timeout period
                if inactive_time > timedelta(seconds=settings.SESSION_COOKIE_AGE):
                    # Log the user out
                    logout(request)
                    # Redirect to home page
                    return redirect('/')
            
            # Update last activity time
            request.session['last_activity'] = current_time.isoformat()

        response = self.get_response(request)
        return response 
    
class RestrictAdminAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # اگر درخواست به مسیر /ewdfsrgtyuiougyjgtrdthugghuji/ یا زیرمسیرهای آن باشد
        if request.path.startswith('/ewdfsrgtyuiougyjgtrdthugghuji/'):
            # اگر کاربر لاگین نکرده یا سوپریوزر نیست، مستقیماً ریدایرکت شود
            if not request.user.is_authenticated or not request.user.is_superuser:
                return HttpResponseRedirect(reverse('home_view'))
            # اگر از مسیر درست نیامده باشد (یعنی admin_access_allowed در session نباشد)
            if not request.session.get('admin_access_allowed', False):
                return HttpResponseRedirect(reverse('home_view'))

        response = self.get_response(request)
        return response


class SecurityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware برای لاگ کردن تمام درخواست‌ها و محافظت امنیتی
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def get_client_ip(self, request):
        """
        دریافت IP کلاینت با پشتیبانی از proxy
        """
        direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        real_ip = request.META.get('HTTP_X_REAL_IP')
        
        client_ip = direct_ip
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        elif real_ip:
            client_ip = real_ip
        
        def is_local_ip(ip):
            if ip == 'Unknown':
                return False
            return (ip.startswith('192.168.') or 
                   ip.startswith('10.') or 
                   ip.startswith('172.') or 
                   ip.startswith('127.') or
                   ip == 'localhost')
        
        ip_type = "local" if is_local_ip(client_ip) else "external"
        
        if forwarded_for or real_ip:
            proxy_info = f" (via {direct_ip})"
        else:
            proxy_info = ""
        
        return f"{client_ip}({ip_type}){proxy_info}"
    
    def process_request(self, request):
        """
        پردازش درخواست ورودی
        """
        # ثبت زمان شروع درخواست
        request.start_time = time()
        
        # دریافت اطلاعات درخواست
        client_ip = self.get_client_ip(request)
        method = request.method
        path = request.path
        user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
        username = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
        
        # لاگ درخواست
        logger.info(f"REQUEST: {method} {path} - User: {username} - IP: {client_ip} - UA: {user_agent[:100]}")
        
        client_ip_main = client_ip.split('(')[0]  # فقط IP اصلی

        # Skip specific IP from rate limit
        if client_ip_main == "80.210.45.53":
            pass  # Do nothing, allow full access
        else:
            # Fixed 60s window using current minute
            minute_slot = int(time() // 60)
            rate_limit_key = f"rate_limit_{client_ip_main}_{minute_slot}"

            current_requests = cache.get(rate_limit_key, 0)

            # Check limit
            if current_requests >= 100:
                security_logger.alert(
                    f"RATE LIMIT EXCEEDED: IP {client_ip_main} - User: {username} - Path: {path}"
                )
                return HttpResponseForbidden(
                    "تعداد درخواست‌های شما بیش از حد مجاز است. لطفا کمی صبر کنید."
                )

            # Increment count — uses fixed window, no timeout reset problem
            cache.set(rate_limit_key, current_requests + 1, timeout=60)
        
        return None
    
    def process_response(self, request, response):
        """
        پردازش پاسخ خروجی
        """
        # محاسبه زمان پردازش درخواست
        if hasattr(request, 'start_time'):
            processing_time = time() - request.start_time
        else:
            processing_time = 0
        
        # دریافت اطلاعات درخواست
        client_ip = self.get_client_ip(request)
        method = request.method
        path = request.path
        status_code = response.status_code
        username = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
        
        # لاگ پاسخ
        logger.info(f"RESPONSE: {method} {path} - Status: {status_code} - User: {username} - IP: {client_ip} - Time: {processing_time:.3f}s")
        
        # لاگ امنیتی برای status code های مشکوک
        if status_code >= 400:
            if status_code == 404:
                security_logger.info(f"404 NOT FOUND: {method} {path} - User: {username} - IP: {client_ip}")
            elif status_code == 403:
                security_logger.alert(f"403 FORBIDDEN: {method} {path} - User: {username} - IP: {client_ip}")
            elif status_code == 401:
                security_logger.alert(f"401 UNAUTHORIZED: {method} {path} - User: {username} - IP: {client_ip}")
            elif status_code >= 500:
                security_logger.error(f"SERVER ERROR {status_code}: {method} {path} - User: {username} - IP: {client_ip}")
        
        return response
    
    def process_exception(self, request, exception):
        """
        پردازش خطاهای غیرمنتظره
        """
        client_ip = self.get_client_ip(request)
        method = request.method
        path = request.path
        username = request.user.username if hasattr(request, 'user') and request.user.is_authenticated else 'Anonymous'
        
        # لاگ امنیتی برای exception ها
        security_logger.error(f"EXCEPTION: {method} {path} - User: {username} - IP: {client_ip} - Exception: {str(exception)}")
        
        return None


class LoginAttemptMiddleware(MiddlewareMixin):
    """
    Middleware برای نظارت بر تلاش‌های ورود مشکوک
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def get_client_ip(self, request):
        """دریافت IP کلاینت"""
        direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        
        client_ip = direct_ip
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        return client_ip
    
    def process_request(self, request):
        """بررسی تلاش‌های ورود مشکوک"""
        
        # فقط برای مسیرهای مربوط به authentication
        if request.path.startswith('/authentication/'):
            client_ip = self.get_client_ip(request)
            
            # بررسی تعداد تلاش‌های ناموفق ورود در 1 ساعت گذشته
            failed_attempts_key = f"failed_login_attempts_{client_ip}"
            failed_attempts = cache.get(failed_attempts_key, 0)
            
            # اگر بیش از 20 تلاش ناموفق در ساعت گذشته داشته باشد
            if failed_attempts >= 20:
                security_logger.alert(f"SUSPICIOUS LOGIN ACTIVITY: IP {client_ip} has {failed_attempts} failed attempts in last hour")
                
                # بلاک کردن IP برای 1 ساعت
                blocked_key = f"blocked_ip_{client_ip}"
                if not cache.get(blocked_key):
                    cache.set(blocked_key, True, timeout=3600)  # 1 ساعت
                    security_logger.alert(f"IP BLOCKED: {client_ip} blocked for 1 hour due to suspicious activity")
                
                return HttpResponseForbidden("IP شما به دلیل تلاش‌های مشکوک برای ورود، موقتاً مسدود شده است.")
        
        return None 
    

class LogContextMiddleware(MiddlewareMixin):
    """
    Middleware برای تنظیم context اطلاعات کاربر برای logging
    """
    def process_request(self, request):
        user = getattr(request, 'user', None)
        # دریافت شماره تلفن کاربر از session
        user_phone = None
        if user and user.is_authenticated:
            # برای ادمین‌ها
            if request.session.get('is_admin_session'):
                user_phone = request.session.get('admin_phone_number')
            else:
                # برای کاربران عادی
                user_phone = request.session.get('logged_in_phone_number')
            
            # اگر از decorator تنظیم شده باشد، اولویت با آن است
            decorator_phone = getattr(request, 'user_phone_number', None)
            if decorator_phone:
                user_phone = decorator_phone
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # If there are multiple IPs, client IP is typically the first one
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', None)
        content_length = request.META.get('CONTENT_LENGTH')
        try:
            upload_size = int(content_length) if content_length not in [None, ''] else 0
        except ValueError:
            upload_size = 0
        # We can't get download_size yet - set it in process_response
        set_log_context(user, ip, user_phone, upload_size, 0)
        request._up_size = upload_size

    def process_response(self, request, response):
        # Get down size
        download_size = len(response.content) if hasattr(response, 'content') else 0
        # Get context again (so we keep username/ip/up)
        user = getattr(request, 'user', None)
        # دریافت شماره تلفن کاربر از session
        user_phone = None
        if user and user.is_authenticated:
            # برای ادمین‌ها
            if request.session.get('is_admin_session'):
                user_phone = request.session.get('admin_phone_number')
            else:
                # برای کاربران عادی
                user_phone = request.session.get('logged_in_phone_number')
            
            # اگر از decorator تنظیم شده باشد، اولویت با آن است
            decorator_phone = getattr(request, 'user_phone_number', None)
            if decorator_phone:
                user_phone = decorator_phone
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # If there are multiple IPs, client IP is typically the first one
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', None)
        content_length = request.META.get('CONTENT_LENGTH')
        try:
            upload_size = int(content_length) if content_length not in [None, ''] else 0
        except ValueError:
            upload_size = 0
        set_log_context(user, ip, user_phone, upload_size, download_size)
        return response


def custom_session_expired_middleware(get_response):
    """
    Middleware برای هدایت کاربران غیر احراز هویت شده به صفحه لاگین
    """
    def middleware(request):
        LOGIN_URL = getattr(settings, 'LOGIN_URL', '/authentication/login/')
        if not request.user.is_authenticated and request.path not in [reverse_lazy('unified_login'), '/authentication/login/', '/core/active-users/']:
            return redirect_to_login(request.get_full_path(), login_url=LOGIN_URL)
        return get_response(request)
    return middleware


class AdminSessionManagementMiddleware(MiddlewareMixin):
    """
    Middleware برای مدیریت session های ادمین و بررسی مداوم دسترسی‌ها
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # بررسی دسترسی ادمین فقط برای کاربران احراز هویت شده
        if request.user.is_authenticated:
            # بررسی آیا session فعلی یک session ادمین است
            is_admin_session = request.session.get('is_admin_session', False)
            admin_phone_number = request.session.get('admin_phone_number')
            
            if is_admin_session and admin_phone_number:
                # بررسی آیا شماره هنوز در لیست ادمین‌ها است
                admin_numbers = getattr(settings, 'ADMIN_PHONE_NUMBERS', [])
                
                if admin_phone_number not in admin_numbers:
                    # شماره دیگر ادمین نیست، session را پاک کن
                    request.session.pop('is_admin_session', None)
                    request.session.pop('admin_phone_number', None)
                    request.session.pop('admin_access_allowed', None)
                    
                    # کاربر را از حالت superuser خارج کن
                    if request.user.is_superuser or request.user.is_staff:
                        request.user.is_superuser = False
                        request.user.is_staff = False
                        request.user.save()
                        
                    logger.warning(f"شماره {admin_phone_number} از لیست ادمین‌ها حذف شده - دسترسی‌های ادمین لغو شد")
                else:
                    # اطمینان از اینکه کاربر هنوز superuser است
                    if not request.user.is_superuser or not request.user.is_staff:
                        request.user.is_superuser = True
                        request.user.is_staff = True
                        request.user.save()
                        logger.info(f"دسترسی‌های superuser برای شماره ادمین {admin_phone_number} بازیابی شد")
            
            # بررسی دسترسی به پنل ادمین
            if request.path.startswith('/admin/'):
                if not request.session.get('admin_access_allowed', False):
                    logger.warning(f"تلاش دسترسی غیرمجاز به پنل ادمین توسط کاربر {request.user.username}")
                    return HttpResponseForbidden("دسترسی مجاز نیست - شما با شماره ادمین وارد نشده‌اید")
        
        return None