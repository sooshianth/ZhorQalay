from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.apps import apps
from bi.models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI
)
import uuid


class Command(BaseCommand):
    help = 'راه‌اندازی اولیه سیستم BI - ایجاد منابع داده، متریک‌ها و داشبورد نمونه'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample-data',
            action='store_true',
            help='ایجاد داده‌های نمونه',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 شروع راه‌اندازی سیستم BI...'))
        
        # ایجاد منابع داده
        self.create_data_sources()
        
        # ایجاد متریک‌ها
        self.create_metrics()
        
        # ایجاد فیلترها
        self.create_filters()
        
        # ایجاد نمودارها
        self.create_charts()
        
        # ایجاد KPI ها
        self.create_kpis()
        
        # ایجاد داشبورد نمونه
        self.create_sample_dashboard()
        
        # ایجاد گزارش‌های نمونه
        self.create_sample_reports()
        
        if options['create_sample_data']:
            self.create_sample_data()
        
        self.stdout.write(self.style.SUCCESS('✅ راه‌اندازی سیستم BI با موفقیت انجام شد!'))

    def create_data_sources(self):
        """ایجاد منابع داده اصلی"""
        self.stdout.write('📊 ایجاد منابع داده...')
        
        data_sources = [
            {
                'name': 'مشتریان',
                'app_name': 'core',
                'model_name': 'Customer',
                'description': 'اطلاعات کامل مشتریان شامل داده‌های تماس و ترجیحات'
            },
            {
                'name': 'خریدها',
                'app_name': 'core', 
                'model_name': 'Purchase',
                'description': 'تمام خریدهای انجام شده توسط مشتریان'
            },
            {
                'name': 'محصولات',
                'app_name': 'core',
                'model_name': 'CargoProduct',
                'description': 'کوتاژها و محصولات موجود'
            },
            {
                'name': 'بارنامه‌ها',
                'app_name': 'bki_barnameh',
                'model_name': 'Barnameh',
                'description': 'بارنامه‌های صادر شده'
            }
        ]
        
        for ds_data in data_sources:
            data_source, created = DataSource.objects.get_or_create(
                name=ds_data['name'],
                defaults={
                    'type': 'model',
                    'app_name': ds_data['app_name'],
                    'model_name': ds_data['model_name'],
                    'description': ds_data['description'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  ✓ منبع داده "{ds_data["name"]}" ایجاد شد')

    def create_metrics(self):
        """ایجاد متریک‌های اصلی"""
        self.stdout.write('📈 ایجاد متریک‌ها...')
        
        # دریافت منابع داده
        customer_ds = DataSource.objects.get(name='مشتریان')
        purchase_ds = DataSource.objects.get(name='خریدها')
        product_ds = DataSource.objects.get(name='محصولات')
        barnameh_ds = DataSource.objects.get(name='بارنامه‌ها')
        
        metrics = [
            # متریک‌های مشتری
            {
                'name': 'total_customers',
                'display_name': 'تعداد کل مشتریان',
                'data_source': customer_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل مشتریان ثبت شده در سیستم'
            },
            {
                'name': 'active_customers',
                'display_name': 'مشتریان فعال',
                'data_source': customer_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'filter_expression': {'is_active': True},
                'description': 'تعداد مشتریان فعال'
            },
            
            # متریک‌های خرید
            {
                'name': 'total_purchases',
                'display_name': 'تعداد کل خریدها',
                'data_source': purchase_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل خریدهای انجام شده'
            },
            {
                'name': 'total_sales_amount',
                'display_name': 'مجموع فروش',
                'data_source': purchase_ds,
                'field_name': 'amount_paid',
                'aggregation_type': 'sum',
                'unit': 'ریال',
                'description': 'مجموع مبلغ فروش‌های انجام شده'
            },
            {
                'name': 'average_order_value',
                'display_name': 'میانگین ارزش سفارش',
                'data_source': purchase_ds,
                'field_name': 'amount_paid',
                'aggregation_type': 'avg',
                'unit': 'ریال',
                'description': 'میانگین ارزش هر سفارش'
            },
            {
                'name': 'total_weight_sold',
                'display_name': 'کل وزن فروخته شده',
                'data_source': purchase_ds,
                'field_name': 'order_weight',
                'aggregation_type': 'sum',
                'unit': 'کیلوگرم',
                'description': 'مجموع وزن محصولات فروخته شده'
            },
            
            # متریک‌های محصول
            {
                'name': 'total_products',
                'display_name': 'تعداد کل محصولات',
                'data_source': product_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل کوتاژهای موجود'
            },
            {
                'name': 'available_inventory',
                'display_name': 'موجودی قابل فروش',
                'data_source': product_ds,
                'field_name': 'weight',
                'aggregation_type': 'sum',
                'unit': 'کیلوگرم',
                'filter_expression': {'status': True},
                'description': 'مجموع وزن محصولات قابل فروش'
            },
            
            # متریک‌های بارنامه
            {
                'name': 'total_barnamehs',
                'display_name': 'تعداد بارنامه‌ها',
                'data_source': barnameh_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'description': 'تعداد کل بارنامه‌های صادر شده'
            },
            {
                'name': 'completed_barnamehs',
                'display_name': 'بارنامه‌های کامل',
                'data_source': barnameh_ds,
                'field_name': 'id',
                'aggregation_type': 'count',
                'filter_expression': {'status': 'BARNAMEH_COMPLETE'},
                'description': 'تعداد بارنامه‌های کامل شده'
            }
        ]
        
        for metric_data in metrics:
            metric, created = MetricDefinition.objects.get_or_create(
                name=metric_data['name'],
                defaults=metric_data
            )
            if created:
                self.stdout.write(f'  ✓ متریک "{metric_data["display_name"]}" ایجاد شد')

    def create_filters(self):
        """ایجاد فیلترهای اصلی"""
        self.stdout.write('🔍 ایجاد فیلترها...')
        
        customer_ds = DataSource.objects.get(name='مشتریان')
        purchase_ds = DataSource.objects.get(name='خریدها')
        product_ds = DataSource.objects.get(name='محصولات')
        
        filters = [
            {
                'name': 'city_filter',
                'display_name': 'شهر',
                'data_source': customer_ds,
                'field_name': 'city',
                'filter_type': 'select',
                'default_operator': 'eq'
            },
            {
                'name': 'purchase_state_filter',
                'display_name': 'وضعیت خرید',
                'data_source': purchase_ds,
                'field_name': 'state',
                'filter_type': 'select',
                'default_operator': 'eq'
            },
            {
                'name': 'product_type_filter',
                'display_name': 'نوع محصول',
                'data_source': product_ds,
                'field_name': 'product_type',
                'filter_type': 'select',
                'default_operator': 'eq'
            },
            {
                'name': 'date_range_filter',
                'display_name': 'بازه زمانی',
                'data_source': purchase_ds,
                'field_name': 'created_at',
                'filter_type': 'date_range',
                'default_operator': 'between'
            }
        ]
        
        for filter_data in filters:
            filter_obj, created = Filter.objects.get_or_create(
                name=filter_data['name'],
                defaults=filter_data
            )
            if created:
                self.stdout.write(f'  ✓ فیلتر "{filter_data["display_name"]}" ایجاد شد')

    def create_charts(self):
        """ایجاد نمودارهای اصلی"""
        self.stdout.write('📊 ایجاد نمودارها...')
        
        purchase_ds = DataSource.objects.get(name='خریدها')
        customer_ds = DataSource.objects.get(name='مشتریان')
        product_ds = DataSource.objects.get(name='محصولات')
        
        # دریافت متریک‌ها
        total_sales = MetricDefinition.objects.get(name='total_sales_amount')
        total_purchases = MetricDefinition.objects.get(name='total_purchases')
        total_weight = MetricDefinition.objects.get(name='total_weight_sold')
        
        charts = [
            {
                'name': 'فروش ماهانه',
                'chart_type': 'line',
                'data_source': purchase_ds,
                'x_axis_field': 'created_at',
                'time_period': 'month',
                'metrics': [total_sales]
            },
            {
                'name': 'تعداد خریدها در هر شهر',
                'chart_type': 'bar',
                'data_source': purchase_ds,
                'x_axis_field': 'customer__city',
                'group_by_field': 'customer__city',
                'metrics': [total_purchases]
            },
            {
                'name': 'توزیع نوع محصولات',
                'chart_type': 'pie',
                'data_source': purchase_ds,
                'x_axis_field': 'cargo__product_type',
                'group_by_field': 'cargo__product_type',
                'metrics': [total_weight]
            },
            {
                'name': 'نقشه فروش استان‌ها',
                'chart_type': 'map_iran',
                'data_source': customer_ds,
                'x_axis_field': 'city',
                'group_by_field': 'city',
                'metrics': [total_purchases]
            }
        ]
        
        for chart_data in charts:
            metrics = chart_data.pop('metrics')
            chart, created = Chart.objects.get_or_create(
                name=chart_data['name'],
                defaults=chart_data
            )
            if created:
                chart.y_axis_metrics.set(metrics)
                self.stdout.write(f'  ✓ نمودار "{chart_data["name"]}" ایجاد شد')

    def create_kpis(self):
        """ایجاد KPI های اصلی"""
        self.stdout.write('🎯 ایجاد KPI ها...')
        
        # دریافت متریک‌ها
        total_sales = MetricDefinition.objects.get(name='total_sales_amount')
        total_customers = MetricDefinition.objects.get(name='total_customers')
        avg_order = MetricDefinition.objects.get(name='average_order_value')
        
        kpis = [
            {
                'name': 'monthly_sales_kpi',
                'display_name': 'فروش ماهانه',
                'metric': total_sales,
                'kpi_type': 'revenue',
                'target_value': 1000000000,  # 1 میلیارد ریال
                'warning_threshold': 800000000,
                'critical_threshold': 500000000,
                'comparison_period': 'month'
            },
            {
                'name': 'customer_growth_kpi',
                'display_name': 'رشد مشتریان',
                'metric': total_customers,
                'kpi_type': 'growth',
                'target_value': 1000,
                'warning_threshold': 800,
                'critical_threshold': 600,
                'comparison_period': 'month'
            },
            {
                'name': 'average_order_kpi',
                'display_name': 'میانگین ارزش سفارش',
                'metric': avg_order,
                'kpi_type': 'performance',
                'target_value': 50000000,  # 50 میلیون ریال
                'warning_threshold': 30000000,
                'critical_threshold': 20000000,
                'comparison_period': 'week'
            }
        ]
        
        for kpi_data in kpis:
            kpi, created = KPI.objects.get_or_create(
                name=kpi_data['name'],
                defaults=kpi_data
            )
            if created:
                self.stdout.write(f'  ✓ KPI "{kpi_data["display_name"]}" ایجاد شد')

    def create_sample_dashboard(self):
        """ایجاد داشبورد نمونه"""
        self.stdout.write('🏠 ایجاد داشبورد نمونه...')
        
        # دریافت یا ایجاد کاربر admin
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
        
        # ایجاد داشبورد
        dashboard, created = Dashboard.objects.get_or_create(
            name='داشبورد مدیریتی',
            defaults={
                'description': 'داشبورد اصلی برای مدیریت و کنترل عملکرد',
                'owner': admin_user,
                'is_public': True,
                'refresh_interval': 300,  # 5 دقیقه
                'layout_config': {
                    'grid_cols': 12,
                    'grid_rows': 8,
                    'compact_type': 'vertical'
                }
            }
        )
        
        if created:
            # اضافه کردن نمودارها به داشبورد
            charts = Chart.objects.all()
            for i, chart in enumerate(charts):
                Widget.objects.create(
                    dashboard=dashboard,
                    chart=chart,
                    title=chart.name,
                    size='medium',
                    position_x=(i % 3) * 4,
                    position_y=(i // 3) * 3,
                    width=4,
                    height=3,
                    order=i
                )
            
            self.stdout.write('  ✓ داشبورد مدیریتی ایجاد شد')

    def create_sample_reports(self):
        """ایجاد گزارش‌های نمونه"""
        self.stdout.write('📋 ایجاد گزارش‌های نمونه...')
        
        admin_user = User.objects.filter(is_superuser=True).first()
        purchase_ds = DataSource.objects.get(name='خریدها')
        customer_ds = DataSource.objects.get(name='مشتریان')
        
        reports = [
            {
                'name': 'گزارش فروش ماهانه',
                'report_type': 'table',
                'data_source': purchase_ds,
                'owner': admin_user,
                'description': 'گزارش تفصیلی فروش‌های ماهانه',
                'columns': [
                    {'field': 'created_at', 'title': 'تاریخ'},
                    {'field': 'customer__name', 'title': 'نام مشتری'},
                    {'field': 'amount_paid', 'title': 'مبلغ'},
                    {'field': 'order_weight', 'title': 'وزن'}
                ],
                'grouping': ['created_at__month'],
                'sorting': [{'field': 'created_at', 'direction': 'desc'}],
                'is_scheduled': True,
                'schedule_config': {'frequency': 'monthly'},
                'export_formats': ['excel', 'pdf']
            },
            {
                'name': 'گزارش مشتریان',
                'report_type': 'table',
                'data_source': customer_ds,
                'owner': admin_user,
                'description': 'گزارش اطلاعات مشتریان',
                'columns': [
                    {'field': 'name', 'title': 'نام'},
                    {'field': 'city', 'title': 'شهر'},
                    {'field': 'created_at', 'title': 'تاریخ ثبت'}
                ],
                'sorting': [{'field': 'created_at', 'direction': 'desc'}]
            }
        ]
        
        for report_data in reports:
            report, created = Report.objects.get_or_create(
                name=report_data['name'],
                defaults=report_data
            )
            if created:
                self.stdout.write(f'  ✓ گزارش "{report_data["name"]}" ایجاد شد')

    def create_sample_data(self):
        """ایجاد داده‌های نمونه برای تست"""
        self.stdout.write('🧪 ایجاد داده‌های نمونه...')
        
        # این قسمت در صورت نیاز می‌توان داده‌های تستی ایجاد کرد
        self.stdout.write('  ℹ️  داده‌های نمونه در نسخه‌های بعدی اضافه خواهد شد') 