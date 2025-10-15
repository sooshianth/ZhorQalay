from django.contrib import admin
from .forms.forms import WeeklyAttendanceForm
from .EmployeeAttendanceModel import WeeklyAttendance, MonthlyAttendance, WorkCalendar, Salary, AttendanceConfiguration
from .MorqkModel import MorqkTask, MonthlyMorqkSummary, TaskAssignment
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.template.response import TemplateResponse
from django.urls import path
from django.contrib.auth.models import User
from .EmployeeModel import Employee
from admin_list_charts.admin import ListChartMixin

@admin.register(Employee)
class EmployeeAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'email', 'is_manager')
    list_filter = ('is_manager',)
    search_fields = ('user__username', 'first_name', 'last_name', 'email')
    date_hierarchy = 'hire_date'


class MonthFilter(admin.SimpleListFilter):
    title = 'ماه'
    parameter_name = 'month'

    def lookups(self, request, model_admin):
        # استخراج مقادیر یکتا از فیلد 'month'
        months = MonthlyAttendance.objects.values_list('month', flat=True).distinct()
        return [(month, month) for month in months]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(month=self.value())
        return queryset

class WeeklyAttendanceInline(admin.TabularInline):
    model = WeeklyAttendance
    extra = 1
    fields = (
        'week_start_date', 'day', 'saturday_hours', 'sunday_hours', 'monday_hours',
        'tuesday_hours', 'wednesday_hours', 'thursday_hours', 'friday_hours', 'total_hours'
    )
    readonly_fields = ('total_hours',)


@admin.register(WeeklyAttendance)
class WeeklyAttendanceAdmin(ListChartMixin, admin.ModelAdmin):
    form = WeeklyAttendanceForm
    list_display = ('employee', 'week_start_date', 'day', 'total_hours', 'is_fully_approved')
    list_filter = ('week_start_date', 'employee', 'approved_by_admin')
    search_fields = ('employee__username', 'description')
    actions = ['recalculate_total_hours']
    date_hierarchy = 'week_start_date'

    def recalculate_total_hours(self, request, queryset):
        for attendance in queryset:
            attendance.calculate_total_hours()
            attendance.save()
        self.message_user(request, "مجموع ساعات با موفقیت محاسبه شد.")
    recalculate_total_hours.short_description = "محاسبه مجدد مجموع ساعات"

@admin.register(MonthlyAttendance)
class MonthlyAttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'month', 'total_hours')
    list_filter = ('employee', MonthFilter)
    search_fields = ('employee__username', 'month')


@admin.register(AttendanceConfiguration)
class AttendanceConfigurationAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('allowed_delay_days', 'consider_friday_exception', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'consider_friday_exception', 'created_at')
    search_fields = ('allowed_delay_days',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('تنظیمات اصلی', {
            'fields': ('allowed_delay_days', 'consider_friday_exception', 'is_active')
        }),
        ('اطلاعات تاریخ', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def has_delete_permission(self, request, obj=None):
        # فقط اگر بیش از یک تنظیمات وجود داشته باشد، امکان حذف باشد
        return AttendanceConfiguration.objects.count() > 1
    
    def save_model(self, request, obj, form, change):
        # هنگام ذخیره، اطمینان حاصل کنیم که فقط یک تنظیمات فعال باشد
        if obj.is_active:
            AttendanceConfiguration.objects.filter(is_active=True).exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


class TaskAssignmentInline(admin.TabularInline):
    model = TaskAssignment
    extra = 1
    fields = ('employee', 'percentage', 'status', 'completed_at')
    readonly_fields = ('completed_at',)


@admin.register(MorqkTask)
class MorqkTaskAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'is_multi_assigned', 'morqk_value', 'status', 'created_by', 'created_at', 'due_date')
    list_filter = ('status', 'is_multi_assigned', 'morqk_value', 'created_at', 'assigned_to')
    search_fields = ('title', 'description', 'assigned_to__username', 'created_by__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'completed_at', 'approved_at')
    inlines = [TaskAssignmentInline]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('title', 'description', 'is_multi_assigned', 'assigned_to', 'created_by', 'morqk_value', 'due_date')
        }),
        ('وضعیت', {
            'fields': ('status', 'completion_note', 'approval_note', 'rejection_note')
        }),
        ('تاریخ‌ها', {
            'fields': ('created_at', 'completed_at', 'approved_at', 'approved_by'),
            'classes': ('collapse',),
        }),
    )


@admin.register(MonthlyMorqkSummary)
class MonthlyMorqkSummaryAdmin(ListChartMixin, admin.ModelAdmin):
    list_display = ('employee', 'month', 'total_approved_morqk', 'approved_tasks', 'total_tasks', 'last_updated')
    list_filter = ('month', 'employee')
    search_fields = ('employee__username', 'month')
    readonly_fields = ('last_updated',)
    date_hierarchy = 'last_updated'
