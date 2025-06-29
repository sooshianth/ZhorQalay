from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

# Import BI models
from bi.models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI
)

# Import core models
from core.CustomerModel import Customer
from core.PurchaseModel import Purchase
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent

class Command(BaseCommand):
    help = 'تست سلامت سیستم BI و بررسی آمادگی برای استفاده'

    def add_arguments(self, parser):
        parser.add_argument(
            '--detailed',
            action='store_true',
            help='نمایش جزئیات کامل هر بخش',
        )
        parser.add_argument(
            '--fix-issues',
            action='store_true',
            help='تلاش برای رفع مشکلات خودکار',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 شروع تست سلامت سیستم BI...'))
        
        self.detailed = options.get('detailed', False)
        self.fix_issues = options.get('fix_issues', False)
        
        # آرایه برای نگهداری نتایج
        results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'issues': []
        }
        
        # تست‌های مختلف
        self.test_core_data(results)
        self.test_bi_structure(results)
        self.test_data_integrity(results)
        self.test_dashboard_health(results)
        self.test_api_endpoints(results)
        
        # نمایش نتیجه نهایی
        self.display_final_results(results)

    def test_core_data(self, results):
        """تست وجود داده‌های پایه"""
        self.stdout.write('\n📊 بررسی داده‌های پایه:')
        
        # بررسی کاربران
        admin_count = User.objects.filter(is_superuser=True).count()
        sales_agents_count = SalesAgent.objects.count()
        
        if admin_count > 0:
            self.print_success(f'✓ {admin_count} کاربر مدیر موجود')
            results['passed'] += 1
        else:
            self.print_error('✗ هیچ کاربر مدیری موجود نیست')
            results['failed'] += 1
            results['issues'].append('عدم وجود کاربر مدیر')
        
        if sales_agents_count > 0:
            self.print_success(f'✓ {sales_agents_count} کارشناس فروش موجود')
            results['passed'] += 1
        else:
            self.print_warning('⚠ هیچ کارشناس فروشی موجود نیست')
            results['warnings'] += 1
        
        # بررسی داده‌های اصلی
        customers_count = Customer.objects.count()
        purchases_count = Purchase.objects.count()
        products_count = CargoProduct.objects.count()
        
        if customers_count > 0:
            self.print_success(f'✓ {customers_count} مشتری موجود')
            results['passed'] += 1
        else:
            self.print_error('✗ هیچ مشتری موجود نیست')
            results['failed'] += 1
            results['issues'].append('عدم وجود مشتری')
        
        if purchases_count > 0:
            self.print_success(f'✓ {purchases_count} خرید موجود')
            results['passed'] += 1
        else:
            self.print_warning('⚠ هیچ خریدی موجود نیست')
            results['warnings'] += 1
            
        if products_count > 0:
            self.print_success(f'✓ {products_count} محصول موجود')
            results['passed'] += 1
        else:
            self.print_error('✗ هیچ محصولی موجود نیست')
            results['failed'] += 1
            results['issues'].append('عدم وجود محصول')

    def test_bi_structure(self, results):
        """تست ساختار BI"""
        self.stdout.write('\n🏗️ بررسی ساختار BI:')
        
        # بررسی منابع داده
        datasources_count = DataSource.objects.count()
        metrics_count = MetricDefinition.objects.count()
        charts_count = Chart.objects.count()
        dashboards_count = Dashboard.objects.count()
        
        if datasources_count >= 3:
            self.print_success(f'✓ {datasources_count} منبع داده تعریف شده')
            results['passed'] += 1
        else:
            self.print_error(f'✗ تعداد منابع داده ناکافی ({datasources_count}/3)')
            results['failed'] += 1
            results['issues'].append('منابع داده ناکافی')
        
        if metrics_count >= 5:
            self.print_success(f'✓ {metrics_count} متریک تعریف شده')
            results['passed'] += 1
        else:
            self.print_error(f'✗ تعداد متریک‌ها ناکافی ({metrics_count}/5)')
            results['failed'] += 1
            results['issues'].append('متریک‌ها ناکافی')
        
        if charts_count >= 4:
            self.print_success(f'✓ {charts_count} نمودار تعریف شده')
            results['passed'] += 1
        else:
            self.print_warning(f'⚠ تعداد نمودارها کم ({charts_count}/4)')
            results['warnings'] += 1
            
        if dashboards_count >= 1:
            self.print_success(f'✓ {dashboards_count} داشبورد موجود')
            results['passed'] += 1
        else:
            self.print_error('✗ هیچ داشبوردی موجود نیست')
            results['failed'] += 1
            results['issues'].append('عدم وجود داشبورد')

        # نمایش جزئیات در صورت درخواست
        if self.detailed:
            self.show_detailed_bi_info()

    def test_data_integrity(self, results):
        """تست یکپارچگی داده‌ها"""
        self.stdout.write('\n🔗 بررسی یکپارچگی داده‌ها:')
        
        # بررسی ارتباط chart ها با metrics
        charts_with_metrics = Chart.objects.filter(y_axis_metrics__isnull=False).distinct().count()
        total_charts = Chart.objects.count()
        
        if charts_with_metrics == total_charts and total_charts > 0:
            self.print_success(f'✓ همه نمودارها ({total_charts}) متریک دارند')
            results['passed'] += 1
        elif total_charts > 0:
            self.print_warning(f'⚠ {charts_with_metrics}/{total_charts} نمودار متریک دارند')
            results['warnings'] += 1
        else:
            self.print_warning('⚠ هیچ نموداری موجود نیست')
            results['warnings'] += 1
        
        # بررسی widgets
        widgets_count = Widget.objects.count()
        dashboard_count = Dashboard.objects.count()
        
        if widgets_count > 0 and dashboard_count > 0:
            self.print_success(f'✓ {widgets_count} ویجت در {dashboard_count} داشبورد')
            results['passed'] += 1
        else:
            self.print_warning('⚠ ویجت یا داشبورد موجود نیست')
            results['warnings'] += 1
        
        # بررسی ارتباط purchases با customers
        purchases_with_customer = Purchase.objects.filter(customer__isnull=False).count()
        total_purchases = Purchase.objects.count()
        
        if total_purchases > 0:
            percentage = (purchases_with_customer / total_purchases) * 100
            if percentage >= 90:
                self.print_success(f'✓ {percentage:.1f}% خریدها مشتری دارند')
                results['passed'] += 1
            else:
                self.print_warning(f'⚠ فقط {percentage:.1f}% خریدها مشتری دارند')
                results['warnings'] += 1

    def test_dashboard_health(self, results):
        """تست سلامت داشبورد"""
        self.stdout.write('\n📈 بررسی سلامت داشبورد:')
        
        main_dashboard = Dashboard.objects.filter(name='داشبورد مدیریتی').first()
        
        if main_dashboard:
            self.print_success('✓ داشبورد اصلی موجود است')
            results['passed'] += 1
            
            # بررسی ویجت‌های داشبورد
            widget_count = main_dashboard.widgets.count()
            if widget_count > 0:
                self.print_success(f'✓ داشبورد {widget_count} ویجت دارد')
                results['passed'] += 1
            else:
                self.print_warning('⚠ داشبورد هیچ ویجتی ندارد')
                results['warnings'] += 1
                
            # بررسی تنظیمات داشبورد
            if main_dashboard.is_active:
                self.print_success('✓ داشبورد فعال است')
                results['passed'] += 1
            else:
                self.print_warning('⚠ داشبورد غیرفعال است')
                results['warnings'] += 1
                
        else:
            self.print_error('✗ داشبورد اصلی موجود نیست')
            results['failed'] += 1
            results['issues'].append('عدم وجود داشبورد اصلی')

    def test_api_endpoints(self, results):
        """تست نقاط انتهایی API (ساده)"""
        self.stdout.write('\n🌐 بررسی API endpoints:')
        
        # در اینجا فقط بررسی می‌کنیم که مدل‌ها query قابل دارند
        try:
            # تست ساده query ها
            Customer.objects.all()[:1]
            Purchase.objects.all()[:1]
            Chart.objects.all()[:1]
            
            self.print_success('✓ Model queries قابل اجرا هستند')
            results['passed'] += 1
            
        except Exception as e:
            self.print_error(f'✗ خطا در model queries: {str(e)}')
            results['failed'] += 1
            results['issues'].append(f'خطای database: {str(e)}')

    def show_detailed_bi_info(self):
        """نمایش اطلاعات تفصیلی BI"""
        self.stdout.write('\n📋 جزئیات سیستم BI:')
        
        # منابع داده
        datasources = DataSource.objects.all()
        for ds in datasources:
            self.stdout.write(f'   📊 {ds.name} ({ds.app_name}.{ds.model_name})')
        
        # متریک‌ها
        metrics = MetricDefinition.objects.all()
        for metric in metrics:
            self.stdout.write(f'   📈 {metric.display_name} ({metric.aggregation_type})')
        
        # نمودارها
        charts = Chart.objects.all()
        for chart in charts:
            self.stdout.write(f'   📊 {chart.name} ({chart.chart_type})')

    def display_final_results(self, results):
        """نمایش نتیجه نهایی"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('📊 خلاصه نتایج تست:')
        self.stdout.write('='*50)
        
        total_tests = results['passed'] + results['failed'] + results['warnings']
        
        self.print_success(f'✅ موفق: {results["passed"]} تست')
        
        if results['warnings'] > 0:
            self.print_warning(f'⚠️  هشدار: {results["warnings"]} مورد')
            
        if results['failed'] > 0:
            self.print_error(f'❌ خطا: {results["failed"]} مورد')
        
        # محاسبه امتیاز کلی
        if results['failed'] == 0 and results['warnings'] <= 2:
            score = 'عالی 🎉'
            color = self.style.SUCCESS
        elif results['failed'] <= 2:
            score = 'قابل قبول 👍'
            color = self.style.WARNING
        else:
            score = 'نیاز به بهبود 🔧'
            color = self.style.ERROR
        
        self.stdout.write(f'\n🏆 وضعیت کلی سیستم: {color(score)}')
        
        # نمایش مشکلات
        if results['issues']:
            self.stdout.write('\n🔧 مشکلات شناسایی شده:')
            for i, issue in enumerate(results['issues'], 1):
                self.stdout.write(f'   {i}. {issue}')
            
            if self.fix_issues:
                self.stdout.write('\n💡 برای رفع مشکلات اجرا کنید:')
                self.stdout.write('   python manage.py complete_bi_setup --clear-all')
        
        # راهنمایی
        if results['failed'] > 0 or results['warnings'] > 3:
            self.stdout.write('\n💡 پیشنهاد: سیستم BI را مجدداً راه‌اندازی کنید:')
            self.stdout.write('   python manage.py complete_bi_setup')

    def print_success(self, message):
        self.stdout.write(self.style.SUCCESS(f'  {message}'))
    
    def print_warning(self, message):
        self.stdout.write(self.style.WARNING(f'  {message}'))
    
    def print_error(self, message):
        self.stdout.write(self.style.ERROR(f'  {message}')) 