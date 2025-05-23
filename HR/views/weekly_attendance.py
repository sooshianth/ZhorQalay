from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from ..EmployeeAttendanceModel import WeeklyAttendance, MonthlyAttendance, AttendanceDocument
from ..forms.forms import DailyAttendanceForm
import csv
from django.http import HttpResponse
from datetime import timedelta
import datetime
import jdatetime
from django.contrib.auth.models import User
from ..EmployeeModel import Employee
from core.decorators.decorators import role_required

@role_required('employee', 'admin')
@login_required
def daily_attendance_view(request):
    if request.method == 'POST':
        form = DailyAttendanceForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                # تاریخ جلالی از فرم
                jalali_date = form.cleaned_data['date']
                hours = form.cleaned_data['hours']
                description = form.cleaned_data['description']
                documents = request.FILES.getlist('documents')  # دریافت همه‌ی فایل‌های آپلود شده
                approved_by_user1 = form.cleaned_data['approved_by_user1']
                approved_by_user2 = form.cleaned_data['approved_by_user2']
                approved_by_user3 = form.cleaned_data['approved_by_user3']

                # دریافت بازه‌های زمانی
                time_ranges = []
                if 'start_times' in request.POST and 'end_times' in request.POST:
                    start_times = request.POST.getlist('start_times')
                    end_times = request.POST.getlist('end_times')
                    
                    # اطمینان از برابر بودن تعداد بازه‌ها
                    if len(start_times) == len(end_times):
                        # چک کردن که بازه‌ها خالی نباشند
                        for i in range(len(start_times)):
                            if start_times[i] and end_times[i]:
                                time_ranges.append({
                                    'start_time': start_times[i],
                                    'end_time': end_times[i]
                                })

                # محاسبه روز هفته
                jalali_weekday = jalali_date.weekday()
                
                # نگاشت بین روز هفته jdatetime و نام روز در مدل
                jalali_weekday_to_name = {
                    2: 'Monday',    # دوشنبه
                    3: 'Tuesday',   # سه شنبه
                    4: 'Wednesday', # چهارشنبه
                    5: 'Thursday',  # پنج شنبه
                    6: 'Friday',    # جمعه
                    0: 'Saturday',  # شنبه
                    1: 'Sunday'     # یکشنبه
                }
                day_of_week = jalali_weekday_to_name[jalali_weekday]

                # دیگر شنبه هفته را محاسبه نمی‌کنیم!
                # دقیقاً از همان تاریخی که کاربر انتخاب کرده استفاده می‌کنیم
                selected_date = jalali_date
                
                print(f"Debug - Selected date: {selected_date}, Day: {day_of_week}")
                
                # ایجاد یا به‌روزرسانی رکورد حضور
                attendance, created = WeeklyAttendance.objects.update_or_create(
                    employee=request.user,
                    week_start_date=selected_date,  # استفاده از همان تاریخ انتخابی
                    defaults={
                        'approved_by_user1': approved_by_user1,  # این فیلد حالا به Employee اشاره می‌کند
                        'approved_by_user2': approved_by_user2,  # این فیلد حالا به Employee اشاره می‌کند
                        'approved_by_user3': approved_by_user3,  # این فیلد حالا به Employee اشاره می‌کند
                        'user1_approved': False,
                        'user2_approved': False,
                        'user3_approved': False,
                        'approved_by_admin': False,
                        'description': description,
                        'day': day_of_week
                    }
                )
                
                # ذخیره مستندات آپلود شده
                if documents:
                    for document in documents:
                        AttendanceDocument.objects.create(
                            attendance=attendance,
                            file=document
                        )
                
                # تنظیم ساعات کاری برای روز مربوطه
                # نگاشت روز جلالی به فیلد مربوطه در مدل
                jalali_weekday_to_field = {
                    2: 'monday_hours',    # دوشنبه
                    3: 'tuesday_hours',   # سه شنبه
                    4: 'wednesday_hours', # چهارشنبه
                    5: 'thursday_hours',  # پنج شنبه
                    6: 'friday_hours',    # جمعه
                    0: 'saturday_hours',  # شنبه
                    1: 'sunday_hours'     # یکشنبه
                }
                
                # تنظیم مقدار ساعات برای روز مربوطه
                day_field = jalali_weekday_to_field[jalali_weekday]
                setattr(attendance, day_field, hours)
                
                # اطمینان از اینکه سایر فیلدها مقدار پیش‌فرض 0 دارند
                for field in jalali_weekday_to_field.values():
                    if getattr(attendance, field) is None:
                        setattr(attendance, field, 0)
                
                # محاسبه مجموع ساعات
                attendance.calculate_total_hours()
                attendance.save()

                # ذخیره بازه‌های زمانی
                # ابتدا بازه‌های قبلی را حذف می‌کنیم
                from HR.EmployeeAttendanceModel import TimeRange
                TimeRange.objects.filter(attendance=attendance).delete()
                
                # اضافه کردن بازه‌های جدید
                for time_range in time_ranges:
                    try:
                        start_time = datetime.datetime.strptime(time_range['start_time'], '%H:%M').time()
                        end_time = datetime.datetime.strptime(time_range['end_time'], '%H:%M').time()
                        
                        TimeRange.objects.create(
                            attendance=attendance,
                            start_time=start_time,
                            end_time=end_time
                        )
                    except (ValueError, TypeError) as e:
                        print(f"Error saving time range: {e}")

                # ترجمه روز هفته به فارسی برای پیام
                day_translation = {
                    'Saturday': 'شنبه',
                    'Sunday': 'یکشنبه',
                    'Monday': 'دوشنبه',
                    'Tuesday': 'سه‌شنبه',
                    'Wednesday': 'چهارشنبه',
                    'Thursday': 'پنج‌شنبه',
                    'Friday': 'جمعه'
                }
                persian_day = day_translation.get(day_of_week)
                
                messages.success(request, f'ساعات کاری برای {persian_day} با موفقیت ثبت شد!')
                return redirect('weekly_attendance_view')
                
            except Exception as e:
                messages.error(request, f'خطا در ثبت اطلاعات: {str(e)}')
        else:
            # نمایش خطاهای خاص فرم
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'خطا در فیلد {form.fields[field].label}: {error}')
    else:
        form = DailyAttendanceForm(user=request.user)

    attendances = WeeklyAttendance.objects.filter(employee=request.user).order_by('-week_start_date')
    status = request.GET.get('status')
    if status == 'approved':
        attendances = attendances.filter(approved_by_admin=True)
    elif status == 'pending':
        attendances = attendances.exclude(approved_by_admin=True)

    q = request.GET.get('q')
    if q:
        attendances = attendances.filter(Q(description__icontains=q) | Q(day__icontains=q))
    
    # دریافت و استفاده مستقیم از تاریخ‌های جلالی برای فیلتر
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        try:
            # تبدیل رشته به تاریخ جلالی و فیلتر مستقیم
            start_date = start_date.replace('-', '/').replace('.', '/')
            if '/' in start_date:
                year, month, day = map(int, start_date.split('/'))
                jalali_date = jdatetime.date(year, month, day)
                attendances = attendances.filter(week_start_date__gte=jalali_date)
        except:
            pass
            
    if end_date:
        try:
            # تبدیل رشته به تاریخ جلالی و فیلتر مستقیم
            end_date = end_date.replace('-', '/').replace('.', '/')
            if '/' in end_date:
                year, month, day = map(int, end_date.split('/'))
                jalali_date = jdatetime.date(year, month, day)
                attendances = attendances.filter(week_start_date__lte=jalali_date)
        except:
            pass

    # تاریخ‌های جلالی مستقیماً از دیتابیس خوانده می‌شوند
    formatted_attendances = []
    for attendance in attendances:
        # نیازی به تبدیل نیست چون فیلد از نوع jDateField است
        # فقط فرمت‌دهی مستقیم انجام می‌دهیم
        formatted_date = attendance.week_start_date.strftime('%Y/%m/%d')
        
        # مترجم روزهای هفته به فارسی
        day_translation = {
            'Saturday': 'شنبه',
            'Sunday': 'یکشنبه',
            'Monday': 'دوشنبه',
            'Tuesday': 'سه‌شنبه',
            'Wednesday': 'چهارشنبه',
            'Thursday': 'پنج‌شنبه',
            'Friday': 'جمعه'
        }
        
        # برگرداندن روز هفته به فارسی
        persian_day = day_translation.get(attendance.day, attendance.day)
        
        # شمارش تعداد تاییدهای انجام شده
        approval_count = sum([
            1 if attendance.user1_approved else 0,
            1 if attendance.user2_approved else 0,
            1 if attendance.user3_approved else 0
        ])

        # آماده‌سازی جزئیات ساعات روزانه
        daily_hours = {
            'شنبه': attendance.saturday_hours if attendance.saturday_hours > 0 else None,
            'یکشنبه': attendance.sunday_hours if attendance.sunday_hours > 0 else None,
            'دوشنبه': attendance.monday_hours if attendance.monday_hours > 0 else None,
            'سه‌شنبه': attendance.tuesday_hours if attendance.tuesday_hours > 0 else None,
            'چهارشنبه': attendance.wednesday_hours if attendance.wednesday_hours > 0 else None,
            'پنج‌شنبه': attendance.thursday_hours if attendance.thursday_hours > 0 else None,
            'جمعه': attendance.friday_hours if attendance.friday_hours > 0 else None,
        }
        
        # دریافت بازه‌های زمانی
        from HR.EmployeeAttendanceModel import TimeRange
        time_ranges = TimeRange.objects.filter(attendance=attendance).order_by('start_time')
        formatted_time_ranges = []
        
        # چک کردن آیا بازه زمانی وجود دارد
        print(f"Debug - Checking time ranges for attendance {attendance.id}")
        
        for time_range in time_ranges:
            formatted_time_ranges.append({
                'start_time': time_range.start_time.strftime('%H:%M'),
                'end_time': time_range.end_time.strftime('%H:%M'),
                'duration': time_range.duration
            })
            print(f"Debug - Added time range: {time_range.start_time.strftime('%H:%M')} to {time_range.end_time.strftime('%H:%M')}")
        
        # وضعیت تاییدها
        attendance.enough_approvals = attendance.is_enough_user_approvals
        
        formatted_attendances.append({
            'id': attendance.id,
            'week_start_date': formatted_date,
            'day': persian_day,
            'total_hours': attendance.total_hours,
            'daily_hours': daily_hours,  # جزئیات ساعات روزانه
            'time_ranges': formatted_time_ranges,  # بازه‌های زمانی
            'description': attendance.description,
            'documents': attendance.documents,  # این یک رابطه related_name است و documents.all در تمپلیت استفاده می‌شود
            'approved_by_admin': attendance.approved_by_admin,
            'user1_approved': attendance.user1_approved,
            'user2_approved': attendance.user2_approved,
            'user3_approved': attendance.user3_approved,
            'approval_count': approval_count,
            'enough_approvals': attendance.is_enough_user_approvals,
            'is_fully_approved': attendance.is_fully_approved,
        })

    # دریافت اطلاعات خلاصه ماهانه برای کارمند
    from django.db.models.functions import TruncMonth
    from django.db.models import Sum
    
    # فیلتر ماهانه
    filter_month = request.GET.get('filter_month')
    month_filter = None
    
    if filter_month:
        try:
            # فرض می‌کنیم فرمت به صورت YYYY/MM یا YYYY-MM باشد
            filter_month = filter_month.replace('-', '/').replace('.', '/')
            if '/' in filter_month:
                month_parts = filter_month.split('/')
                if len(month_parts) == 2:
                    year, month = map(int, month_parts)
                    month_filter = f"{year}-{month:02d}"
                    print(f"Debug - Filter by month: {month_filter}")
        except Exception as e:
            print(f"Error parsing month filter: {e}")
            pass
    
    # استخراج اطلاعات ماهانه از مدل MonthlyAttendance
    monthly_summary_query = MonthlyAttendance.objects.filter(employee=request.user)
    
    # اگر فیلتر ماه فعال باشد، اعمال می‌کنیم
    if month_filter:
        monthly_summary_query = monthly_summary_query.filter(month=month_filter)
        print(f"Debug - Filtered monthly data: {monthly_summary_query.count()} records found")
    
    monthly_summary = monthly_summary_query.order_by('-month')
    
    # تبدیل تاریخ‌های ماهانه به فرمت جلالی قابل خواندن
    formatted_monthly_summary = []
    for month_data in monthly_summary:
        # فرمت ماه به صورت YYYY-MM است
        year, month = month_data.month.split('-')
        # نمایش به فرمت جلالی استاندارد
        jalali_month = f"{year}/{month}"
        
        formatted_monthly_summary.append({
            'month': jalali_month,
            'total_hours': round(month_data.total_hours, 2)
        })

    return render(request, 'weekly_attendance.html', {
        'form': form,
        'attendances': formatted_attendances,
        'monthly_summary': formatted_monthly_summary,
        'status': status,
        'q': q
    })

