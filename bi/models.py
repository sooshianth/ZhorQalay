from django.db import models
from django.contrib.auth.models import User
from django_jalali.db import models as jmodels
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import JSONField
import uuid


class DataSource(models.Model):
    """منابع داده برای BI"""
    DATASOURCE_TYPES = [
        ('model', 'مدل Django'),
        ('api', 'API خارجی'),
        ('file', 'فایل (CSV/Excel)'),
        ('database', 'پایگاه داده خارجی'),
    ]
    
    name = models.CharField("نام منبع داده", max_length=100)
    type = models.CharField("نوع منبع", max_length=20, choices=DATASOURCE_TYPES)
    model_name = models.CharField("نام مدل", max_length=100, blank=True, null=True)
    app_name = models.CharField("نام اپلیکیشن", max_length=100, blank=True, null=True)
    connection_config = JSONField("تنظیمات اتصال", default=dict, blank=True)
    description = models.TextField("توضیحات", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    created_at = jmodels.jDateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True)
    
    class Meta:
        verbose_name = "منبع داده"
        verbose_name_plural = "منابع داده"
    
    def __str__(self):
        return self.name


class MetricDefinition(models.Model):
    """تعریف شاخص‌ها و متریک‌ها"""
    AGGREGATION_TYPES = [
        ('sum', 'مجموع'),
        ('avg', 'میانگین'),
        ('count', 'تعداد'),
        ('count_distinct', 'تعداد منحصر به فرد'),
        ('min', 'حداقل'),
        ('max', 'حداکثر'),
        ('median', 'میانه'),
        ('percentage', 'درصد'),
    ]
    
    name = models.CharField("نام شاخص", max_length=100)
    display_name = models.CharField("نام نمایشی", max_length=100)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, verbose_name="منبع داده")
    field_name = models.CharField("نام فیلد", max_length=100)
    aggregation_type = models.CharField("نوع تجمیع", max_length=20, choices=AGGREGATION_TYPES)
    filter_expression = models.TextField("عبارت فیلتر", blank=True, help_text="فیلتر ORM Django")
    unit = models.CharField("واحد", max_length=50, blank=True)
    description = models.TextField("توضیحات", blank=True)
    is_active = models.BooleanField("فعال", default=True)
    
    class Meta:
        verbose_name = "تعریف شاخص"
        verbose_name_plural = "تعریف شاخص‌ها"
        unique_together = ['name', 'data_source']
    
    def __str__(self):
        return f"{self.display_name} ({self.data_source.name})"


