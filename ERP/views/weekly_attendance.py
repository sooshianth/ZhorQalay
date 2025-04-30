from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from core._models import WeeklyAttendance, MonthlyAttendance
from core.forms.forms import WeeklyAttendanceForm, DailyAttendanceForm
import csv
from django.http import HttpResponse
from datetime import datetime, timedelta
import jdatetime

from django.utils.timezone import datetime
import jdatetime

@login_required
def daily_attendance_view(request):
    if request.method == 'POST':
        form = DailyAttendanceForm(request.POST)
        if form.is_valid():
            date = form.cleaned_data['date']
            hours = form.cleaned_data['hours']
            description = form.cleaned_data['description']
            approved_by_user1 = form.cleaned_data['approved_by_user1']
            approved_by_user2 = form.cleaned_data['approved_by_user2']

            # استخراج روز هفته
            weekdays = ['یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه']
            day_of_week = weekdays[date.weekday()]  # استخراج نام روز هفته

            # ثبت ساعات کاری برای روز خاص
            attendance, created = WeeklyAttendance.objects.get_or_create(
                employee=request.user,
                week_start_date=date - timedelta(days=date.weekday()),  # تاریخ شروع هفته
            )
            setattr(attendance, f"{day_of_week.lower()}_hours", hours)  # تنظیم ساعات برای روز خاص
            attendance.day = day_of_week  # ذخیره روز هفته
            attendance.description = description
            attendance.approved_by_user1 = approved_by_user1
            attendance.approved_by_user2 = approved_by_user2
            attendance.save()

            return JsonResponse({'success': True, 'message': f'ساعات کاری برای {day_of_week} با موفقیت ثبت شد!'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = DailyAttendanceForm()

    attendances = WeeklyAttendance.objects.filter(employee=request.user).order_by('-week_start_date')
    return render(request, 'weekly_attendance.html', {'form': form, 'attendances': attendances})

@login_required
def download_attendance_report(request):
    # دانلود گزارش به‌صورت CSV
    attendances = WeeklyAttendance.objects.filter(employee=request.user).order_by('-week_start_date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['تاریخ شروع هفته', 'مجموع ساعات', 'توضیحات', 'تأیید ادمین', 'تأیید کاربر ۱', 'تأیید کاربر ۲'])
    for attendance in attendances:
        writer.writerow([
            attendance.week_start_date,
            attendance.total_hours,
            attendance.description,
            '✅' if attendance.approved_by_admin else '❌',
            '✅' if attendance.approved_by_user1 else '❌',
            '✅' if attendance.approved_by_user2 else '❌',
        ])

    return response

@login_required
def pending_approvals_view(request):
    pending_attendances = WeeklyAttendance.objects.filter(
        Q(approved_by_user1=request.user, user1_approved=False) |
        Q(approved_by_user2=request.user, user2_approved=False) |
        Q(approved_by_admin=False, employee=request.user),
    ).order_by('-week_start_date')

    return render(request, 'pending_approvals.html', {
        'pending_attendances': pending_attendances
    })

@login_required
def approve_attendance(request, attendance_id):
    attendance = get_object_or_404(WeeklyAttendance, id=attendance_id)

    if attendance.approved_by_user1 == request.user:
        attendance.user1_approved = True
    elif attendance.approved_by_user2 == request.user:
        attendance.user2_approved = True
    elif request.user.is_superuser:
        attendance.approved_by_admin = True

    attendance.save()

    if attendance.is_fully_approved():
        # اگر همه تاییدها انجام شده باشد، پیام موفقیت ارسال شود
        return JsonResponse({'success': True, 'message': 'ساعات کاری با موفقیت تایید شد!'})
    else:
        return JsonResponse({'success': True, 'message': 'تایید شما ثبت شد!'})

from django.db.models import Sum

@login_required
def attendance_summary_view(request):
    # جمع ساعات هفتگی
    weekly_summary = WeeklyAttendance.objects.filter(employee=request.user).values(
        'week_start_date'
    ).annotate(total_hours=Sum('total_hours')).order_by('-week_start_date')

    # جمع ساعات ماهانه
    monthly_summary = MonthlyAttendance.objects.filter(employee=request.user).order_by('-month')

    return render(request, 'attendance_summary.html', {
        'weekly_summary': weekly_summary,
        'monthly_summary': monthly_summary,
    })