from django.shortcuts import render, redirect
from django.contrib import messages
from core.forms.forms import OTPLoginForm
from django.core.cache import cache
from django import forms

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

    if request.method == "POST":
        form = OTPLoginForm(data=request.POST, verification_step=verification_step)
        if form.is_valid():
            phone_number = form.cleaned_data.get('phone_number')
            verification_code = form.cleaned_data.get('verification_code')
            
            # اگر کد تایید داریم، بررسی آن
            if verification_code:
                try:
                    if form.verify_otp(request):
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
                        messages.error(request, "کد تایید اشتباه است. لطفا مجددا تلاش کنید.")
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
                    form.send_otp()
                    request.session['phone_number'] = phone_number
                    return render(request, "unified_login.html", {
                        'form': OTPLoginForm(initial={'phone_number': phone_number}, verification_step=True),
                        'verification_step': True
                    })
                except Exception as e:
                    messages.error(request, str(e))
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        initial_data = {}
        if 'phone_number' in request.session:
            initial_data['phone_number'] = request.session.get('phone_number')
        form = OTPLoginForm(initial=initial_data, verification_step=verification_step)
        if verification_step:
            form.fields['phone_number'].widget.input_type = 'hidden'

    return render(request, "unified_login.html", {
        'form': form,
        'verification_step': verification_step
    })