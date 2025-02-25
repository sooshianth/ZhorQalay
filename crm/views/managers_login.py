from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import SalesAgent

def logistics_manager_login_view(request):
    # اگر کاربر قبلاً لاگین کرده باشد، به صفحه پروفایل هدایت شود
    if request.user.is_authenticated:
        return redirect('logistics_manager_profile')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if hasattr(user, 'logistics_manager'):  # بررسی کنید که کاربر مدیر لجستیک باشد
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")
                return redirect('logistics_manager_profile')  # هدایت به صفحه پروفایل پس از لاگین
            else:
                messages.error(request, "شما مدیر لجستیک نیستید. لطفاً از حساب مدیر لجستیک استفاده کنید.")
        else:
            messages.error(request, "نام کاربری یا رمز عبور اشتباه است.")

    return render(request, "logistics_manager_login.html")



def financial_manager_login_view(request):
    # اگر کاربر قبلاً لاگین کرده باشد، به صفحه پروفایل هدایت شود
    if request.user.is_authenticated:
        return redirect('financial_manager_profile')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if hasattr(user, 'financial_manager'):  # بررسی کنید که کاربر مدیر مالی باشد
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")
                return redirect('financial_manager_profile')  # هدایت به صفحه پروفایل پس از لاگین
            else:
                messages.error(request, "شما مدیر مالی نیستید. لطفاً از حساب مدیر مالی استفاده کنید.")
        else:
            messages.error(request, "نام کاربری یا رمز عبور اشتباه است.")

    return render(request, "financial_manager_login.html")
