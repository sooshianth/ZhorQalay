from core._models import SalesAgent, Customer, Purchase, CargoProduct, CallSession, Notification
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

    # دریافت تمام تسک‌ها
    all_tasks = sales_agent.get_all_tasks()

    # تقسیم تسک‌ها به انجام شده و انجام نشده
    pending_tasks = [task for task in all_tasks if not task.status]  # تسک‌های انجام نشده
    completed_tasks = [task for task in all_tasks if task.status]  # تسک‌های انجام شده

    # Pagination برای تسک‌های انجام نشده
    task_page = request.GET.get('task_page', 1)
    task_paginator = Paginator(pending_tasks, 5)  # نمایش ۵ تسک در هر صفحه
    try:
        tasks = task_paginator.page(task_page)
    except PageNotAnInteger:
        tasks = task_paginator.page(1)
    except EmptyPage:
        tasks = task_paginator.page(task_paginator.num_pages)

    # Pagination برای تسک‌های انجام شده
    completed_task_page = request.GET.get('completed_task_page', 1)
    completed_task_paginator = Paginator(completed_tasks, 5)  # نمایش ۵ تسک در هر صفحه
    try:
        completed_tasks_page = completed_task_paginator.page(completed_task_page)
    except PageNotAnInteger:
        completed_tasks_page = completed_task_paginator.page(1)
    except EmptyPage:
        completed_tasks_page = completed_task_paginator.page(completed_task_paginator.num_pages)

    # Pagination برای خریدها (بدون تغییر)
    unpaid_purchases = sales_agent.get_all_unpaid_sales()
    active_purchases = sales_agent.get_all_active_sales()
    archived_purchases = sales_agent.get_all_archived_sales()
    total_sales_this_month = sales_agent.get_this_month_sales_weight()

    unpaid_page = request.GET.get('unpaid_page', 1)
    unpaid_paginator = Paginator(unpaid_purchases, 3)
    try:
        unpaid = unpaid_paginator.page(unpaid_page)
    except PageNotAnInteger:
        unpaid = unpaid_paginator.page(1)
    except EmptyPage:
        unpaid = unpaid_paginator.page(unpaid_paginator.num_pages)

    active_page = request.GET.get('active_page', 1)
    active_paginator = Paginator(active_purchases, 3)
    try:
        active = active_paginator.page(active_page)
    except PageNotAnInteger:
        active = active_paginator.page(1)
    except EmptyPage:
        active = active_paginator.page(active_paginator.num_pages)

    archived_page = request.GET.get('archived_page', 1)
    archived_paginator = Paginator(archived_purchases, 10)
    try:
        archived = archived_paginator.page(archived_page)
    except PageNotAnInteger:
        archived = archived_paginator.page(1)
    except EmptyPage:
        archived = archived_paginator.page(archived_paginator.num_pages)

    notifications = Notification.objects.filter(user=request.user, is_read = False)

    context = {
        'sales_agent': sales_agent,
        'tasks': tasks,  # تسک‌های انجام نشده
        'completed_tasks_page': completed_tasks_page,  # تسک‌های انجام شده (صفحه‌بندی شده)
        'unpaid': unpaid,
        'active': active,
        'archived': archived,
        'total_sales_this_month': total_sales_this_month,
        'notifications': notifications,
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
    paginator = Paginator(customers, 10)  # نمایش 10 مشتری در هر صفحه
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