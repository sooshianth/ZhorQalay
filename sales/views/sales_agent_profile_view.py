from core._models import Notification, Customer
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
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
    task_filter = request.GET.get('task_filter', 'all')  # all, today, overdue
    if task_filter == 'today':
        pending_tasks = [task for task in all_tasks if not task.status and task.due_date.date() == timezone.now().date()]
    elif task_filter == 'overdue':
        pending_tasks = [task for task in all_tasks if not task.status and task.due_date < timezone.now()]
    else:
        pending_tasks = [task for task in all_tasks if not task.status]
    completed_tasks = [task for task in all_tasks if task.status]

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

    weekly_trend = sales_agent.get_weekly_sales_trend()
    top_customers = sales_agent.get_top_customers()

    sales_agent.check_task_deadlines()

    context = {
        'sales_agent': sales_agent,
        'tasks': tasks,  # تسک‌های انجام نشده
        'completed_tasks_page': completed_tasks_page,  # تسک‌های انجام شده (صفحه‌بندی شده)
        'unpaid': unpaid,
        'active': active,
        'archived': archived,
        'weekly_trend': weekly_trend,
        'top_customers': top_customers,
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
    sort_by = request.GET.get('sort', 'name')
    order = request.GET.get('order', 'asc')
    city_filter = request.GET.get('city', '')
    activity_filter = request.GET.get('activity', '')
    purchase_filter = request.GET.get('purchase', '')  # مثلاً: has_purchase, no_purchase

    customers = sales_agent.get_all_customers()

    city_filter = request.GET.getlist('city', [])
    activity_filter = request.GET.getlist('activity', [])
    min_purchases = request.GET.get('min_purchases', 0)
    last_purchase_days = request.GET.get('last_purchase_days', 0)
    
    # ساخت کوئری‌ست پایه
    customers = sales_agent.get_all_customers()
    
    # ساخت Q objects برای فیلترها
    q_objects = Q()
    
    # فیلتر شهرها
    if city_filter:
        q_objects &= Q(city__in=city_filter)
    
    # فیلتر حوزه فعالیت
    if activity_filter:
        q_objects &= Q(field_of_activity__in=activity_filter)
    
    # فیلتر حداقل تعداد خریدها
    if min_purchases:
        customers = customers.annotate(
            total_purchases=Count('purchases_made')
        ).filter(total_purchases__gte=int(min_purchases))
    
    # فیلتر آخرین خرید در X روز گذشته
    if last_purchase_days:
        date_threshold = timezone.now() - timedelta(days=int(last_purchase_days))
        customers = customers.filter(
            purchases_made__created_at__gte=date_threshold
        ).distinct()
    
    # اعمال فیلترهای ترکیبی
    customers = customers.filter(q_objects)
    
    # مرتب‌سازی پیشرفته
    SORT_MAP = {
        'name_asc': 'name',
        'name_desc': '-name',
        'purchases_asc': 'total_purchases',
        'purchases_desc': '-total_purchases',
        'last_purchase_asc': 'last_purchase_date',
        'last_purchase_desc': '-last_purchase_date'
    }
    
    sort_key = request.GET.get('sort', 'name_asc')
    sort_field = SORT_MAP.get(sort_key, 'name')


    # تعداد خریدهای هر مشتری این ماه
    from django.db.models import Count
    customers = customers.annotate(purchase_count=Count('purchases_made', filter=Q(purchases_made__created_at__month=timezone.now().month)))

    # Pagination
    paginator = Paginator(customers, 10)
    page = request.GET.get('page', 1)
    try:
        customers_page = paginator.page(page)
    except PageNotAnInteger:
        customers_page = paginator.page(1)
    except EmptyPage:
        customers_page = paginator.page(paginator.num_pages)

    context = {
        'customers': customers_page,
        'search_query': search_query,
        'sort_by': sort_by,
        'order': order,
        'city_filter': city_filter,
        'activity_filter': activity_filter,
        'purchase_filter': purchase_filter,
    }
    return render(request, 'customer_list.html', context)

from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
import pandas as pd
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

@login_required
def export_customers_to_excel(request):
    if not hasattr(request.user, 'sales_agent'):
        logger.warning(f"Unauthorized access attempt by user {request.user.username}")
        return redirect('sales_agent_login')

    try:
        sales_agent = request.user.sales_agent
        customers = sales_agent.get_all_customers().values('name', 'phone_number', 'city', 'field_of_activity')
        
        if not customers:
            return HttpResponse("هیچ مشتری‌ای برای دانلود وجود ندارد.", content_type='text/plain')

        df = pd.DataFrame(list(customers))
        df.columns = ['نام', 'شماره موبایل', 'شهر', 'حیطه فعالیت']
        
        buffer = BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="customer_list.xlsx"'
        return response
    except Exception as e:
        logger.error(f"Error exporting customers to Excel: {str(e)}")
        return HttpResponse(f"خطا در تولید فایل اکسل: {str(e)}", status=500)