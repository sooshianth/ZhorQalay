from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from ..EmployeeAttendanceModel import MonthlyTarget, WeeklySchedule, MonthlyAttendance
from core.decorators.decorators import role_required
import jdatetime
from django.http import JsonResponse


@role_required('employee', 'admin')
@login_required
def monthly_target_view(request):
    """نمایش و مدیریت اهداف ماهانه"""
    
    # دریافت ماه فیلتر (اگر مشخص شده باشد)
    filter_month = request.GET.get('month')
    
    # دریافت تمام اهداف کاربر
    targets = MonthlyTarget.objects.filter(employee=request.user).order_by('-month')
    
    if filter_month:
        targets = targets.filter(month=filter_month)
    
    # فرمت کردن داده‌ها برای نمایش
    formatted_targets = []
    for target in targets:
        year, month = target.month.split('-')
        jalali_month = f"{year}/{month}"
        
        formatted_targets.append({
            'id': target.id,
            'month': jalali_month,
            'month_raw': target.month,
            'target_hours': target.target_hours,
            'achieved_hours': target.achieved_hours,
            'remaining_hours': target.remaining_hours,
            'achievement_percentage': target.achievement_percentage,
            'is_achieved': target.is_achieved,
            'status': target.status,
            'status_color': target.status_color,
            'description': target.description,
            'created_at': target.created_at,
        })
    
    # ماه جاری شمسی
    current_jalali = jdatetime.date.today()
    current_month = f"{current_jalali.year}-{current_jalali.month:02d}"
    
    # بررسی اینکه آیا هدف برای ماه جاری وجود دارد
    current_month_target = MonthlyTarget.objects.filter(
        employee=request.user,
        month=current_month
    ).first()
    
    return render(request, 'monthly_target.html', {
        'targets': formatted_targets,
        'current_month': f"{current_jalali.year}/{current_jalali.month:02d}",
        'current_month_target': current_month_target,
        'filter_month': filter_month,
    })


@role_required('employee', 'admin')
@login_required
def create_monthly_target(request):
    """ایجاد هدف ماهانه جدید"""
    
    if request.method == 'POST':
        try:
            month = request.POST.get('month')  # فرمت: YYYY/MM
            target_hours = request.POST.get('target_hours')
            description = request.POST.get('description', '')
            
            # تبدیل فرمت ماه از YYYY/MM به YYYY-MM
            if '/' in month:
                month = month.replace('/', '-')
            
            # بررسی اینکه آیا هدف برای این ماه وجود دارد
            existing = MonthlyTarget.objects.filter(
                employee=request.user,
                month=month
            ).first()
            
            if existing:
                messages.error(request, 'هدف برای این ماه قبلاً ایجاد شده است. لطفاً از گزینه ویرایش استفاده کنید.')
                return redirect('monthly_target_view')
            
            # ایجاد هدف جدید
            MonthlyTarget.objects.create(
                employee=request.user,
                month=month,
                target_hours=target_hours,
                description=description
            )
            
            messages.success(request, 'هدف ماهانه با موفقیت ایجاد شد!')
            return redirect('monthly_target_view')
            
        except Exception as e:
            messages.error(request, f'خطا در ایجاد هدف: {str(e)}')
            return redirect('monthly_target_view')
    
    # برای GET request، نمایش فرم
    current_jalali = jdatetime.date.today()
    current_month = f"{current_jalali.year}/{current_jalali.month:02d}"
    
    return render(request, 'create_monthly_target.html', {
        'current_month': current_month,
    })


@role_required('employee', 'admin')
@login_required
def edit_monthly_target(request, target_id):
    """ویرایش هدف ماهانه"""
    
    target = get_object_or_404(MonthlyTarget, id=target_id, employee=request.user)
    
    if request.method == 'POST':
        try:
            target_hours = request.POST.get('target_hours')
            description = request.POST.get('description', '')
            
            target.target_hours = target_hours
            target.description = description
            target.save()
            
            messages.success(request, 'هدف ماهانه با موفقیت ویرایش شد!')
            return redirect('monthly_target_view')
            
        except Exception as e:
            messages.error(request, f'خطا در ویرایش هدف: {str(e)}')
            return redirect('monthly_target_view')
    
    # تبدیل ماه به فرمت نمایشی
    year, month = target.month.split('-')
    jalali_month = f"{year}/{month}"
    
    return render(request, 'edit_monthly_target.html', {
        'target': target,
        'jalali_month': jalali_month,
    })


@role_required('employee', 'admin')
@login_required
def delete_monthly_target(request, target_id):
    """حذف هدف ماهانه"""
    
    target = get_object_or_404(MonthlyTarget, id=target_id, employee=request.user)
    
    if request.method == 'POST':
        target.delete()
        messages.success(request, 'هدف ماهانه با موفقیت حذف شد!')
        return redirect('monthly_target_view')
    
    return render(request, 'confirm_delete_target.html', {'target': target})


