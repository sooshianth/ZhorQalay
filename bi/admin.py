from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI, UserPreference, DashboardSession
)


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'app_name', 'model_name', 'is_active', 'created_at')
    list_filter = ('type', 'is_active', 'created_at')
    search_fields = ('name', 'app_name', 'model_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'type', 'description', 'is_active')
        }),
        ('تنظیمات اتصال', {
            'fields': ('app_name', 'model_name', 'connection_config'),
            'classes': ('collapse',)
        }),
        ('زمان‌بندی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(MetricDefinition)
class MetricDefinitionAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'data_source', 'field_name', 'aggregation_type', 'unit', 'is_active')
    list_filter = ('aggregation_type', 'is_active', 'data_source')
    search_fields = ('name', 'display_name', 'field_name')
    autocomplete_fields = ('data_source',)
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'display_name', 'data_source', 'is_active')
        }),
        ('تنظیمات محاسبه', {
            'fields': ('field_name', 'aggregation_type', 'filter_expression', 'unit')
        }),
        ('توضیحات', {
            'fields': ('description',),
            'classes': ('collapse',)
        })
    )


@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'is_public', 'widgets_count', 'refresh_interval', 'is_active', 'created_at')
    list_filter = ('is_public', 'is_active', 'created_at', 'owner')
    search_fields = ('name', 'description', 'owner__username')
    readonly_fields = ('id', 'created_at', 'updated_at', 'widgets_count')
    filter_horizontal = ('allowed_users',)
    
    def widgets_count(self, obj):
        return obj.widgets.count()
    widgets_count.short_description = 'تعداد ویجت'
    
    def view_dashboard_link(self, obj):
        url = reverse('bi:dashboard_detail', args=[obj.id])
        return format_html('<a href="{}" target="_blank">مشاهده داشبورد</a>', url)
    view_dashboard_link.short_description = 'لینک'
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('id', 'name', 'description', 'owner')
        }),
        ('تنظیمات دسترسی', {
            'fields': ('is_public', 'allowed_users', 'is_active')
        }),
        ('تنظیمات نمایش', {
            'fields': ('layout_config', 'refresh_interval'),
            'classes': ('collapse',)
        }),
        ('زمان‌بندی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


class WidgetInline(admin.TabularInline):
    model = Widget
    extra = 0
    readonly_fields = ('id',)
    fields = ('title', 'chart', 'size', 'position_x', 'position_y', 'width', 'height', 'is_visible', 'order')


@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = ('name', 'chart_type', 'data_source', 'x_axis_field', 'time_period', 'is_real_time', 'created_at')
    list_filter = ('chart_type', 'time_period', 'is_real_time', 'created_at', 'data_source')
    search_fields = ('name', 'x_axis_field', 'group_by_field')
    autocomplete_fields = ('data_source',)
    filter_horizontal = ('y_axis_metrics',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [WidgetInline]
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('id', 'name', 'chart_type', 'data_source')
        }),
        ('تنظیمات داده', {
            'fields': ('x_axis_field', 'y_axis_metrics', 'group_by_field', 'time_period')
        }),
        ('تنظیمات پیشرفته', {
            'fields': ('chart_config', 'drill_down_config', 'filters', 'is_real_time'),
            'classes': ('collapse',)
        }),
        ('زمان‌بندی', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Widget)