@role_required('employee', 'admin')
@login_required
def download_attendance_report(request):
    attendances = WeeklyAttendance.objects.filter(employee=request.user).order_by('-week_start_date')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['تاریخ شروع هفته', 'مجموع ساعات', 'توضیحات', 'تأیید ادمین', 'تعداد تأییدها', 'وضعیت کلی'])
    for attendance in attendances:
        # استفاده مستقیم از تاریخ جلالی
        formatted_date = attendance.week_start_date.strftime('%Y/%m/%d')
        
        # محاسبه تعداد تاییدها
        approval_count = sum([
            1 if attendance.user1_approved else 0,
            1 if attendance.user2_approved else 0,
            1 if attendance.user3_approved else 0
        ])
        
        # وضعیت کلی
        status = "تایید نهایی" if attendance.is_fully_approved else "در انتظار تایید"
        
        writer.writerow([
            formatted_date,
            attendance.total_hours,
            attendance.description,
            '✅' if attendance.approved_by_admin else '❌',
            f'{approval_count}/3',
            status
        ])

    return response

@role_required('employee', 'admin')
@login_required
def pending_approvals_view(request):
    if request.user.is_superuser:
        # برای ادمین، نمایش رکوردهایی که حداقل 2 تایید دارند ولی تایید ادمین ندارند
        pending_attendances = WeeklyAttendance.objects.filter(
            (
                (Q(user1_approved=True) & Q(user2_approved=True)) |
                (Q(user1_approved=True) & Q(user3_approved=True)) |
                (Q(user2_approved=True) & Q(user3_approved=True))
            ) & 
            Q(approved_by_admin=False)
        ).order_by('-week_start_date')
    else:
        # برای کاربران عادی، فقط نمایش رکوردهایی که:
        # 1. در انتظار تایید آنها هستند
        # 2. هنوز به حد نصاب 2 تایید نرسیده‌اند
        try:
            # ابتدا کارمند متناظر با کاربر فعلی را پیدا می‌کنیم
            current_employee = Employee.objects.get(user=request.user)
            
            # نمایش رکوردهایی که کاربر فعلی باید تایید کند و هنوز به 2 تایید نرسیده‌اند
            pending_attendances = WeeklyAttendance.objects.filter(
                (
                    (Q(approved_by_user1=current_employee, user1_approved=False) & ~(Q(user2_approved=True) & Q(user3_approved=True))) |
                    (Q(approved_by_user2=current_employee, user2_approved=False) & ~(Q(user1_approved=True) & Q(user3_approved=True))) |
                    (Q(approved_by_user3=current_employee, user3_approved=False) & ~(Q(user1_approved=True) & Q(user2_approved=True)))
                )
            ).order_by('-week_start_date')
            
            # این کد برای تست کردن تعداد رکوردهای نمایش داده شده است
            print(f"Debug - Pending approvals for user {request.user.username}: {pending_attendances.count()} records")
            
        except Employee.DoesNotExist:
            # اگر کاربر فعلی کارمند نیست، لیست خالی نمایش دهیم
            pending_attendances = WeeklyAttendance.objects.none()
        
    # فرمت‌دهی تاریخ‌ها و اطلاعات دیگر
    pending_data = []
    
    print(f"Debug - Total pending records: {pending_attendances.count()}")
    
    for attendance in pending_attendances:
        # استفاده مستقیم از تاریخ جلالی ذخیره شده
        formatted_date = attendance.week_start_date.strftime('%Y/%m/%d')
        
        # مترجم روزهای هفته به فارسی
        day_translation = {
            'Saturday': 'شنبه',
            'Sunday': 'یکشنبه',
            'Monday': 'دوشنبه',
            'Tuesday': 'سه‌شنبه',
            'Wednesday': 'چهارشنبه',
            'Thursday': 'پنج‌شنبه',
            'Friday': 'جمعه'
        }
        persian_day = day_translation.get(attendance.day, attendance.day)
        
        # محاسبه تعداد تاییدها
        approval_count = sum([
            1 if attendance.user1_approved else 0,
            1 if attendance.user2_approved else 0,
            1 if attendance.user3_approved else 0
        ])
        
        # آماده‌سازی جزئیات ساعات روزانه
        daily_hours = {
            'شنبه': attendance.saturday_hours if attendance.saturday_hours > 0 else None,
            'یکشنبه': attendance.sunday_hours if attendance.sunday_hours > 0 else None,
            'دوشنبه': attendance.monday_hours if attendance.monday_hours > 0 else None,
            'سه‌شنبه': attendance.tuesday_hours if attendance.tuesday_hours > 0 else None,
            'چهارشنبه': attendance.wednesday_hours if attendance.wednesday_hours > 0 else None,
            'پنج‌شنبه': attendance.thursday_hours if attendance.thursday_hours > 0 else None,
            'جمعه': attendance.friday_hours if attendance.friday_hours > 0 else None,
        }
        
        # دریافت بازه‌های زمانی
        from HR.EmployeeAttendanceModel import TimeRange
        time_ranges = list(TimeRange.objects.filter(attendance=attendance).order_by('start_time'))
        
        print(f"Debug - Attendance ID {attendance.id} has {len(time_ranges)} time ranges")
        
        formatted_time_ranges = []
        for time_range in time_ranges:
            formatted_entry = {
                'start_time': time_range.start_time.strftime('%H:%M'),
                'end_time': time_range.end_time.strftime('%H:%M'),
                'duration': time_range.duration
            }
            formatted_time_ranges.append(formatted_entry)
            print(f"Debug - Added range: {formatted_entry['start_time']} to {formatted_entry['end_time']}")
            
        # اطمینان از اینکه لیست بازه‌های زمانی خالی نیست
        print(f"Debug - Final formatted_time_ranges: {formatted_time_ranges}")
        
        # وضعیت تاییدها
        attendance_data = {
            'id': attendance.id,
            'employee': attendance.employee,
            'jalali_date': formatted_date,
            'persian_day': persian_day,
            'total_hours': attendance.total_hours,
            'daily_hours': daily_hours,  # جزئیات ساعات روزانه
            'time_ranges': formatted_time_ranges,  # بازه‌های زمانی
            'description': attendance.description,
            'documents': attendance.documents,
            'approved_by_user1': attendance.approved_by_user1,
            'approved_by_user2': attendance.approved_by_user2,
            'approved_by_user3': attendance.approved_by_user3,
            'user1_approved': attendance.user1_approved,
            'user2_approved': attendance.user2_approved,
            'user3_approved': attendance.user3_approved,
            'approved_by_admin': attendance.approved_by_admin,
            'approval_count': approval_count,
            'enough_approvals': attendance.is_enough_user_approvals
        }
        
        pending_data.append(attendance_data)

    return render(request, 'pending_approvals.html', {
        'pending_attendances': pending_data
    })

