from core.models import SalesAgent, Customer, Purchase, CargoProduct, CallSession
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import Http404
from django.views import View
from django.db.models import Q

def sales_agent_profile_view(request):
    # دریافت کارشناس فروش مربوط به کاربر وارد شده
    sales_agent = request.user.sales_agent  

    # دریافت همه تسک‌های این کارشناس فروش و مرتب‌سازی بر اساس تاریخ (جدیدترین اول)
    all_tasks = sales_agent.get_all_tasks().order_by('-due_date')

    # دریافت خریدهای پرداخت نشده (Unpaid)
    unpaid_purchases = sales_agent.get_all_unpaid_sales()

    # دریافت خریدهای فعال (Active)
    active_purchases = sales_agent.get_all_active_sales()

    # دریافت خریدهای آرشیو شده (Archived)
    archived_purchases = sales_agent.get_all_archived_sales()

    # دریافت مجموع فروش‌های این ماه
    total_sales_this_month = sales_agent.get_this_month_sales_amount()

    # آماده‌سازی context برای ارسال به template
    context = {
        'sales_agent': sales_agent,
        'all_tasks': all_tasks,  # همه تسک‌ها
        'unpaid_purchases': unpaid_purchases,  # خریدهای پرداخت نشده
        'active_purchases': active_purchases,  # خریدهای فعال
        'archived_purchases': archived_purchases,  # خریدهای آرشیو شده
        'total_sales_this_month': total_sales_this_month,
    }

    # رندر کردن template با استفاده از context
    return render(request, 'sales_agent_profile.html', context)

def customer_list_view(request):
    # دریافت کارشناس فروش مربوط به کاربر وارد شده
    sales_agent = request.user.sales_agent  

    # دریافت پارامتر جستجو از URL
    search_query = request.GET.get('search', '')

    # دریافت لیست مشتریان این کارشناس فروش
    customers = sales_agent.get_all_customers()

    # اگر پارامتر جستجو وجود داشت، فیلتر اعمال می‌شود
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |  # جستجو بر اساس نام
            Q(phone_number__icontains=search_query)  # جستجو بر اساس شماره موبایل
        )

    # آماده‌سازی context برای ارسال به template
    context = {
        'customers': customers,
        'search_query': search_query,  # برای نمایش عبارت جستجو در فرم
    }

    # رندر کردن template با استفاده از context
    return render(request, 'customer_list.html', context)