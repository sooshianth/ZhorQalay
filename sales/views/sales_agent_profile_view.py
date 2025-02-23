from core.models import SalesAgent, Customer, Purchase, CargoProduct, CallSession
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

@login_required
def sales_agent_profile_view(request):
    if not hasattr(request.user, 'sales_agent'):
        messages.error(request, "شما مجاز به مشاهده این صفحه نیستید. لطفاً با حساب کارشناس فروش وارد شوید.")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent  
    all_tasks = sales_agent.get_all_tasks()
    unpaid_purchases = sales_agent.get_all_unpaid_sales()
    active_purchases = sales_agent.get_all_active_sales()
    archived_purchases = sales_agent.get_all_archived_sales()
    total_sales_this_month = sales_agent.get_this_month_sales_weight()

    # Pagination for tasks
    task_page = request.GET.get('task_page', 1)
    task_paginator = Paginator(all_tasks, 5)  # Show 10 tasks per page
    try:
        tasks = task_paginator.page(task_page)
    except PageNotAnInteger:
        tasks = task_paginator.page(1)
    except EmptyPage:
        tasks = task_paginator.page(task_paginator.num_pages)

    # Pagination for unpaid purchases
    unpaid_page = request.GET.get('unpaid_page', 1)
    unpaid_paginator = Paginator(unpaid_purchases, 3)  # Show 10 unpaid purchases per page
    try:
        unpaid = unpaid_paginator.page(unpaid_page)
    except PageNotAnInteger:
        unpaid = unpaid_paginator.page(1)
    except EmptyPage:
        unpaid = unpaid_paginator.page(unpaid_paginator.num_pages)

    # Pagination for active purchases
    active_page = request.GET.get('active_page', 1)
    active_paginator = Paginator(active_purchases, 3)  # Show 10 active purchases per page
    try:
        active = active_paginator.page(active_page)
    except PageNotAnInteger:
        active = active_paginator.page(1)
    except EmptyPage:
        active = active_paginator.page(active_paginator.num_pages)

    # Pagination for archived purchases
    archived_page = request.GET.get('archived_page', 1)
    archived_paginator = Paginator(archived_purchases, 10)  # Show 10 archived purchases per page
    try:
        archived = archived_paginator.page(archived_page)
    except PageNotAnInteger:
        archived = archived_paginator.page(1)
    except EmptyPage:
        archived = archived_paginator.page(archived_paginator.num_pages)

    context = {
        'sales_agent': sales_agent,
        'tasks': tasks,
        'unpaid': unpaid,
        'active': active,
        'archived': archived,
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

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(customers, 5)  # نمایش 10 مشتری در هر صفحه
    try:
        customers_page = paginator.page(page)
    except PageNotAnInteger:
        customers_page = paginator.page(1)
    except EmptyPage:
        customers_page = paginator.page(paginator.num_pages)

    context = {
        'customers': customers_page,  # ارسال صفحه مشتریان به جای لیست کامل
        'search_query': search_query,
        'sort_by': sort_by,
        'order': order,
    }

    return render(request, 'customer_list.html', context)