class Dashboard(models.Model):
    """داشبورد اصلی"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("نام داشبورد", max_length=100)
    description = models.TextField("توضیحات", blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="صاحب داشبورد")
    is_public = models.BooleanField("عمومی", default=False)
    allowed_users = models.ManyToManyField(User, blank=True, related_name="shared_dashboards", verbose_name="کاربران مجاز")
    layout_config = JSONField("تنظیمات چیدمان", default=dict, help_text="تنظیمات Grid Layout")
    refresh_interval = models.IntegerField("فاصله بروزرسانی (دقیقه)", default=15)
    is_active = models.BooleanField("فعال", default=True)
    created_at = jmodels.jDateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True)
    
    class Meta:
        verbose_name = "داشبورد"
        verbose_name_plural = "داشبوردها"
    
    def __str__(self):
        return self.name


class Chart(models.Model):
    """نمودارها"""
    CHART_TYPES = [
        ('line', 'نمودار خطی'),
        ('bar', 'نمودار ستونی'),
        ('pie', 'نمودار دایره‌ای'),
        ('doughnut', 'نمودار حلقه‌ای'),
        ('area', 'نمودار ناحیه‌ای'),
        ('scatter', 'نمودار پراکندگی'),
        ('heatmap', 'نقشه حرارتی'),
        ('map_iran', 'نقشه ایران'),
        ('gauge', 'سنج'),
        ('funnel', 'قیف'),
        ('radar', 'رادار'),
        ('bubble', 'حبابی'),
        ('treemap', 'نقشه درختی'),
        ('sankey', 'سنکی'),
        ('table', 'جدول'),
        ('kpi_card', 'کارت KPI'),
        # نمودارهای تخصصی ژورقالای
        ('purchase_timeline', 'خط زمانی خریدها'),
        ('customer_activity', 'فعالیت مشتریان'),
        ('product_performance', 'عملکرد محصولات'),
        ('barnameh_status', 'وضعیت بارنامه‌ها'),
        ('sales_agent_comparison', 'مقایسه کارشناسان فروش'),
    ]
    
    TIME_PERIODS = [
        ('hour', 'ساعتی'),
        ('day', 'روزانه'),
        ('week', 'هفتگی'),
        ('month', 'ماهانه'),
        ('quarter', 'سه‌ماهه'),
        ('year', 'سالانه'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("نام نمودار", max_length=100)
    chart_type = models.CharField("نوع نمودار", max_length=30, choices=CHART_TYPES)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, verbose_name="منبع داده")
    x_axis_field = models.CharField("فیلد محور X", max_length=100)
    y_axis_metrics = models.ManyToManyField(MetricDefinition, verbose_name="شاخص‌های محور Y")
    group_by_field = models.CharField("گروه‌بندی بر اساس", max_length=100, blank=True)
    time_period = models.CharField("دوره زمانی", max_length=20, choices=TIME_PERIODS, blank=True)
    chart_config = JSONField("تنظیمات نمودار", default=dict, help_text="تنظیمات Chart.js یا سایر کتابخانه‌ها")
    drill_down_config = JSONField("تنظیمات Drill Down", default=dict, blank=True)
    filters = JSONField("فیلترهای پیش‌فرض", default=list, blank=True)
    is_real_time = models.BooleanField("بروزرسانی لحظه‌ای", default=False)
    created_at = jmodels.jDateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True)
    
    class Meta:
        verbose_name = "نمودار"
        verbose_name_plural = "نمودارها"
    
    def __str__(self):
        return f"{self.name} ({self.get_chart_type_display()})"


class Widget(models.Model):
    """ویجت‌های داشبورد"""
    WIDGET_SIZES = [
        ('small', 'کوچک (1x1)'),
        ('medium', 'متوسط (2x1)'),
        ('large', 'بزرگ (2x2)'),
        ('wide', 'پهن (3x1)'),
        ('tall', 'بلند (1x3)'),
        ('xl', 'خیلی بزرگ (3x2)'),
        ('full', 'تمام عرض (4x2)'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets", verbose_name="داشبورد")
    chart = models.ForeignKey(Chart, on_delete=models.CASCADE, verbose_name="نمودار")
    title = models.CharField("عنوان", max_length=100)
    size = models.CharField("اندازه", max_length=20, choices=WIDGET_SIZES, default='medium')
    position_x = models.IntegerField("موقعیت X", default=0)
    position_y = models.IntegerField("موقعیت Y", default=0)
    width = models.IntegerField("عرض", default=2)
    height = models.IntegerField("ارتفاع", default=2)
    widget_config = JSONField("تنظیمات ویجت", default=dict)
    is_visible = models.BooleanField("نمایش", default=True)
    order = models.IntegerField("ترتیب", default=0)
    
    class Meta:
        verbose_name = "ویجت"
        verbose_name_plural = "ویجت‌ها"
        ordering = ['order', 'position_y', 'position_x']
    
    def __str__(self):
        return f"{self.title} - {self.dashboard.name}"


class Report(models.Model):
    """گزارش‌های تفصیلی"""
    REPORT_TYPES = [
        ('tabular', 'جدولی'),
        ('chart', 'نموداری'),
        ('mixed', 'ترکیبی'),
        ('pivot', 'جدول محوری'),
    ]
    
    EXPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("نام گزارش", max_length=100)
    description = models.TextField("توضیحات", blank=True)
    report_type = models.CharField("نوع گزارش", max_length=20, choices=REPORT_TYPES)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, verbose_name="منبع داده")
    columns = JSONField("ستون‌ها", default=list, help_text="تعریف ستون‌های گزارش")
    filters = JSONField("فیلترها", default=list)
    grouping = JSONField("گروه‌بندی", default=list, blank=True)
    sorting = JSONField("مرتب‌سازی", default=list, blank=True)
    aggregations = JSONField("تجمیع‌ها", default=list, blank=True)
    export_formats = models.JSONField("فرمت‌های خروجی", default=list)
    is_scheduled = models.BooleanField("زمان‌بندی شده", default=False)
    schedule_config = JSONField("تنظیمات زمان‌بندی", default=dict, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="صاحب گزارش")
    is_public = models.BooleanField("عمومی", default=False)
    created_at = jmodels.jDateTimeField("تاریخ ایجاد", auto_now_add=True)
    updated_at = jmodels.jDateTimeField("تاریخ بروزرسانی", auto_now=True)
    
    class Meta:
        verbose_name = "گزارش"
        verbose_name_plural = "گزارش‌ها"
    
    def __str__(self):
        return self.name


class Filter(models.Model):
    """فیلترهای دینامیک"""
    FILTER_TYPES = [
        ('text', 'متن'),
        ('number', 'عدد'),
        ('date', 'تاریخ'),
        ('datetime', 'تاریخ و زمان'),
        ('select', 'انتخابی'),
        ('multiselect', 'چند انتخابی'),
        ('range', 'محدوده'),
        ('boolean', 'بولین'),
    ]
    
    OPERATORS = [
        ('eq', 'مساوی'),
        ('ne', 'نامساوی'),
        ('gt', 'بزرگتر از'),
        ('gte', 'بزرگتر مساوی'),
        ('lt', 'کوچکتر از'),
        ('lte', 'کوچکتر مساوی'),
        ('contains', 'شامل'),
        ('startswith', 'شروع با'),
        ('endswith', 'پایان با'),
        ('in', 'در لیست'),
        ('between', 'بین'),
        ('isnull', 'خالی'),
        ('isnotnull', 'غیر خالی'),
    ]
    
    name = models.CharField("نام فیلتر", max_length=100)
    display_name = models.CharField("نام نمایشی", max_length=100)
    data_source = models.ForeignKey(DataSource, on_delete=models.CASCADE, verbose_name="منبع داده")
    field_name = models.CharField("نام فیلد", max_length=100)
    filter_type = models.CharField("نوع فیلتر", max_length=20, choices=FILTER_TYPES)
    default_operator = models.CharField("عملگر پیش‌فرض", max_length=20, choices=OPERATORS, default='eq')
    options = JSONField("گزینه‌ها", default=list, blank=True, help_text="برای فیلترهای انتخابی")
    default_value = JSONField("مقدار پیش‌فرض", default=None, blank=True, null=True)
    is_required = models.BooleanField("اجباری", default=False)
    validation_rules = JSONField("قوانین اعتبارسنجی", default=dict, blank=True)
    
    class Meta:
        verbose_name = "فیلتر"
        verbose_name_plural = "فیلترها"
        unique_together = ['name', 'data_source']
    
    def __str__(self):
        return f"{self.display_name} ({self.data_source.name})"


class KPI(models.Model):
    """شاخص‌های کلیدی عملکرد"""
    KPI_TYPES = [
        ('number', 'عددی'),
        ('percentage', 'درصدی'),
        ('currency', 'پولی'),
        ('ratio', 'نسبت'),
        ('score', 'امتیاز'),
    ]
    
    TREND_TYPES = [
        ('up_good', 'افزایش مثبت'),
        ('up_bad', 'افزایش منفی'),
        ('down_good', 'کاهش مثبت'),
        ('down_bad', 'کاهش منفی'),
        ('neutral', 'خنثی'),
    ]
    
    name = models.CharField("نام KPI", max_length=100)
    display_name = models.CharField("نام نمایشی", max_length=100)
    description = models.TextField("توضیحات", blank=True)
    metric = models.ForeignKey(MetricDefinition, on_delete=models.CASCADE, verbose_name="شاخص")
    target_value = models.DecimalField("مقدار هدف", max_digits=15, decimal_places=2, null=True, blank=True)
    warning_threshold = models.DecimalField("آستانه هشدار", max_digits=15, decimal_places=2, null=True, blank=True)
    critical_threshold = models.DecimalField("آستانه بحرانی", max_digits=15, decimal_places=2, null=True, blank=True)
    kpi_type = models.CharField("نوع KPI", max_length=20, choices=KPI_TYPES)
    trend_type = models.CharField("نوع روند", max_length=20, choices=TREND_TYPES, default='neutral')
    comparison_period = models.CharField("دوره مقایسه", max_length=50, default='month')
    format_string = models.CharField("فرمت نمایش", max_length=50, default='{value}')
    icon = models.CharField("آیکون", max_length=50, blank=True)
    color_config = JSONField("تنظیمات رنگ", default=dict, blank=True)
    is_active = models.BooleanField("فعال", default=True)
    
    class Meta:
        verbose_name = "KPI"
        verbose_name_plural = "KPI ها"
    
    def __str__(self):
        return self.display_name


class UserPreference(models.Model):
    """ترجیحات کاربر برای داشبورد"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="کاربر")
    default_dashboard = models.ForeignKey(Dashboard, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="داشبورد پیش‌فرض")
    theme = models.CharField("تم", max_length=20, default='light', choices=[
        ('light', 'روشن'),
        ('dark', 'تاریک'),
        ('auto', 'خودکار'),
    ])
    language = models.CharField("زبان", max_length=10, default='fa')
    timezone = models.CharField("منطقه زمانی", max_length=50, default='Asia/Tehran')
    date_format = models.CharField("فرمت تاریخ", max_length=20, default='jY/jm/jd')
    number_format = models.CharField("فرمت عدد", max_length=20, default='en')
    refresh_preferences = JSONField("ترجیحات بروزرسانی", default=dict)
    notification_settings = JSONField("تنظیمات اعلان", default=dict)
    
    class Meta:
        verbose_name = "ترجیحات کاربر"
        verbose_name_plural = "ترجیحات کاربران"
    
    def __str__(self):
        return f"ترجیحات {self.user.username}"


class DashboardSession(models.Model):
    """جلسات داشبورد برای ردیابی عملکرد"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="کاربر")
    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, verbose_name="داشبورد")
    session_id = models.UUIDField(default=uuid.uuid4)
    start_time = jmodels.jDateTimeField("زمان شروع", auto_now_add=True)
    end_time = jmodels.jDateTimeField("زمان پایان", null=True, blank=True)
    interactions = JSONField("تعاملات", default=list, blank=True)
    filters_applied = JSONField("فیلترهای اعمال شده", default=dict, blank=True)
    
    class Meta:
        verbose_name = "جلسه داشبورد"
        verbose_name_plural = "جلسات داشبورد"
    
    def __str__(self):
        return f"{self.user.username} - {self.dashboard.name} - {self.start_time}"


# Caching models removed - focusing on charts and analytics only
