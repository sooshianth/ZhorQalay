from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import SalesAgent

def sales_agent_login_view(request):
    if request.user.is_authenticated:
        return redirect('sales_agent_profile')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if hasattr(user, 'sales_agent'):
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")  # ✅ این خطو اضافه کن برای تست
                return redirect('sales_agent_profile')
            else:
                messages.error(request, "شما کارشناس فروش نیستید. لطفاً از حساب کارشناس فروش استفاده کنید.")
        else:
            messages.error(request, "نام کاربری یا رمز عبور اشتباه است.")

    return render(request, "sales_agent_login.html")

