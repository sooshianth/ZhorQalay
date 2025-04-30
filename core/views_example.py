from django.shortcuts import render
from django.http import HttpResponse
from .decorators.decorators import (
    sales_agent_required, 
    logistics_manager_required,
    financial_manager_required,
    support_agent_required,
    admin_required,
    role_required
)

# مثال استفاده از دکوراتورهای تک نقشی

@sales_agent_required
def sales_dashboard(request):
    """
    این صفحه فقط برای کارشناسان فروش قابل دسترسی است
    """
    return render(request, 'sales_dashboard.html')

# مثال با پیام سفارشی
@logistics_manager_required(message="فقط مدیران لجستیک می‌توانند به این داشبورد دسترسی داشته باشند")
def logistics_dashboard(request):
    """
    این صفحه فقط برای مدیران لجستیک قابل دسترسی است
    """
    return render(request, 'logistics_dashboard.html')

# مثال با پیام سفارشی و مسیر بازگشت سفارشی
@financial_manager_required(redirect_url='/forbidden/', message="دسترسی به بخش مالی محدود شده است")
def financial_dashboard(request):
    """
    این صفحه فقط برای مدیران مالی قابل دسترسی است
    """
    return render(request, 'financial_dashboard.html')

@support_agent_required
def support_dashboard(request):
    """
    این صفحه فقط برای کارشناسان پشتیبانی قابل دسترسی است
    """
    return render(request, 'support_dashboard.html')

@admin_required
def admin_dashboard(request):
    """
    این صفحه فقط برای ادمین‌ها قابل دسترسی است
    """
    return render(request, 'admin_dashboard.html')

# مثال استفاده از دکوراتور چند نقشی

@role_required('sales_agent', 'admin')
def sales_reports(request):
    """
    این صفحه برای کارشناسان فروش و ادمین‌ها قابل دسترسی است
    """
    return render(request, 'sales_reports.html')

# مثال دکوراتور چند نقشی با پیام سفارشی
@role_required('logistics_manager', 'financial_manager', 'admin', 
              message="فقط مدیران لجستیک، مالی و ادمین‌ها به این بخش دسترسی دارند")
def inventory_management(request):
    """
    این صفحه برای مدیران لجستیک، مدیران مالی و ادمین‌ها قابل دسترسی است
    """
    return render(request, 'inventory_management.html')

# مثال با مسیر بازگشت و پیام سفارشی
@role_required('admin', 'financial_manager', 
              redirect_url='/dashboard/', 
              message="فقط مدیران مالی و ادمین‌ها می‌توانند به بخش پرداخت‌ها دسترسی داشته باشند")
def payment_management(request):
    """
    این صفحه برای مدیران مالی و ادمین‌ها قابل دسترسی است
    """
    return render(request, 'payment_management.html') 