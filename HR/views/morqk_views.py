from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import JsonResponse
from core.decorators.decorators import role_required
from HR.MorqkModel import MorqkTask, MonthlyMorqkSummary, TaskAssignment
from HR.EmployeeModel import Employee
from django.contrib.auth.models import User
import jdatetime


@login_required
def morqk_dashboard(request):
    """
    داشبورد اصلی مرغک
    نمایش وظایف برای کارمند و مدیر
    """
    user = request.user
    
    # بررسی نقش کاربر
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    # وظایف کارمند (تک‌نفره)
    my_tasks = MorqkTask.objects.filter(
        Q(assigned_to=user) | Q(assignments__employee=user)
    ).distinct()
    
    # آمار وظایف
    todo_tasks = my_tasks.filter(status='TODO')
    in_progress_tasks = my_tasks.filter(status='IN_PROGRESS')
    pending_tasks = my_tasks.filter(status='PENDING_APPROVAL')
    approved_tasks = my_tasks.filter(status='APPROVED')
    rejected_tasks = my_tasks.filter(status='REJECTED')
    
    # محاسبه مجموع مرغک ماه جاری
    current_date = jdatetime.datetime.now()
    current_month = f"{current_date.year}-{current_date.month:02d}"
    
    monthly_summary = MonthlyMorqkSummary.objects.filter(
        employee=user,
        month=current_month
    ).first()
    
    # اگر مدیر است، وظایف در انتظار تایید و وظایف ایجاد شده توسط او را نمایش بده
    pending_approval_tasks = []
    created_tasks = []
    if is_manager:
        pending_approval_tasks = MorqkTask.objects.filter(
            status='PENDING_APPROVAL'
        ).select_related('assigned_to', 'created_by').prefetch_related('assignments__employee')
        
        # وظایف ایجاد شده توسط مدیر
        created_tasks = MorqkTask.objects.filter(
            created_by=user
        ).select_related('assigned_to', 'created_by').prefetch_related('assignments__employee')
    
    context = {
        'is_manager': is_manager,
        'my_tasks': my_tasks,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'pending_tasks': pending_tasks,
        'approved_tasks': approved_tasks,
        'rejected_tasks': rejected_tasks,
        'monthly_summary': monthly_summary,
        'pending_approval_tasks': pending_approval_tasks,
        'created_tasks': created_tasks,
    }
    
    return render(request, 'morqk/dashboard.html', context)


@login_required
def create_morqk_task(request):
    """
    ایجاد وظیفه جدید (فقط برای مدیران)
    """
    user = request.user
    
    # بررسی نقش مدیر
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    if not is_manager:
        messages.error(request, 'شما اجازه ایجاد وظیفه ندارید.')
        return redirect('morqk_dashboard')
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        morqk_value = request.POST.get('morqk_value')
        due_date_str = request.POST.get('due_date')
        is_multi = request.POST.get('is_multi_assigned') == 'true'
        
        # اعتبارسنجی
        if not all([title, morqk_value]):
            messages.error(request, 'لطفاً تمام فیلدهای الزامی را پر کنید.')
            return redirect('create_morqk_task')
        
        try:
            # تبدیل تاریخ
            due_date = None
            if due_date_str:
                try:
                    parts = due_date_str.split('-')
                    if len(parts) == 3:
                        due_date = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                except:
                    pass
            
            if is_multi:
                # واگذاری چندنفره
                import json
                assignments_data = json.loads(request.POST.get('assignments', '[]'))
                
                if not assignments_data:
                    messages.error(request, 'لطفاً حداقل یک کارمند انتخاب کنید.')
                    return redirect('create_morqk_task')
                
                # بررسی مجموع درصدها
                total_percentage = sum(int(a.get('percentage', 0)) for a in assignments_data)
                if total_percentage != 100:
                    messages.error(request, f'مجموع درصدها باید 100 باشد. مجموع فعلی: {total_percentage}')
                    return redirect('create_morqk_task')
                
                # ایجاد وظیفه چندنفره
                task = MorqkTask.objects.create(
                    title=title,
                    description=description,
                    is_multi_assigned=True,
                    assigned_to=None,
                    created_by=user,
                    morqk_value=morqk_value,
                    due_date=due_date,
                    status='TODO'
                )
                
                # ایجاد تخصیص‌ها
                for assignment in assignments_data:
                    emp = User.objects.get(id=assignment['employee_id'])
                    TaskAssignment.objects.create(
                        task=task,
                        employee=emp,
                        percentage=int(assignment['percentage'])
                    )
                
                messages.success(request, f'وظیفه "{title}" با {len(assignments_data)} کارمند ایجاد شد.')
                
            else:
                # واگذاری تک‌نفره
                assigned_to_id = request.POST.get('assigned_to')
                if not assigned_to_id:
                    messages.error(request, 'لطفاً یک کارمند انتخاب کنید.')
                    return redirect('create_morqk_task')
                
                assigned_to = User.objects.get(id=assigned_to_id)
                
                task = MorqkTask.objects.create(
                    title=title,
                    description=description,
                    is_multi_assigned=False,
                    assigned_to=assigned_to,
                    created_by=user,
                    morqk_value=morqk_value,
                    due_date=due_date,
                    status='TODO'
                )
                
                messages.success(request, f'وظیفه "{title}" با موفقیت ایجاد شد.')
            
            return redirect('morqk_dashboard')
            
        except User.DoesNotExist:
            messages.error(request, 'کارمند انتخاب شده یافت نشد.')
        except Exception as e:
            messages.error(request, f'خطا در ایجاد وظیفه: {str(e)}')
    
    # دریافت لیست کارمندان
    employees = User.objects.filter(
        Q(employee__isnull=False) | Q(is_superuser=True)
    ).distinct()
    
    # مقادیر مرغک
    morqk_choices = [0.5, 1, 2, 3, 5, 8, 13, 20, 40]
    
    context = {
        'employees': employees,
        'morqk_choices': morqk_choices,
    }
    
    return render(request, 'morqk/create_task.html', context)


