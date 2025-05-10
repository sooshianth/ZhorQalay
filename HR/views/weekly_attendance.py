from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from ..EmployeeAttendanceModel import WeeklyAttendance, MonthlyAttendance
from ..forms.forms import DailyAttendanceForm
import csv
from django.http import HttpResponse
from datetime import timedelta
import datetime

@login_required
def daily_attendance_view(request):
    if request.method == 'POST':
        form = DailyAttendanceForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                date = form.cleaned_data['date']
                hours = form.cleaned_data['hours']
                description = form.cleaned_data['description']
                approved_by_user1 = form.cleaned_data['approved_by_user1']
                approved_by_user2 = form.cleaned_data['approved_by_user2']

                # تبدیل تاریخ گرگوری به فرمت ساده
                weekday_names = ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                day_of_week = weekday_names[date.weekday()]

                # محاسبه تاریخ شروع هفته (شنبه همان هفته)
                week_start_date = date - timedelta(days=(date.weekday() + 2) % 7)

                # ایجاد یا به‌روزرسانی رکورد حضور
                attendance, created = WeeklyAttendance.objects.update_or_create(
                    employee=request.user,
                    week_start_date=week_start_date,
                    defaults={
                        'approved_by_user1': approved_by_user1,
                        'approved_by_user2': approved_by_user2,
                        'user1_approved': False,
                        'user2_approved': False,
                        'approved_by_admin': False,
                        'description': description,
                        'day': day_of_week
                    }
                )
                
                # تنظیم ساعات کاری برای روز مربوطه
                weekday_map = {
                    0: 'saturday_hours',
                    1: 'sunday_hours',
                    2: 'monday_hours',
                    3: 'tuesday_hours',
                    4: 'wednesday_hours',
                    5: 'thursday_hours',
                    6: 'friday_hours'
                }
                # تنظیم مقدار ساعات برای روز مربوطه
                setattr(attendance, weekday_map[date.weekday()], hours)
                # اطمینان از اینکه سایر فیلدها مقدار پیش‌فرض 0 دارند
                for day in weekday_map.values():
                    if getattr(attendance, day) is None:
                        setattr(attendance, day, 0)
                # محاسبه مجموع ساعات
                attendance.calculate_total_hours()
                attendance.save()

                messages.success(request, f'ساعات کاری برای {day_of_week} با موفقیت ثبت شد!')
                return redirect('weekly_attendance_view')
                
            except Exception as e:
                messages.error(request, f'خطا در ثبت اطلاعات: {str(e)}')
        else:
            messages.error(request, 'لطفاً فرم را به‌درستی پر کنید.')
    else:
        form = DailyAttendanceForm(user=request.user)

    attendances = WeeklyAttendance.objects.filter(employee=request.user).order_by('-week_start_date')
    status = request.GET.get('status')
    if status == 'approved':
        attendances = attendances.filter(user1_approved=True, user2_approved=True, approved_by_admin=True)
    elif status == 'pending':
        attendances = attendances.exclude(user1_approved=True, user2_approved=True, approved_by_admin=True)

    q = request.GET.get('q')
    if q:
        attendances = attendances.filter(Q(description__icontains=q) | Q(day__icontains=q))
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if start_date:
        attendances = attendances.filter(week_start_date__gte=start_date)
    if end_date:
        attendances = attendances.filter(week_start_date__lte=end_date)

    # تبدیل تاریخ‌ها به فرمت ساده گرگوری
    formatted_attendances = []
    for attendance in attendances:
        formatted_date = attendance.week_start_date.strftime('%Y-%m-%d')
        formatted_attendances.append({
            'week_start_date': formatted_date,
            'day': attendance.day,
            'total_hours': attendance.total_hours,
            'description': attendance.description,
            'approved_by_admin': attendance.approved_by_admin,
            'user1_approved': attendance.user1_approved,
            'user2_approved': attendance.user2_approved,
            'is_fully_approved': attendance.is_fully_approved,
        })

    return render(request, 'weekly_attendance.html', {
        'form': form,
        'attendances': formatted_attendances,
        'status': status,
        'q': q
    })

