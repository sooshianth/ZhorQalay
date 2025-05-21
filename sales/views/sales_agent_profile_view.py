from core._models import Notification, Customer, Purchase
from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import logging
from core.decorators.decorators import role_required
logger = logging.getLogger(__name__)

@role_required('sales_agent', 'admin')
@login_required
def sales_agent_profile_view(request):
    if not hasattr(request.user, 'sales_agent'):
        messages.error(request, "شما مجاز به مشاهده این صفحه نیستید. لطفاً با حساب کارشناس فروش وارد شوید.")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent  

    # دریافت تمام تسک‌ها با استفاده از متدهای بهبود یافته
    task_filter = request.GET.get('task_filter', 'all')  # all, today, overdue
    task_search = request.GET.get('task_search', '')
    
    now = timezone.now()
    
    if task_filter == 'today':
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        pending_tasks = [
            task for task in sales_agent.get_all_undone_tasks()
            if start_of_day <= task.due_date <= end_of_day
        ]
    elif task_filter == 'overdue':
        pending_tasks = [
            task for task in sales_agent.get_all_undone_tasks()
            if task.due_date < now
        ]
    else:
        pending_tasks = sales_agent.get_all_undone_tasks()
    
    # جستجوی تسک‌ها
    if task_search:
        pending_tasks = [
            task for task in pending_tasks
            if task_search.lower() in task.description.lower()
        ]
    
    # مرتب‌سازی تسک‌ها بر اساس تاریخ سررسید
    pending_tasks = sorted(pending_tasks, key=lambda task: task.due_date)
        
    completed_tasks = sales_agent.get_tasks_by_status(status=True)


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

    # استفاده از متدهای بهبود یافته برای دریافت خریدها
    unpaid_purchases = sales_agent.get_all_unpaid_sales()
    active_purchases = sales_agent.get_all_active_sales()
    archived_purchases = sales_agent.get_all_archived_sales()
    
    # استفاده از متد جدید برای آمار فروش ماه جاری
    sales_stats = sales_agent.get_this_month_sales_stats()

    # Pagination برای خریدها
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

    # دریافت اعلان‌های خوانده نشده
    notifications = Notification.objects.filter(user=request.user, is_read=False)
    
    # استفاده از متد جدید برای بررسی ددلاین تسک‌ها و ایجاد اعلان
    new_notifications = sales_agent.check_task_deadlines()
    if new_notifications > 0:
        messages.info(request, f"{new_notifications} اعلان جدید در مورد تسک‌های نزدیک به سررسید ایجاد شد.")

    all_sales = sales_agent.get_this_month_sales_weight()/1000

    context = {
        'sales_agent': sales_agent,
        'tasks': tasks,  # تسک‌های انجام نشده
        'completed_tasks_page': completed_tasks_page,  # تسک‌های انجام شده (صفحه‌بندی شده)
        'unpaid': unpaid,
        'active': active,
        'archived': archived,
        'sales_stats': sales_stats,
        'all_sales': all_sales,
        'notifications': notifications,
        'target_achievement': round(sales_stats['target_achievement'], 1),
    }

    return render(request, 'sales_agent_profile.html', context)



@role_required('sales_agent', 'admin')
@login_required
def delete_unpaid_purchase(request, purchase_id):
    if not hasattr(request.user, 'sales_agent'):
        return HttpResponse("Unauthorized", status=403)
    
    sales_agent = request.user.sales_agent
    # Get the specific unpaid purchase that belongs to this sales agent
    purchase = get_object_or_404(Purchase, 
                               id=purchase_id,
                               customer__sales_agent=sales_agent,
                               state__in=['INITIATED', 'SMS_SENT'])
    
    try:
        purchase.delete()
        messages.success(request, "خرید با موفقیت حذف شد.")
    except Exception as e:
        logger.error(f"Error deleting purchase {purchase_id}: {str(e)}")
        messages.error(request, "خطا در حذف خرید. لطفاً مجدداً تلاش کنید.")
    
    return redirect('sales_agent_profile')