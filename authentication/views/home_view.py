from django.shortcuts import render, redirect
from django.contrib import messages
from authentication.forms.forms import OTPLoginForm
from django.core.cache import cache
from django import forms
import json
from django.http import JsonResponse

def home_view(request):
    show_admin_link = False
    if request.user.is_authenticated:
        # اگر کاربر سوپریوزر باشه و بعد از لاگین موفقیت‌آمیز باشه، لینک ادمین رو نشون بده
        if request.user.is_superuser:
            request.session['admin_access_allowed'] = True
            show_admin_link = True
    
    # هدایت به پروفایل مناسب بر اساس نقش
    if request.user.is_authenticated:
        if hasattr(request.user, 'financial_manager') and request.user.financial_manager is not None:
            return redirect('financial_manager_profile')
        elif hasattr(request.user, 'logistics_manager') and request.user.logistics_manager is not None:
            return redirect('logistics_manager_profile')
        elif hasattr(request.user, 'sales_agent') and request.user.sales_agent is not None:
            return redirect('sales_agent_profile')
        elif hasattr(request.user, 'support_agent') and request.user.support_agent is not None:
            return redirect('support_agent_profile')
        elif hasattr(request.user, 'employee') and request.user.employee is not None:
            return redirect('employee_profile')

    context = {
        'show_admin_link': show_admin_link,
    }
    return render(request, 'home.html', context)

def unified_login_view(request):
    """
    صفحه ورود واحد برای همه کاربران
    """
    if request.user.is_authenticated:
        # تشخیص نقش کاربر و هدایت به صفحه پروفایل مناسب
        if hasattr(request.user, 'financial_manager') and request.user.financial_manager is not None:
            return redirect('financial_manager_profile')
        elif hasattr(request.user, 'logistics_manager') and request.user.logistics_manager is not None:
            return redirect('logistics_manager_profile')
        elif hasattr(request.user, 'sales_agent') and request.user.sales_agent is not None:
            return redirect('sales_agent_profile')
        elif hasattr(request.user, 'support_agent') and request.user.support_agent is not None:
            return redirect('support_agent_profile')
        elif hasattr(request.user, 'employee') and request.user.employee is not None:
            return redirect('employee_profile')
        else:
            return redirect('home_view')

    # بررسی مرحله تایید
    verification_step = 'phone_number' in request.session and request.session.get('phone_number')
    
    # بررسی درخواست‌های AJAX
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == "POST":
        form = OTPLoginForm(data=request.POST, verification_step=verification_step)
        
        # درخواست ارسال مجدد کد
        if is_ajax and 'resend_code' in request.POST:
            phone_number = request.POST.get('phone_number')
            form = OTPLoginForm(initial={'phone_number': phone_number})
            
            if form.is_valid():
                # بازنشانی اعتبارسنجی قبلی برای امکان ارسال مجدد
                form.reset_verification(phone_number)
                response = form.send_otp()
                return JsonResponse(response)
            else:
                return JsonResponse({'success': False, 'message': 'شماره موبایل نامعتبر است'})
        
        # بررسی زمان باقی‌مانده کول‌داون
        elif is_ajax and 'check_cooldown' in request.POST:
            phone_number = request.POST.get('phone_number')
            form = OTPLoginForm(initial={'phone_number': phone_number})
            remaining = form.get_remaining_cooldown(phone_number)
            return JsonResponse({'remaining_seconds': remaining})
            
        # ارسال معمولی فرم
        elif form.is_valid():
            phone_number = form.cleaned_data.get('phone_number')
            verification_code = form.cleaned_data.get('verification_code')
            
            # اگر کد تایید داریم، بررسی آن
            if verification_code:
                try:
                    result = form.verify_otp(request)
                    if result.get('success'):
                        # پاک کردن داده‌های نشست بعد از ورود موفق
                        if 'phone_number' in request.session:
                            del request.session['phone_number']
                        
                        # اگر کاربر سوپریوزر باشه، دسترسی ادمین رو فعال کن
                        if request.user.is_superuser:
                            request.session['admin_access_allowed'] = True
                        
                        # پس از ورود موفق، تشخیص نقش کاربر و هدایت به صفحه مناسب
                        if hasattr(request.user, 'financial_manager') and request.user.financial_manager is not None:
                            return redirect('financial_manager_profile')
                        elif hasattr(request.user, 'logistics_manager') and request.user.logistics_manager is not None:
                            return redirect('logistics_manager_profile')
                        elif hasattr(request.user, 'sales_agent') and request.user.sales_agent is not None:
                            return redirect('sales_agent_profile')
                        elif hasattr(request.user, 'support_agent') and request.user.support_agent is not None:
                            return redirect('support_agent_profile')
                        elif hasattr(request.user, 'employee') and request.user.employee is not None:
                            return redirect('employee_profile')
                        else:
                            return redirect('home_view')
                    else:
                        messages.error(request, result.get('message', "کد تایید اشتباه است. لطفا مجددا تلاش کنید."))
                except forms.ValidationError as e:
                    # اگر شماره تلفن در سیستم یافت نشد
                    messages.error(request, str(e))
                    # حذف اطلاعات مرحله تایید از نشست
                    if 'phone_number' in request.session:
                        del request.session['phone_number']
                    # برگشت به مرحله اول ورود شماره تلفن
                    return render(request, "unified_login.html", {
                        'form': OTPLoginForm(),
                        'verification_step': False
                    })
            # در غیر این صورت، ارسال کد تایید
            else:
                try:
                    response = form.send_otp()
                    if response.get('success'):
                        request.session['phone_number'] = phone_number
                        
                        # برای درخواست‌های AJAX، پاسخ JSON برگردان
                        if is_ajax:
                            return JsonResponse(response)
                            
                        return render(request, "unified_login.html", {
                            'form': OTPLoginForm(initial={'phone_number': phone_number}, verification_step=True),
                            'verification_step': True,
                            'cooldown': response.get('cooldown', 120)
                        })
                    else:
                        messages.error(request, response.get('message', "خطا در ارسال کد تایید"))
                        if is_ajax:
                            return JsonResponse(response)
                except Exception as e:
                    messages.error(request, str(e))
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': str(e)})
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            
            if is_ajax:
                return JsonResponse({'success': False, 'errors': form.errors})
    else:
        initial_data = {}
        
        # بررسی پارامتر reset برای بازگشت به مرحله اول
        if 'reset' in request.GET and 'phone_number' in request.session:
            del request.session['phone_number']
            verification_step = False
        
        if 'phone_number' in request.session:
            initial_data['phone_number'] = request.session.get('phone_number')
            
        form = OTPLoginForm(initial=initial_data, verification_step=verification_step)
        
    # محاسبه زمان باقی‌مانده کول‌داون برای نمایش در تمپلیت
    cooldown_remaining = 0
    if verification_step:
        phone_number = request.session.get('phone_number')
        cooldown_remaining = form.get_remaining_cooldown(phone_number)

    return render(request, "unified_login.html", {
        'form': form,
        'verification_step': verification_step,
        'cooldown_remaining': cooldown_remaining
    })