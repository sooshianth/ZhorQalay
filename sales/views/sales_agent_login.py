from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import SalesAgent

def sales_agent_login_view(request):
    # اگر کاربر قبلاً لاگین کرده باشد، به صفحه پروفایل هدایت شود
    if request.user.is_authenticated:
        return redirect('sales_agent_profile')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if hasattr(user, 'sales_agent'):  # بررسی کنید که کاربر کارشناس فروش باشد
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")
                return redirect('sales_agent_profile')  # هدایت به صفحه پروفایل پس از لاگین
            else:
                messages.error(request, "شما کارشناس فروش نیستید. لطفاً از حساب کارشناس فروش استفاده کنید.")
        else:
            messages.error(request, "نام کاربری یا رمز عبور اشتباه است.")

    return render(request, "sales_agent_login.html")