@login_required
def task_detail(request, task_id):
    """
    نمایش جزئیات وظیفه
    """
    task = get_object_or_404(MorqkTask, id=task_id)
    user = request.user
    
    # بررسی دسترسی
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    can_edit = (task.assigned_to == user and task.status in ['TODO', 'IN_PROGRESS', 'REJECTED'])
    can_approve = is_manager and task.status == 'PENDING_APPROVAL'
    
    context = {
        'task': task,
        'can_edit': can_edit,
        'can_approve': can_approve,
        'is_manager': is_manager,
    }
    
    return render(request, 'morqk/task_detail.html', context)


@login_required
def update_task_status(request, task_id):
    """
    به‌روزرسانی وضعیت وظیفه
    """
    if request.method != 'POST':
        return redirect('morqk_dashboard')
    
    task = get_object_or_404(MorqkTask, id=task_id)
    user = request.user
    
    # بررسی دسترسی
    if task.assigned_to != user:
        messages.error(request, 'شما اجازه ویرایش این وظیفه را ندارید.')
        return redirect('morqk_dashboard')
    
    action = request.POST.get('action')
    
    if action == 'start':
        if task.status == 'TODO':
            task.status = 'IN_PROGRESS'
            task.save()
            messages.success(request, 'وظیفه به حالت "در حال انجام" تغییر کرد.')
    
    elif action == 'complete':
        if task.status in ['TODO', 'IN_PROGRESS', 'REJECTED']:
            completion_note = request.POST.get('completion_note', '')
            task.mark_as_completed(completion_note)
            messages.success(request, 'وظیفه تکمیل شد و برای تایید ارسال شد.')
            
            # به‌روزرسانی خلاصه ماهانه
            MonthlyMorqkSummary.update_monthly_morqk(user, task.created_at)
    
    elif action == 'reopen':
        if task.status == 'REJECTED':
            task.status = 'TODO'
            task.rejection_note = ''
            task.save()
            messages.success(request, 'وظیفه مجدداً باز شد.')
    
    return redirect('task_detail', task_id=task_id)


@login_required
def approve_task(request, task_id):
    """
    تایید یا رد وظیفه توسط مدیر
    """
    if request.method != 'POST':
        return redirect('morqk_dashboard')
    
    task = get_object_or_404(MorqkTask, id=task_id)
    user = request.user
    
    # بررسی نقش مدیر
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    if not is_manager:
        messages.error(request, 'شما اجازه تایید وظیفه ندارید.')
        return redirect('morqk_dashboard')
    
    if task.status != 'PENDING_APPROVAL':
        messages.error(request, 'این وظیفه در وضعیت مناسب برای تایید نیست.')
        return redirect('morqk_dashboard')
    
    action = request.POST.get('action')
    note = request.POST.get('note', '')
    
    if action == 'approve':
        task.approve(user, note)
        messages.success(request, f'وظیفه "{task.title}" تایید شد.')
        
        # به‌روزرسانی خلاصه ماهانه
        MonthlyMorqkSummary.update_monthly_morqk(task.assigned_to, task.created_at)
    
    elif action == 'reject':
        task.reject(user, note)
        messages.warning(request, f'وظیفه "{task.title}" رد شد.')
        
        # به‌روزرسانی خلاصه ماهانه
        MonthlyMorqkSummary.update_monthly_morqk(task.assigned_to, task.created_at)
    
    return redirect('morqk_dashboard')


