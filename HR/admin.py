from django.contrib import admin
from .forms.forms import WeeklyAttendanceForm
from .EmployeeAttendanceModel import WeeklyAttendance, MonthlyAttendance, WorkCalendar, Salary
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.template.response import TemplateResponse
from django.urls import path
from django.contrib.auth.models import User
from .EmployeeModel import Employee

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user__username', 'first_name', 'last_name', 'email')
    search_fields = ('user__username', 'first_name', 'last_name', 'email')


# class MonthFilter(admin.SimpleListFilter):
#     title = 'ماه'
#     parameter_name = 'month'

#     def lookups(self, request, model_admin):
#         # استخراج مقادیر یکتا از فیلد 'month'
#         months = MonthlyAttendance.objects.values_list('month', flat=True).distinct()
#         return [(month, month) for month in months]

#     def queryset(self, request, queryset):
#         if self.value():
#             return queryset.filter(month=self.value())
#         return queryset

# class WeeklyAttendanceInline(admin.TabularInline):
#     model = WeeklyAttendance
#     extra = 1
#     fields = (
#         'week_start_date', 'saturday_hours', 'sunday_hours', 'monday_hours',
#         'tuesday_hours', 'wednesday_hours', 'thursday_hours', 'friday_hours', 'total_hours'
#     )
#     readonly_fields = ('total_hours',)

# @admin.register(User)
# class EmployeeAdmin(admin.ModelAdmin):
#     list_display = ('username', 'first_name', 'last_name', 'email')
#     search_fields = ('username', 'first_name', 'last_name', 'email')
#     inlines = [WeeklyAttendanceInline]
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path('<int:employee_id>/attendance/', self.admin_site.admin_view(self.attendance_view), name='employee-attendance'),
#         ]
#         return custom_urls + urls

#     def attendance_view(self, request, employee_id):
#         from django.shortcuts import get_object_or_404
#         from ._models import MonthlyAttendance
#         from django.db.models import Sum
#         import jdatetime

#         employee = get_object_or_404(User, pk=employee_id)

#         # دریافت هفته جاری
#         today = jdatetime.date.today()
#         start_of_week = today - jdatetime.timedelta(days=today.weekday())
#         selected_week = request.GET.get('week', start_of_week.togregorian().isoformat())

#         # فیلتر حضور هفتگی بر اساس هفته انتخاب‌شده
#         weekly_attendance = WeeklyAttendance.objects.filter(
#             employee=employee,
#             week_start_date=selected_week
#         ).order_by('-week_start_date')

#         # محاسبه مجموع ساعات ماهانه
#         monthly_total_hours = MonthlyAttendance.objects.filter(employee=employee).aggregate(
#             Sum('total_hours')
#         )['total_hours__sum'] or 0

#         # دریافت تقویم کاری
#         work_calendar = WorkCalendar.objects.filter(
#             date__range=[start_of_week.togregorian(), (start_of_week + jdatetime.timedelta(days=6)).togregorian()]
#         )
#         # ارسال داده‌ها به قالب
#         return TemplateResponse(request, 'admin/employee_attendance.html', {
#             'employee': employee,
#             'weekly_attendance': weekly_attendance,
#             'monthly_total_hours': monthly_total_hours,
#             'selected_week': selected_week,
#             'work_calender' : work_calendar,
#             'title': f'حضور هفتگی {employee.username}',
#     })

#     def attendance_report(request):
#         from django.db.models import Sum
#         from django.utils.timezone import now

#         # فیلتر بر اساس بازه زمانی
#         start_date = request.GET.get('start_date', now().replace(day=1))
#         end_date = request.GET.get('end_date', now())

#         # جمع‌آوری داده‌ها
#         report = WeeklyAttendance.objects.filter(
#             week_start_date__range=[start_date, end_date]
#         ).values('employee__username').annotate(
#             total_hours=Sum('total_hours')
#         ).order_by('-total_hours')

#         return TemplateResponse(request, 'admin/attendance_report.html', {
#             'report': report,
#             'start_date': start_date,
#             'end_date': end_date,
#             'title': 'گزارش ساعات حضور',
#         })
    
#     def salary_report(request):
#         from django.db.models import Sum
#         salaries = Salary.objects.all().order_by('-month')
#         return TemplateResponse(request, 'admin/salary_report.html', {
#             'salaries': salaries,
#             'title': 'گزارش حقوق و مزایا',
#         })


# @admin.register(WeeklyAttendance)
# class WeeklyAttendanceAdmin(admin.ModelAdmin):
#     form = WeeklyAttendanceForm
#     list_display = ('employee', 'week_start_date', 'total_hours')
#     list_filter = ('week_start_date', 'employee')
#     search_fields = ('employee__username',)
#     actions = ['recalculate_total_hours']

#     def recalculate_total_hours(self, request, queryset):
#         for attendance in queryset:
#             attendance.calculate_total_hours()
#             attendance.save()
#         self.message_user(request, "مجموع ساعات با موفقیت محاسبه شد.")
#     recalculate_total_hours.short_description = "محاسبه مجدد مجموع ساعات"

# @admin.register(MonthlyAttendance)
# class MonthlyAttendanceAdmin(admin.ModelAdmin):
#     list_display = ('employee', 'month', 'total_hours')
#     list_filter = ('employee', MonthFilter)
#     search_fields = ('employee__username', 'month')


# @admin.register(WorkCalendar)
# class WorkCalendarAdmin(admin.ModelAdmin):
#     list_display = ('date', 'is_holiday', 'working_hours')
#     list_filter = ('is_holiday',)
#     search_fields = ('date',)

# @admin.register(Salary)
# class SalaryAdmin(admin.ModelAdmin):
#     list_display = ('employee', 'month', 'base_salary', 'overtime_hours', 'overtime_pay', 'deductions', 'total_salary')
#     list_filter = ('employee', 'month')
#     search_fields = ('employee__username', 'month')