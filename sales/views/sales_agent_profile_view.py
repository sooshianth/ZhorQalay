from core.models import SalesAgent, Customer, Purchase, CargoProduct, CallSession
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

@login_required
def sales_agent_profile_view(request):
    # بررسی کنید که کاربر کارشناس فروش باشد
    if not hasattr(request.user, 'sales_agent'):
        messages.error(request, "شما مجاز به مشاهده این صفحه نیستید. لطفاً با حساب کارشناس فروش وارد شوید.")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent  
    all_tasks = sales_agent.get_all_tasks()
    unpaid_purchases = sales_agent.get_all_unpaid_sales()
    active_purchases = sales_agent.get_all_active_sales()
    archived_purchases = sales_agent.get_all_archived_sales()
    total_sales_this_month = sales_agent.get_this_month_sales_weight()

    context = {
        'sales_agent': sales_agent,
        'all_tasks': all_tasks,
        'unpaid_purchases': unpaid_purchases,
        'active_purchases': active_purchases,
        'archived_purchases': archived_purchases,
        'total_sales_this_month': total_sales_this_month,
    }

    return render(request, 'sales_agent_profile.html', context)

@login_required
def customer_list_view(request):
    if not hasattr(request.user, 'sales_agent'):
        messages.error(request, "شما مجاز به مشاهده این بخش نیستید.")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent  
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'name')  # مقدار پیش‌فرض: نام مشتری
    order = request.GET.get('order', 'asc')  # ترتیب پیش‌فرض: صعودی

    # دریافت لیست مشتریان این کارشناس فروش
    customers = sales_agent.get_all_customers()

    # فیلتر جستجو
    if search_query:
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )

    # مرتب‌سازی لیست مشتریان
    if sort_by == 'name':
        customers = customers.order_by('name' if order == 'asc' else '-name')
    elif sort_by == 'phone':
        customers = customers.order_by('phone_number' if order == 'asc' else '-phone_number')

    context = {
        'customers': customers,
        'search_query': search_query,
        'sort_by': sort_by,
        'order': order,
    }

    return render(request, 'customer_list.html', context)