class WidgetAdmin(admin.ModelAdmin):
    list_display = ('title', 'dashboard', 'chart', 'size', 'position_display', 'is_visible', 'order')
    list_filter = ('size', 'is_visible', 'dashboard')
    search_fields = ('title', 'dashboard__name', 'chart__name')
    autocomplete_fields = ('dashboard', 'chart')
    readonly_fields = ('id',)
    
    def position_display(self, obj):
        return f"({obj.position_x}, {obj.position_y})"
    position_display.short_description = 'موقعیت'
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('id', 'dashboard', 'chart', 'title', 'is_visible', 'order')
        }),
        ('تنظیمات چیدمان', {
            'fields': ('size', 'position_x', 'position_y', 'width', 'height')
        }),
        ('تنظیمات اضافی', {
            'fields': ('widget_config',),
            'classes': ('collapse',)
        })
    )


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'data_source', 'owner', 'is_public', 'is_scheduled', 'created_at')
    list_filter = ('report_type', 'is_public', 'is_scheduled', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    autocomplete_fields = ('data_source', 'owner')
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('id', 'name', 'description', 'report_type', 'data_source', 'owner')
        }),
        ('تنظیمات دسترسی', {
            'fields': ('is_public',)
        }),
        ('تنظیمات داده', {
            'fields': ('columns', 'filters', 'grouping', 'sorting', 'aggregations'),
            'classes': ('collapse',)
        }),
        ('زمان‌بندی', {
            'fields': ('is_scheduled', 'schedule_config', 'export_formats'),
            'classes': ('collapse',)
        }),
        ('زمان‌بندی سیستم', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(Filter)
class FilterAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'data_source', 'field_name', 'filter_type', 'default_operator', 'is_required')
    list_filter = ('filter_type', 'default_operator', 'is_required', 'data_source')
    search_fields = ('name', 'display_name', 'field_name')
    autocomplete_fields = ('data_source',)
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'display_name', 'data_source', 'field_name')
        }),
        ('تنظیمات فیلتر', {
            'fields': ('filter_type', 'default_operator', 'is_required')
        }),
        ('گزینه‌ها و مقادیر', {
            'fields': ('options', 'default_value', 'validation_rules'),
            'classes': ('collapse',)
        })
    )


@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'metric', 'kpi_type', 'target_value', 'warning_threshold', 'critical_threshold', 'is_active')
    list_filter = ('kpi_type', 'trend_type', 'is_active')
    search_fields = ('name', 'display_name', 'description')
    autocomplete_fields = ('metric',)
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('name', 'display_name', 'description', 'metric', 'is_active')
        }),
        ('تنظیمات KPI', {
            'fields': ('kpi_type', 'trend_type', 'comparison_period')
        }),
        ('آستانه‌ها', {
            'fields': ('target_value', 'warning_threshold', 'critical_threshold')
        }),
        ('نمایش', {
            'fields': ('format_string', 'icon', 'color_config'),
            'classes': ('collapse',)
        })
    )


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_dashboard', 'theme', 'language', 'timezone')
    list_filter = ('theme', 'language', 'timezone')
    search_fields = ('user__username', 'user__email')
    autocomplete_fields = ('user', 'default_dashboard')
    
    fieldsets = (
        ('کاربر', {
            'fields': ('user', 'default_dashboard')
        }),
        ('تنظیمات نمایش', {
            'fields': ('theme', 'language', 'timezone', 'date_format', 'number_format')
        }),
        ('تنظیمات پیشرفته', {
            'fields': ('refresh_preferences', 'notification_settings'),
            'classes': ('collapse',)
        })
    )


@admin.register(DashboardSession)
class DashboardSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'dashboard', 'start_time', 'end_time', 'session_duration')
    list_filter = ('start_time', 'end_time', 'dashboard')
    search_fields = ('user__username', 'dashboard__name')
    readonly_fields = ('session_id', 'start_time', 'end_time', 'session_duration')
    
    def session_duration(self, obj):
        if obj.end_time and obj.start_time:
            duration = obj.end_time - obj.start_time
            return f"{duration.total_seconds():.0f} ثانیه"
        return "فعال"
    session_duration.short_description = 'مدت جلسه'
    
    fieldsets = (
        ('اطلاعات جلسه', {
            'fields': ('user', 'dashboard', 'session_id')
        }),
        ('زمان‌بندی', {
            'fields': ('start_time', 'end_time', 'session_duration')
        }),
        ('جزئیات', {
            'fields': ('interactions', 'filters_applied'),
            'classes': ('collapse',)
        })
    )


# CachedData admin removed - no caching system needed