@login_required
def download_attendance_report(request):
    attendances = WeeklyAttendance.objects.filter(employee=request.user).order_by('-week_start_date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['تاریخ شروع هفته', 'مجموع ساعات', 'توضیحات', 'تأیید ادمین', 'تأیید کاربر ۱', 'تأیید کاربر ۲'])
    for attendance in attendances:
        writer.writerow([
            attendance.week_start_date.strftime('%Y-%m-%d'),
            attendance.total_hours,
            attendance.description,
            '✅' if attendance.approved_by_admin else '❌',
            '✅' if attendance.user1_approved else '❌',
            '✅' if attendance.user2_approved else '❌',
        ])

    return response

@login_required
def pending_approvals_view(request):
    if request.user.is_superuser:
        pending_attendances = WeeklyAttendance.objects.filter(
            approved_by_admin=False
        ).order_by('-week_start_date')
    else:
        pending_attendances = WeeklyAttendance.objects.filter(
            (
                Q(approved_by_user1=request.user, user1_approved=False) |
                Q(approved_by_user2=request.user, user2_approved=False)
            )
        ).order_by('-week_start_date')

    return render(request, 'pending_approvals.html', {
        'pending_attendances': pending_attendances
    })

@login_required
def approve_attendance(request, attendance_id):
    attendance = get_object_or_404(WeeklyAttendance, id=attendance_id)

    if attendance.approved_by_user1 == request.user:
        attendance.user1_approved = True
        attendance.save()
        messages.success(request, "تأیید شما ثبت شد!")
    elif attendance.approved_by_user2 == request.user:
        attendance.user2_approved = True
        attendance.save()
        messages.success(request, "تأیید شما ثبت شد!")
    elif request.user.is_superuser:
        attendance.approved_by_admin = True
        attendance.save()
        messages.success(request, "تأیید ادمین ثبت شد!")
    else:
        messages.error(request, "شما مجاز به تأیید این رکورد نیستید.")
        return redirect('pending_approvals')

    if attendance.is_fully_approved:
        messages.success(request, "ساعات کاری با موفقیت تأیید شد!")

    return redirect('pending_approvals')

@login_required
def attendance_summary_view(request):
    week = request.GET.get('week')
    month = request.GET.get('month')
    weekly_qs = WeeklyAttendance.objects.filter(employee=request.user)
    monthly_qs = MonthlyAttendance.objects.filter(employee=request.user)

    if week:
        weekly_qs = weekly_qs.filter(week_start_date=week)
    if month:
        monthly_qs = monthly_qs.filter(month=month)

    weekly_summary = weekly_qs.values('week_start_date').annotate(total_hours=Sum('total_hours')).order_by('-week_start_date')
    monthly_summary = monthly_qs.order_by('-month')

    # محاسبه جمع و میانگین به صورت دستی
    total_weekly_hours = sum(item['total_hours'] for item in weekly_summary) if weekly_summary else 0
    total_monthly_hours = sum(item.total_hours for item in monthly_summary) if monthly_summary else 0
    avg_weekly_hours = total_weekly_hours / len(weekly_summary) if weekly_summary else 0

    # تبدیل تاریخ‌ها به فرمت ساده گرگوری
    formatted_weekly_summary = []
    for summary in weekly_summary:
        formatted_date = summary['week_start_date'].strftime('%Y-%m-%d')
        formatted_weekly_summary.append({
            'week_start_date': formatted_date,
            'total_hours': summary['total_hours']
        })

    return render(request, 'attendance_summary.html', {
        'weekly_summary': formatted_weekly_summary,
        'monthly_summary': monthly_summary,
        'selected_week': week,
        'selected_month': month,
        'total_weekly_hours': total_weekly_hours,
        'total_monthly_hours': total_monthly_hours,
        'avg_weekly_hours': round(avg_weekly_hours, 2),
    })