@role_required('employee', 'admin')
@login_required
def weekly_schedule_view(request):
    """نمایش و مدیریت برنامه هفتگی"""
    
    # دریافت برنامه هفتگی کاربر
    schedules = WeeklySchedule.objects.filter(employee=request.user).order_by('day_of_week')
    
    # فرمت کردن داده‌ها برای نمایش
    formatted_schedules = []
    for schedule in schedules:
        formatted_schedules.append({
            'id': schedule.id,
            'day_of_week': schedule.get_day_of_week_display(),
            'day_of_week_en': schedule.day_of_week,
            'start_time': schedule.start_time.strftime('%H:%M'),
            'end_time': schedule.end_time.strftime('%H:%M'),
            'duration_hours': schedule.duration_hours,
            'is_active': schedule.is_active,
            'description': schedule.description,
        })
    
    # لیست روزهای هفته
    days_of_week = [
        ('Saturday', 'شنبه'),
        ('Sunday', 'یکشنبه'),
        ('Monday', 'دوشنبه'),
        ('Tuesday', 'سه‌شنبه'),
        ('Wednesday', 'چهارشنبه'),
        ('Thursday', 'پنج‌شنبه'),
        ('Friday', 'جمعه'),
    ]
    
    return render(request, 'weekly_schedule.html', {
        'schedules': formatted_schedules,
        'days_of_week': days_of_week,
    })


@role_required('employee', 'admin')
@login_required
def create_weekly_schedule(request):
    """ایجاد برنامه هفتگی جدید"""
    
    if request.method == 'POST':
        try:
            day_of_week = request.POST.get('day_of_week')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            description = request.POST.get('description', '')
            is_active = request.POST.get('is_active') == 'on'
            
            # بررسی اینکه آیا برنامه برای این روز وجود دارد
            existing = WeeklySchedule.objects.filter(
                employee=request.user,
                day_of_week=day_of_week
            ).first()
            
            if existing:
                messages.error(request, 'برنامه برای این روز قبلاً ایجاد شده است. لطفاً از گزینه ویرایش استفاده کنید.')
                return redirect('weekly_schedule_view')
            
            # ایجاد برنامه جدید
            WeeklySchedule.objects.create(
                employee=request.user,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                description=description,
                is_active=is_active
            )
            
            messages.success(request, 'برنامه هفتگی با موفقیت ایجاد شد!')
            return redirect('weekly_schedule_view')
            
        except Exception as e:
            messages.error(request, f'خطا در ایجاد برنامه: {str(e)}')
            return redirect('weekly_schedule_view')
    
    # لیست روزهای هفته
    days_of_week = [
        ('Saturday', 'شنبه'),
        ('Sunday', 'یکشنبه'),
        ('Monday', 'دوشنبه'),
        ('Tuesday', 'سه‌شنبه'),
        ('Wednesday', 'چهارشنبه'),
        ('Thursday', 'پنج‌شنبه'),
        ('Friday', 'جمعه'),
    ]
    
    return render(request, 'create_weekly_schedule.html', {
        'days_of_week': days_of_week,
    })


@role_required('employee', 'admin')
@login_required
def edit_weekly_schedule(request, schedule_id):
    """ویرایش برنامه هفتگی"""
    
    schedule = get_object_or_404(WeeklySchedule, id=schedule_id, employee=request.user)
    
    if request.method == 'POST':
        try:
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            description = request.POST.get('description', '')
            is_active = request.POST.get('is_active') == 'on'
            
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.description = description
            schedule.is_active = is_active
            schedule.save()
            
            messages.success(request, 'برنامه هفتگی با موفقیت ویرایش شد!')
            return redirect('weekly_schedule_view')
            
        except Exception as e:
            messages.error(request, f'خطا در ویرایش برنامه: {str(e)}')
            return redirect('weekly_schedule_view')
    
    return render(request, 'edit_weekly_schedule.html', {
        'schedule': schedule,
    })


@role_required('employee', 'admin')
@login_required
def delete_weekly_schedule(request, schedule_id):
    """حذف برنامه هفتگی"""
    
    schedule = get_object_or_404(WeeklySchedule, id=schedule_id, employee=request.user)
    
    if request.method == 'POST':
        schedule.delete()
        messages.success(request, 'برنامه هفتگی با موفقیت حذف شد!')
        return redirect('weekly_schedule_view')
    
    return render(request, 'confirm_delete_schedule.html', {'schedule': schedule})


@role_required('employee', 'admin')
@login_required
def toggle_schedule_status(request, schedule_id):
    """فعال/غیرفعال کردن برنامه"""
    
    schedule = get_object_or_404(WeeklySchedule, id=schedule_id, employee=request.user)
    
    schedule.is_active = not schedule.is_active
    schedule.save()
    
    status = 'فعال' if schedule.is_active else 'غیرفعال'
    messages.success(request, f'برنامه با موفقیت {status} شد!')
    
    return redirect('weekly_schedule_view')

