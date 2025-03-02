from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.models import SalesAgent
from sales.views.forms import LogisticsManagerLoginForm  # فرم جدید را ایمپورت کنید
from sales.views.forms import FinancialManagerLoginForm

def logistics_manager_login_view(request):
    if request.user.is_authenticated:
        return redirect('logistics_manager_profile')

    if request.method == "POST":
        form = LogisticsManagerLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None and hasattr(user, 'logistics_manager'):
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")
                return redirect('logistics_manager_profile')
            else:
                messages.error(request, "شما مدیر لجستیک نیستید. لطفاً از حساب مدیر لجستیک استفاده کنید.")
        else:
            messages.error(request, "لطفاً کپچا را به درستی وارد کنید.")
    else:
        form = LogisticsManagerLoginForm()

    return render(request, "logistics_manager_login.html", {'form': form})


def financial_manager_login_view(request):
    if request.user.is_authenticated:
        return redirect('financial_manager_profile')

    if request.method == "POST":
        form = FinancialManagerLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None and hasattr(user, 'financial_manager'):
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")
                return redirect('financial_manager_profile')
            else:
                messages.error(request, "شما مدیر مالی نیستید. لطفاً از حساب مدیر مالی استفاده کنید.")
        else:
            messages.error(request, "لطفاً کپچا را به درستی وارد کنید.")
    else:
        form = FinancialManagerLoginForm()

    return render(request, "financial_manager_login.html", {'form': form})
