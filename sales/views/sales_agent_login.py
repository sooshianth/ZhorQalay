from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from core.forms.forms import SalesAgentLoginForm

def sales_agent_login_view(request):
    if request.user.is_authenticated:
        return redirect('sales_agent_profile')

    if request.method == "POST":
        form = SalesAgentLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            
            if user is not None and hasattr(user, 'sales_agent'):
                login(request, user)
                print(f"✅ لاگین موفق! یوزر: {user.username}")
                return redirect('sales_agent_profile')
            else:
                messages.error(request, "شما کارشناس فروش نیستید. لطفاً از حساب کارشناس فروش استفاده کنید.")
        else:
            messages.error(request, "لطفاً کپچا را به درستی وارد کنید.")
    else:
        form = SalesAgentLoginForm()

    return render(request, "sales_agent_login.html", {'form': form})