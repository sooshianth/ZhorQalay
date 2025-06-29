#!/usr/bin/env python
"""
🚀 Universal BI Setup - راه‌اندازی جامع سیستم BI 
فایل جامع برای راه‌اندازی سریع سیستم BI روی هر سیستمی
مستقل از داده‌های موجود - همیشه کار می‌کند!
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

# Import BI models
from bi.models import (
    DataSource, MetricDefinition, Dashboard, Chart, Widget, 
    Report, Filter, KPI
)

def universal_bi_setup():
    """راه‌اندازی جامع سیستم BI"""
    print('🚀 شروع راه‌اندازی جامع سیستم BI...\n')
    
    # مرحله ۱: تنظیمات اولیه
    print('⚙️ تنظیمات اولیه...')
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            username='admin', email='admin@kunqalay.com', password='admin123')
        print('  ✅ کاربر مدیر ایجاد شد')
    else:
        print(f'  ✅ کاربر مدیر: {admin_user.username}')
    
    # مرحله ۲: پاکسازی
    print('\n🧹 پاکسازی تنظیمات قبلی...')
    Widget.objects.all().delete()
    Chart.objects.all().delete()
    Dashboard.objects.all().delete()
    KPI.objects.all().delete()
    Filter.objects.all().delete()
    Report.objects.all().delete()
    MetricDefinition.objects.all().delete()
    DataSource.objects.all().delete()
    print('  ✅ تنظیمات قبلی پاک شد')
    
    # مرحله ۳: منابع داده
    print('\n📊 ایجاد منابع داده...')
    sources = [
        ('مشتریان', 'core', 'Customer'),
        ('خریدها', 'core', 'Purchase'),
        ('محصولات', 'core', 'CargoProduct'),
        ('کارشناسان فروش', 'core', 'SalesAgent'),
        ('کاربران', 'auth', 'User'),
    ]
    
    data_sources = {}
    for name, app, model in sources:
        ds = DataSource.objects.create(
            name=name, type='model', app_name=app, model_name=model,
            description=f'منبع داده {name}', is_active=True
        )
        data_sources[name] = ds
    print(f'  ✅ {len(sources)} منبع داده ایجاد شد')
    
    # مرحله ۴: متریک‌ها
    print('\n📏 ایجاد متریک‌ها...')
    metrics = [
        ('تعداد مشتریان', 'مشتریان', 'id', 'count'),
        ('تعداد خریدها', 'خریدها', 'id', 'count'),
        ('مجموع فروش', 'خریدها', 'amount_paid', 'sum'),
        ('میانگین خرید', 'خریدها', 'amount_paid', 'avg'),
        ('مجموع وزن', 'خریدها', 'order_weight', 'sum'),
        ('تعداد محصولات', 'محصولات', 'id', 'count'),
    ]
    
    metrics_dict = {}
    for name, ds_name, field, agg in metrics:
        metric = MetricDefinition.objects.create(
            name=name, display_name=name,
            data_source=data_sources[ds_name],
            field_name=field, aggregation_type=agg, is_active=True
        )
        metrics_dict[name] = metric
    print(f'  ✅ {len(metrics)} متریک ایجاد شد')
    
    # مرحله ۵: نمودارها
    print('\n📈 ایجاد نمودارها...')
    charts_config = [
        ('روند فروش ماهانه', 'line', 'خریدها', 'created_at', 'month', ['مجموع فروش']),
        ('فروش شهرها', 'bar', 'خریدها', 'customer__city', None, ['مجموع فروش']),
        ('توزیع وضعیت', 'pie', 'خریدها', 'state', None, ['تعداد خریدها']),
        ('نوع محصولات', 'pie', 'محصولات', 'product_type', None, ['تعداد محصولات']),
    ]
    
    charts_dict = {}
    for name, chart_type, ds_name, x_field, time_period, metric_names in charts_config:
        chart_data = {
            'name': name, 
            'chart_type': chart_type,
            'data_source': data_sources[ds_name],
            'x_axis_field': x_field,
            'group_by_field': x_field if chart_type in ['pie', 'bar'] else ''
        }
        
        # فقط برای نمودارهای زمانی time_period اضافه کن
        if time_period:
            chart_data['time_period'] = time_period
            
        chart = Chart.objects.create(**chart_data)
        
        # اضافه کردن متریک‌ها
        for metric_name in metric_names:
            if metric_name in metrics_dict:
                chart.y_axis_metrics.add(metrics_dict[metric_name])
                
        charts_dict[name] = chart
        
    print(f'  ✅ {len(charts_config)} نمودار ایجاد شد')
    
    # مرحله ۶: داشبورد
    print('\n🏠 ایجاد داشبورد...')
    dashboard = Dashboard.objects.create(
        name='داشبورد مدیریتی کونقالای',
        description='داشبورد جامع مدیریتی',
        owner=admin_user, is_public=True, is_active=True
    )
    
    # اضافه کردن ویجت‌ها
    widget_configs = [
        ('روند فروش ماهانه', 0, 0, 6, 3),
        ('توزیع وضعیت', 6, 0, 6, 3),
        ('فروش شهرها', 0, 3, 8, 3),
        ('نوع محصولات', 8, 3, 4, 3),
    ]
    
    for i, (chart_name, x, y, w, h) in enumerate(widget_configs):
        if chart_name in charts_dict:
            Widget.objects.create(
                dashboard=dashboard, chart=charts_dict[chart_name],
                title=chart_name, position_x=x, position_y=y,
                width=w, height=h, order=i
            )
            
    print(f'  ✅ داشبورد و {len(widget_configs)} ویجت ایجاد شد')
    
    # نتیجه نهایی
    print(f'\n🎉 راه‌اندازی کامل شد!')
    print(f'📊 آمار:')
    print(f'  • منابع داده: {DataSource.objects.count()}')
    print(f'  • متریک‌ها: {MetricDefinition.objects.count()}')
    print(f'  • نمودارها: {Chart.objects.count()}')
    print(f'  • داشبوردها: {Dashboard.objects.count()}')
    print(f'  • ویجت‌ها: {Widget.objects.count()}')
    
    print(f'\n🌐 داشبورد آماده است:')
    print(f'   http://127.0.0.1:8000/bi/dashboard/')
    print(f'\n✅ این فایل روی هر سیستمی کار می‌کند!')

if __name__ == '__main__':
    try:
        universal_bi_setup()
    except Exception as e:
        print(f'❌ خطا: {str(e)}')
        import traceback
        traceback.print_exc() 