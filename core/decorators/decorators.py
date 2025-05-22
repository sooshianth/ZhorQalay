from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps
from django.contrib import messages

def is_sales_agent(user):
    """
    تشخیص اینکه کاربر یک کارشناس فروش است
    """
    if user.is_authenticated:
        try:
            return hasattr(user, 'sales_agent')
        except:
            return False
    return False

def is_logistics_manager(user):
    """
    تشخیص اینکه کاربر یک مدیر لجستیک است
    """
    if user.is_authenticated:
        try:
            return hasattr(user, 'logistics_manager')
        except:
            return False
    return False

def is_financial_manager(user):
    """
    تشخیص اینکه کاربر یک مدیر مالی است
    """
    if user.is_authenticated:
        try:
            return hasattr(user, 'financial_manager')
        except:
            return False
    return False

def is_support_agent(user):
    """
    تشخیص اینکه کاربر یک کارشناس پشتیبانی است
    """
    if user.is_authenticated:
        try:
            return hasattr(user, 'support_agent')
        except:
            return False
    return False

def is_employee(user):
    if user.is_authenticated:
        try:
            return hasattr(user, 'employee')
        except:
            return False
    return False

def is_admin(user):
    """
    تشخیص اینکه کاربر یک ادمین یا سوپر یوزر است
    """
    return user.is_authenticated and (user.is_staff or user.is_superuser)

# دکوراتورهای اختصاصی برای هر نقش با پیام

def sales_agent_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص کارشناس فروش
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_sales_agent(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط کارشناسان فروش به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def logistics_manager_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص مدیر لجستیک
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_logistics_manager(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط مدیران لجستیک به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def financial_manager_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص مدیر مالی
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_financial_manager(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط مدیران مالی به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def support_agent_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص کارشناس پشتیبانی
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_support_agent(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط کارشناسان پشتیبانی به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def admin_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص ادمین
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_admin(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط مدیران سیستم به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def employee_required(function=None, redirect_url='/login/', message=None):
    """
    دکوراتور برای دسترسی‌های مخصوص کارمزدگیران
    """
    def actual_decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if is_employee(request.user):
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'فقط کارمندان به این بخش دسترسی دارند'
                messages.error(request, error_message)
                return redirect(redirect_url)
        return _wrapped_view


# دکوراتور پیشرفته برای دسترسی چند نقشی
def role_required(*roles, redirect_url='/', message='دسترسی محدود است'):
    """
    دکوراتور برای دسترسی چند نقشی
    مثال استفاده: @role_required('sales_agent', 'admin', redirect_url='/access-denied/', message='دسترسی محدود است')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            allowed = False
            
            for role in roles:
                if role == 'admin' and is_admin(request.user):
                    allowed = True
                    break
                elif role == 'sales_agent' and is_sales_agent(request.user):
                    allowed = True
                    break
                elif role == 'logistics_manager' and is_logistics_manager(request.user):
                    allowed = True
                    break
                elif role == 'financial_manager' and is_financial_manager(request.user):
                    allowed = True
                    break
                elif role == 'support_agent' and is_support_agent(request.user):
                    allowed = True
                    break
                elif role == 'employee' and is_employee(request.user):
                    allowed = True
                    break

            if allowed:
                return view_func(request, *args, **kwargs)
            else:
                error_message = message or 'شما دسترسی لازم برای این صفحه را ندارید'
                messages.error(request, error_message)
                return redirect(redirect_url)
                
        return _wrapped_view
    
    # این بررسی برای حالتی است که کاربر پارامتر message یا redirect_url را تعیین کرده باشد
    if len(roles) == 1 and callable(roles[0]):
        view_func = roles[0]
        roles = []
        return decorator(view_func)
    
    return decorator 