@role_required('employee', 'admin')
@login_required
def approve_attendance(request, attendance_id):
    attendance = get_object_or_404(WeeklyAttendance, id=attendance_id)
    
    # اگر کاربر ادمین است، مستقیماً اجازه تایید بدهیم
    if request.user.is_superuser:
        # بررسی اینکه آیا به حد نصاب 2 تایید رسیده‌ایم یا خیر
        if attendance.is_enough_user_approvals:
            attendance.approved_by_admin = True
            attendance.save()
            messages.success(request, "تأیید ادمین ثبت شد!")
        else:
            messages.error(request, "حداقل دو تایید از تاییدکنندگان لازم است، سپس می‌توانید تایید ادمین را انجام دهید.")
        return redirect('pending_approvals')
    
    try:
        # ابتدا کارمند متناظر با کاربر فعلی را پیدا می‌کنیم
        current_employee = Employee.objects.get(user=request.user)
        
        # بررسی اینکه آیا به حد نصاب 2 تایید رسیده‌ایم یا خیر
        approval_count = sum([
            1 if attendance.user1_approved else 0,
            1 if attendance.user2_approved else 0,
            1 if attendance.user3_approved else 0
        ])
        
        # اگر به حد نصاب 2 تایید رسیده‌ایم، نیازی به تایید بیشتر نیست
        if approval_count >= 2 and not request.user.is_superuser:
            messages.info(request, "این رکورد قبلاً توسط 2 نفر تایید شده و نیاز به تایید بیشتر ندارد.")
            return redirect('pending_approvals')
        
        if attendance.approved_by_user1 and attendance.approved_by_user1 == current_employee:
            attendance.user1_approved = True
            attendance.save()
            messages.success(request, "تأیید شما ثبت شد!")
        elif attendance.approved_by_user2 and attendance.approved_by_user2 == current_employee:
            attendance.user2_approved = True
            attendance.save()
            messages.success(request, "تأیید شما ثبت شد!")
        elif attendance.approved_by_user3 and attendance.approved_by_user3 == current_employee:
            attendance.user3_approved = True
            attendance.save()
            messages.success(request, "تأیید شما ثبت شد!")
        else:
            messages.error(request, "شما مجاز به تأیید این رکورد نیستید.")
            return redirect('pending_approvals')
    except Employee.DoesNotExist:
        # اگر کاربر فعلی کارمند نیست و ادمین هم نیست، اجازه تایید ندارد
        messages.error(request, "شما کارمند فعالی نیستید و مجاز به تأیید نمی‌باشید.")
        return redirect('pending_approvals')
    
    # بررسی اینکه آیا به حد نصاب 2 تایید رسیده‌ایم پس از تایید فعلی
    if attendance.is_enough_user_approvals:
        messages.success(request, "این رکورد به حد نصاب 2 تایید رسید و حالا در انتظار تایید ادمین است.")
    
    # اگر هم 2 تایید کاربران و هم تایید ادمین را داشته باشیم، آنگاه تایید نهایی شده است
    if attendance.is_fully_approved:
        messages.success(request, "ساعات کاری با موفقیت تأیید شد!")

    return redirect('pending_approvals')

