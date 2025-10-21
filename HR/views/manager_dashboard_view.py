"""
ویوهای داشبورد مدیریتی برای سیستم مرغک
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.contrib.auth.models import User
from HR.MorqkModel import MorqkTask, MonthlyMorqkSummary, TaskAssignment
from HR.EmployeeModel import Employee
import jdatetime


@login_required
def manager_dashboard(request):
    """
    داشبورد مدیریتی کامل برای superuser و مدیران
    """
    user = request.user
    
    # بررسی نقش کاربر
    is_manager = False
    is_superuser = user.is_superuser
    try:
        is_manager = user.employee.is_manager
    except:
        pass
    
    # اگر نه superuser و نه مدیر است، دسترسی نداره
    if not (is_superuser or is_manager):
        messages.error(request, 'شما به این صفحه دسترسی ندارید.')
        return redirect('morqk_dashboard')
    
    # دریافت همه تسک‌ها
    if is_superuser:
        # superuser همه تسک‌ها را می‌بیند
        all_tasks = MorqkTask.objects.all()
    else:
        # مدیر فقط تسک‌هایی که خودش ایجاد کرده را می‌بیند
        all_tasks = MorqkTask.objects.filter(created_by=user)
    
    all_tasks = all_tasks.select_related('assigned_to', 'created_by', 'approved_by').prefetch_related('assignments__employee').order_by('-created_at')
    
    # آمار وضعیت‌ها
    todo_count = all_tasks.filter(status='TODO').count()
    in_progress_count = all_tasks.filter(status='IN_PROGRESS').count()
    pending_count = all_tasks.filter(status='PENDING_APPROVAL').count()
    approved_count = all_tasks.filter(status='APPROVED').count()
    rejected_count = all_tasks.filter(status='REJECTED').count()
    
    # محاسبه مجموع مرغک‌های تایید شده در ماه جاری برای هر کارمند
    current_date = jdatetime.datetime.now()
    current_month = f"{current_date.year}-{current_date.month:02d}"
    
    # دریافت خلاصه ماهانه مرغک‌ها
    monthly_summaries = MonthlyMorqkSummary.objects.filter(
        month=current_month
    ).select_related('employee').order_by('-total_approved_morqk')
    
    context = {
        'is_superuser': is_superuser,
        'is_manager': is_manager,
        'all_tasks': all_tasks,
        'todo_count': todo_count,
        'in_progress_count': in_progress_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'monthly_summaries': monthly_summaries,
        'current_month': current_month,
        'current_month_display': f"{current_date.year}/{current_date.month:02d}",
    }
    
    return render(request, 'morqk/manager_dashboard.html', context)


@login_required
def manager_task_detail(request, task_id):
    """
    صفحه جزئیات تسک برای مدیران با قابلیت تغییر وضعیت
    """
    user = request.user
    task = get_object_or_404(MorqkTask, id=task_id)
    
    # بررسی نقش کاربر
    is_manager = False
    is_superuser = user.is_superuser
    try:
        is_manager = user.employee.is_manager
    except:
        pass
    
    # بررسی دسترسی
    if not (is_superuser or (is_manager and task.created_by == user)):
        messages.error(request, 'شما به این تسک دسترسی ندارید.')
        return redirect('manager_dashboard')
    
    # دریافت تخصیص‌ها (برای تسک‌های چندنفره)
    assignments = task.assignments.all().select_related('employee')
    
    context = {
        'task': task,
        'is_superuser': is_superuser,
        'is_manager': is_manager,
        'assignments': assignments,
        'can_edit': True,  # همیشه می‌تواند ویرایش کند (جز تسک‌های تایید شده)
    }
    
    return render(request, 'morqk/manager_task_detail.html', context)


@login_required
def manager_change_task_status(request, task_id):
    """
    تغییر وضعیت تسک توسط مدیر
    """
    if request.method != 'POST':
        return redirect('manager_dashboard')
    
    user = request.user
    task = get_object_or_404(MorqkTask, id=task_id)
    
    # بررسی نقش کاربر
    is_manager = False
    is_superuser = user.is_superuser
    try:
        is_manager = user.employee.is_manager
    except:
        pass
    
    # بررسی دسترسی
    if not (is_superuser or (is_manager and task.created_by == user)):
        messages.error(request, 'شما اجازه تغییر وضعیت این تسک را ندارید.')
        return redirect('manager_dashboard')
    
    new_status = request.POST.get('status')
    note = request.POST.get('note', '')
    
    valid_statuses = ['TODO', 'IN_PROGRESS', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED']
    
    if new_status not in valid_statuses:
        messages.error(request, 'وضعیت انتخاب شده معتبر نیست.')
        return redirect('manager_task_detail', task_id=task_id)
    
    old_status = task.status
    
    # تغییر وضعیت
    if new_status == 'APPROVED':
        task.approve(user, note)
        messages.success(request, f'تسک "{task.title}" تایید شد.')
        # به‌روزرسانی خلاصه ماهانه
        if task.assigned_to:
            MonthlyMorqkSummary.update_monthly_morqk(task.assigned_to, task.created_at)
        # برای تسک‌های چندنفره
        for assignment in task.assignments.all():
            MonthlyMorqkSummary.update_monthly_morqk(assignment.employee, task.created_at)
            
    elif new_status == 'REJECTED':
        task.reject(user, note)
        messages.warning(request, f'تسک "{task.title}" رد شد.')
        # به‌روزرسانی خلاصه ماهانه
        if task.assigned_to:
            MonthlyMorqkSummary.update_monthly_morqk(task.assigned_to, task.created_at)
        # برای تسک‌های چندنفره
        for assignment in task.assignments.all():
            MonthlyMorqkSummary.update_monthly_morqk(assignment.employee, task.created_at)
            
    else:
        # تغییر ساده وضعیت
        task.status = new_status
        if new_status == 'PENDING_APPROVAL' and not task.completed_at:
            task.completed_at = jdatetime.datetime.now()
        task.save()
        messages.success(request, f'وضعیت تسک به "{task.get_status_display()}" تغییر کرد.')
    
    return redirect('manager_task_detail', task_id=task_id)


@login_required
def manager_edit_task(request, task_id):
    """
    ویرایش تسک توسط مدیر
    """
    user = request.user
    task = get_object_or_404(MorqkTask, id=task_id)
    
    # بررسی نقش کاربر
    is_manager = False
    is_superuser = user.is_superuser
    try:
        is_manager = user.employee.is_manager
    except:
        pass
    
    # بررسی دسترسی
    if not (is_superuser or (is_manager and task.created_by == user)):
        messages.error(request, 'شما اجازه ویرایش این تسک را ندارید.')
        return redirect('manager_dashboard')
    
    # نمی‌توان تسک‌های تایید شده را ویرایش کرد
    if task.status == 'APPROVED':
        messages.error(request, 'نمی‌توان تسک‌های تایید شده را ویرایش کرد.')
        return redirect('manager_task_detail', task_id=task_id)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        morqk_value = request.POST.get('morqk_value')
        due_date_str = request.POST.get('due_date')
        
        # اعتبارسنجی
        if not all([title, morqk_value]):
            messages.error(request, 'لطفاً تمام فیلدهای الزامی را پر کنید.')
            return redirect('manager_edit_task', task_id=task_id)
        
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
            
            # اگر تسک تک‌نفره است
            if not task.is_multi_assigned:
                assigned_to_id = request.POST.get('assigned_to')
                if assigned_to_id:
                    old_assigned_to = task.assigned_to
                    assigned_to = User.objects.get(id=assigned_to_id)
                    task.assigned_to = assigned_to
                    
                    # اگر کارمند تغییر کرد، خلاصه ماهانه را به‌روزرسانی کن
                    if old_assigned_to and old_assigned_to != assigned_to:
                        MonthlyMorqkSummary.update_monthly_morqk(old_assigned_to, task.created_at)
                        MonthlyMorqkSummary.update_monthly_morqk(assigned_to, task.created_at)
            
            # به‌روزرسانی فیلدها
            task.title = title
            task.description = description
            task.morqk_value = morqk_value
            task.due_date = due_date
            task.save()
            
            messages.success(request, f'تسک "{title}" با موفقیت ویرایش شد.')
            return redirect('manager_task_detail', task_id=task_id)
            
        except User.DoesNotExist:
            messages.error(request, 'کارمند انتخاب شده یافت نشد.')
        except Exception as e:
            messages.error(request, f'خطا در ویرایش تسک: {str(e)}')
    
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
        'is_superuser': is_superuser,
        'is_manager': is_manager,
    }
    
    return render(request, 'morqk/manager_edit_task.html', context)


@login_required
def admin_overview_dashboard(request):
    """
    داشبورد مدیریتی برای ادمین - نمایش برنامه هفتگی و هدف ماهانه همه کارمندان
    """
    user = request.user
    
    # فقط ادمین می‌تواند به این صفحه دسترسی داشته باشد
    if not user.is_superuser:
        messages.error(request, 'شما به این صفحه دسترسی ندارید.')
        return redirect('morqk_dashboard')
    
    from ..EmployeeAttendanceModel import WeeklySchedule, MonthlyTarget
    
    # دریافت ماه جاری
    current_date = jdatetime.datetime.now()
    current_month = f"{current_date.year}-{current_date.month:02d}"
    
    # دریافت همه کارمندان (افرادی که Employee record دارند یا superuser هستند)
    all_employees = User.objects.filter(
        Q(employee__isnull=False) | Q(is_superuser=True)
    ).distinct().order_by('first_name', 'username')
    
    # آماده‌سازی داده‌ها برای هر کارمند
    employees_data = []
    
    for employee in all_employees:
        # برنامه هفتگی
        schedules = WeeklySchedule.objects.filter(
            employee=employee,
            is_active=True
        ).order_by('day_of_week')
        
        # محاسبه مجموع ساعات هفتگی
        total_weekly_hours = sum([s.duration_hours for s in schedules])
        
        # هدف ماهانه برای ماه جاری
        monthly_target = MonthlyTarget.objects.filter(
            employee=employee,
            month=current_month
        ).first()
        
        # خلاصه مرغک ماهانه
        morqk_summary = MonthlyMorqkSummary.objects.filter(
            employee=employee,
            month=current_month
        ).first()
        
        employees_data.append({
            'employee': employee,
            'full_name': f"{employee.first_name} {employee.last_name}" if employee.first_name else employee.username,
            'schedules': schedules,
            'total_weekly_hours': total_weekly_hours,
            'monthly_target': monthly_target,
            'morqk_summary': morqk_summary,
        })
    
    context = {
        'employees_data': employees_data,
        'current_month': current_month,
        'current_month_display': f"{current_date.year}/{current_date.month:02d}",
        'current_date': current_date,
    }
    
    return render(request, 'morqk/admin_overview_dashboard.html', context)