@login_required
def monthly_morqk_report(request):
    """
    گزارش ماهانه مرغک‌ها
    """
    user = request.user
    
    # بررسی نقش مدیر
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    # دریافت ماه از پارامترها
    selected_month = request.GET.get('month')
    if not selected_month:
        current_date = jdatetime.datetime.now()
        selected_month = f"{current_date.year}-{current_date.month:02d}"
    
    if is_manager:
        # نمایش همه کارمندان
        summaries = MonthlyMorqkSummary.objects.filter(
            month=selected_month
        ).select_related('employee')
    else:
        # فقط خودش
        summaries = MonthlyMorqkSummary.objects.filter(
            employee=user,
            month=selected_month
        )
    
    # لیست ماه‌ها برای انتخاب
    available_months = MonthlyMorqkSummary.objects.values_list(
        'month', flat=True
    ).distinct().order_by('-month')
    
    context = {
        'summaries': summaries,
        'selected_month': selected_month,
        'available_months': available_months,
        'is_manager': is_manager,
    }
    
    return render(request, 'morqk/monthly_report.html', context)


@login_required
def delete_task(request, task_id):
    """
    حذف وظیفه (فقط توسط مدیر یا سازنده)
    """
    if request.method != 'POST':
        return redirect('morqk_dashboard')
    
    task = get_object_or_404(MorqkTask, id=task_id)
    user = request.user
    
    # بررسی نقش مدیر
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    # فقط مدیر یا سازنده می‌توانند حذف کنند
    if not (is_manager or task.created_by == user):
        messages.error(request, 'شما اجازه حذف این وظیفه را ندارید.')
        return redirect('morqk_dashboard')
    
    # نمی‌توان وظایف تایید شده را حذف کرد
    if task.status == 'APPROVED':
        messages.error(request, 'نمی‌توان وظایف تایید شده را حذف کرد.')
        return redirect('morqk_dashboard')
    
    title = task.title
    assigned_to = task.assigned_to
    task.delete()
    
    # به‌روزرسانی خلاصه ماهانه
    current_date = jdatetime.datetime.now()
    MonthlyMorqkSummary.update_monthly_morqk(assigned_to, current_date)
    
    messages.success(request, f'وظیفه "{title}" حذف شد.')
    return redirect('morqk_dashboard')


@login_required
def edit_task(request, task_id):
    """
    ویرایش وظیفه (فقط توسط مدیر یا سازنده)
    """
    task = get_object_or_404(MorqkTask, id=task_id)
    user = request.user
    
    # بررسی نقش مدیر
    is_manager = False
    try:
        is_manager = user.employee.is_manager or user.is_superuser
    except:
        is_manager = user.is_superuser
    
    # فقط مدیر یا سازنده می‌توانند ویرایش کنند
    if not (is_manager or task.created_by == user):
        messages.error(request, 'شما اجازه ویرایش این وظیفه را ندارید.')
        return redirect('morqk_dashboard')
    
    # نمی‌توان وظایف تایید شده را ویرایش کرد
    if task.status == 'APPROVED':
        messages.error(request, 'نمی‌توان وظایف تایید شده را ویرایش کرد.')
        return redirect('task_detail', task_id=task_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        assigned_to_id = request.POST.get('assigned_to')
        morqk_value = request.POST.get('morqk_value')
        due_date_str = request.POST.get('due_date')
        
        # اعتبارسنجی
        if not all([title, assigned_to_id, morqk_value]):
            messages.error(request, 'لطفاً تمام فیلدهای الزامی را پر کنید.')
            return redirect('edit_task', task_id=task_id)
        
        try:
            assigned_to = User.objects.get(id=assigned_to_id)
            
            # تبدیل تاریخ
            due_date = None
            if due_date_str:
                try:
                    parts = due_date_str.split('-')
                    if len(parts) == 3:
                        due_date = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
                except:
                    pass
            
            # به‌روزرسانی وظیفه
            old_assigned_to = task.assigned_to
            task.title = title
            task.description = description
            task.assigned_to = assigned_to
            task.morqk_value = morqk_value
            task.due_date = due_date
            task.save()
            
            # اگر کارمند تغییر کرده، خلاصه ماهانه هر دو را به‌روزرسانی کن
            if old_assigned_to != assigned_to:
                MonthlyMorqkSummary.update_monthly_morqk(old_assigned_to, task.created_at)
                MonthlyMorqkSummary.update_monthly_morqk(assigned_to, task.created_at)
            else:
                MonthlyMorqkSummary.update_monthly_morqk(assigned_to, task.created_at)
            
            messages.success(request, f'وظیفه "{title}" با موفقیت ویرایش شد.')
            return redirect('task_detail', task_id=task_id)
            
        except User.DoesNotExist:
            messages.error(request, 'کارمند انتخاب شده یافت نشد.')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش وظیفه: {str(e)}')
    
    # دریافت لیست کارمندان
    employees = User.objects.filter(
        Q(employee__isnull=False) | Q(is_superuser=True)
    ).distinct()
    
    # مقادیر مرغک
    morqk_choices = [0.5, 1, 2, 3, 5, 8, 13, 20, 40]
    
    context = {
        'task': task,
        'employees': employees,
        'morqk_choices': morqk_choices,
        'is_manager': is_manager,
    }
    
    return render(request, 'morqk/edit_task.html', context)