@role_required('admin')
@login_required
def attendance_summary_view(request):
    # فقط ادمین مجاز به دیدن این صفحه است
    if not request.user.is_superuser:
        messages.error(request, "شما دسترسی لازم برای مشاهده این صفحه را ندارید.")
        return redirect('weekly_attendance_view')

    week = request.GET.get('week')
    month = request.GET.get('month')
    employee_id = request.GET.get('employee_id')
    
    # دریافت همه کارمندان برای نمایش در dropdown
    employees = Employee.objects.all().order_by('last_name', 'first_name')
    
    # اگر کارمند انتخاب شده، داده‌های آن کارمند را نمایش می‌دهیم
    if employee_id:
        try:
            selected_employee = Employee.objects.get(id=employee_id)
            # Employee is linked to User via OneToOneField, so we need to filter by the related user
            weekly_qs = WeeklyAttendance.objects.filter(employee=selected_employee.user)
            monthly_qs = MonthlyAttendance.objects.filter(employee=selected_employee.user)
        except Employee.DoesNotExist:
            messages.error(request, "کارمند مورد نظر یافت نشد.")
            weekly_qs = WeeklyAttendance.objects.none()
            monthly_qs = MonthlyAttendance.objects.none()
            selected_employee = None
    else:
        # نمای کلی - داده‌های همه کارمندان
        weekly_qs = WeeklyAttendance.objects.all()
        monthly_qs = MonthlyAttendance.objects.all()
        selected_employee = None

    # فیلتر بر اساس تاریخ جلالی هفته
    if week:
        try:
            # تبدیل رشته به تاریخ جلالی و فیلتر مستقیم
            week = week.replace('-', '/').replace('.', '/')
            if '/' in week:
                year, month_val, day = map(int, week.split('/'))
                jalali_date = jdatetime.date(year, month_val, day)
                weekly_qs = weekly_qs.filter(week_start_date=jalali_date)
        except:
            pass
    
    # فیلتر بر اساس ماه جلالی
    if month:
        try:
            # فرض می‌کنیم فرمت به صورت YYYY/MM یا YYYY-MM باشد
            month = month.replace('-', '/').replace('.', '/')
            if '/' in month:
                month_parts = month.split('/')
                if len(month_parts) == 2:
                    year, month_val = map(int, month_parts)
                    # برای فیلتر کردن بر اساس ماه در فیلد jDateField
                    # باید محدوده ابتدا و انتهای ماه را محاسبه کنیم
                    start_of_month = jdatetime.date(year, month_val, 1)
                    if month_val == 12:
                        end_of_month = jdatetime.date(year + 1, 1, 1) - jdatetime.timedelta(days=1)
                    else:
                        end_of_month = jdatetime.date(year, month_val + 1, 1) - jdatetime.timedelta(days=1)
                    
                    weekly_qs = weekly_qs.filter(
                        week_start_date__gte=start_of_month,
                        week_start_date__lte=end_of_month
                    )
                    
                    # برای ماهانه هنوز از رشته استفاده می‌کنیم
                    monthly_qs = monthly_qs.filter(month=f"{year}-{month_val:02d}")
        except:
            pass

    # محاسبه آمار کلی و تفکیک‌شده بر اساس کارمندان
    employee_stats = []
    if not employee_id:
        # گروه‌بندی بر اساس کارمند برای نمای کلی
        employee_data = weekly_qs.values('employee__username').annotate(
            total_hours=Sum('total_hours'),
            attendance_count=Count('id')
        ).order_by('-total_hours')
        
        for data in employee_data:
            try:
                user = User.objects.get(username=data['employee__username'])
                # Try to get the associated Employee record
                try:
                    employee = Employee.objects.get(user=user)
                    employee_stats.append({
                        'id': employee.id,
                        'username': user.username,
                        'full_name': f"{employee.first_name} {employee.last_name}",
                        'total_hours': round(data['total_hours'], 2),
                        'attendance_count': data['attendance_count']
                    })
                except Employee.DoesNotExist:
                    # Fallback if no employee record exists for this user
                    employee_stats.append({
                        'id': user.id,
                        'username': user.username,
                        'full_name': f"{user.first_name} {user.last_name}",
                        'total_hours': round(data['total_hours'], 2),
                        'attendance_count': data['attendance_count']
                    })
            except User.DoesNotExist:
                continue

    weekly_summary = weekly_qs.values('week_start_date', 'employee__username').annotate(
        total_hours=Sum('total_hours')
    ).order_by('-week_start_date')
    
    monthly_summary = monthly_qs.order_by('-month')

    # محاسبه جمع و میانگین به صورت دستی
    total_weekly_hours = sum(item['total_hours'] for item in weekly_summary) if weekly_summary else 0
    total_monthly_hours = sum(item.total_hours for item in monthly_summary) if monthly_summary else 0
    avg_weekly_hours = total_weekly_hours / len(weekly_summary) if weekly_summary else 0
    
    # فرمت کردن مقادیر عددی با دو رقم اعشار
    total_weekly_hours = round(total_weekly_hours, 2)
    total_monthly_hours = round(total_monthly_hours, 2)
    avg_weekly_hours = round(avg_weekly_hours, 2)

    # فرمت‌سازی داده‌های هفتگی - تاریخ جلالی مستقیماً از دیتابیس
    formatted_weekly_summary = []
    for summary in weekly_summary:
        # تاریخ جلالی را مستقیماً فرمت می‌کنیم
        jalali_date = summary['week_start_date']  # already a jdatetime.date instance
        formatted_date = jalali_date.strftime('%Y/%m/%d')
        
        # اضافه کردن نام کاربری کارمند
        username = summary['employee__username']
        
        formatted_weekly_summary.append({
            'week_start_date': formatted_date,
            'total_hours': round(summary['total_hours'], 2),
            'employee': username
        })
        
    # تبدیل تاریخ‌های ماهانه به فرمت جلالی
    formatted_monthly_summary = []
    for summary in monthly_summary:
        year, month = summary.month.split('-')
        # نمایش به فرمت جلالی استاندارد
        jalali_month = f"{year}/{month}"
        
        formatted_monthly_summary.append({
            'month': jalali_month,
            'total_hours': round(summary.total_hours, 2),
            'employee': summary.employee.username
        })

    return render(request, 'attendance_summary.html', {
        'weekly_summary': formatted_weekly_summary,
        'monthly_summary': formatted_monthly_summary,
        'selected_week': week,
        'selected_month': month,
        'total_weekly_hours': total_weekly_hours,
        'total_monthly_hours': total_monthly_hours,
        'avg_weekly_hours': round(avg_weekly_hours, 2),
        'employees': employees,
        'selected_employee': selected_employee,
        'employee_stats': employee_stats,
    })

@role_required('admin')
@login_required
def clear_approval_references(request):
    if not request.user.is_superuser:
        messages.error(request, "فقط ادمین اجازه انجام این عملیات را دارد.")
        return redirect('weekly_attendance_view')
    
    # پاک کردن همه ارجاعات به تاییدکنندگان
    WeeklyAttendance.objects.all().update(
        approved_by_user1=None,
        approved_by_user2=None,
        approved_by_user3=None,
        user1_approved=False,
        user2_approved=False,
        user3_approved=False,
        approved_by_admin=False
    )
    
    messages.success(request, "همه ارجاعات تاییدکنندگان با موفقیت پاک شدند. اکنون می‌توانید مایگریشن‌ها را اجرا کنید.")
    return redirect('weekly_attendance_view')