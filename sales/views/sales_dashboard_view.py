from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from core._models import Customer, Purchase
import logging
import json
import os

logger = logging.getLogger(__name__)

file_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'iran_cities_fa.json')
with open(file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

def normalize_city_name(city_name):
    # تبدیل "ی" عربی به "ی" فارسی و حذف فاصله‌ها
    city_name = city_name.replace('ي', 'ی').strip().replace(' ', '').lower()
    return city_name

def find_province_by_city(target_city):
    target_city = normalize_city_name(target_city)  # نرمال‌سازی نام شهر هدف
    print(f"جستجو برای شهر: {target_city}")
    for province in data:
        for city in province['cities']:
            city_name = normalize_city_name(city['name'])  # نرمال‌سازی نام شهر از JSON
            if city_name == target_city:
                print(f"شهر {target_city} در استان {province['name']} یافت شد.")
                return province['name']
    print(f"شهر {target_city} یافت نشد.")
    return None

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from django.core.cache import cache
import logging

def calculate_ml_prediction(sales_agent, monthly_sales):
    # کش برای کاهش بار محاسباتی
    cache_key = f"sales_pred_{sales_agent.id}_{monthly_sales[-1]['month']}"
    cached_pred = cache.get(cache_key)
    if cached_pred:
        return cached_pred
    
    try:
        # آماده‌سازی داده‌های آموزشی
        X = []
        y = []
        
        # ساخت ویژگی‌های مبتنی بر توالی زمانی
        for i in range(1, len(monthly_sales)):
            prev_month = monthly_sales[i-1]
            current_month = monthly_sales[i]
            
            # ویژگی‌ها: ماه قبل، میانگین متحرک ۳ ماهه، روند
            features = [
                prev_month['sales'],  # فروش ماه قبل
                np.mean([m['sales'] for m in monthly_sales[max(0,i-3):i]]),  # میانگین ۳ ماهه
                i  # روند زمانی
            ]
            
            X.append(features)
            y.append(current_month['sales'])
        
        if len(X) < 3:
            raise ValueError("داده کافی برای آموزش مدل وجود ندارد")
        
        # آموزش مدل جنگل تصادفی
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        # پیش‌بینی برای ماه بعد
        last_month_features = [
            monthly_sales[-1]['sales'],  # آخرین فروش
            np.mean([m['sales'] for m in monthly_sales[-3:]]),  # میانگین ۳ ماه آخر
            len(monthly_sales)  # ادامه روند
        ]
        
        prediction = model.predict([last_month_features])[0]
        
        # ذخیره در کش به مدت ۱ هفته
        cache.set(cache_key, prediction, 604800)
        return prediction
        
    except Exception as e:
        logger.error(f"خطا در پیش‌بینی هوش مصنوعی: {str(e)}")
        # فال‌بک به میانگین ساده در صورت خطا
        return np.mean([m['sales'] for m in monthly_sales]) if monthly_sales else 0

@login_required
def sales_dashboard_view(request):
    if not hasattr(request.user, 'sales_agent'):
        logger.warning(f"Unauthorized access attempt by user {request.user.username}")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent
    today = timezone.now()

    # داده‌های فروش برای 6 ماه گذشته
    monthly_sales = []
    for i in range(6):  # 6 ماه گذشته شامل ماه جاری
        # محاسبه شروع و پایان ماه
        month_date = today - timedelta(days=i * 30)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=31)).replace(day=1) - timedelta(seconds=1)

        # استفاده از متد جدید get_sales_in_period
        sales = sales_agent.get_sales_in_period(start_date=month_start, end_date=month_end)
        sales_weight = sum(purchase.weight for purchase in sales)

        monthly_sales.append({
            'month': month_start.strftime('%Y-%m'),
            'sales': sales_weight
        })

    # پیش‌بینی فروش ماه بعد با استفاده از متد forecast_sales
    try:
        # استفاده از پیش‌بینی پیشرفته اگر در دسترس باشد
        forecast_data = sales_agent.forecast_sales(days_ahead=30)
        sales_prediction = forecast_data['total_forecast']
        forecast_confidence = forecast_data['confidence']
    except Exception as e:
        logger.error(f"Error using forecast_sales: {str(e)}")
        # فال‌بک به روش قبلی
        sales_prediction = calculate_ml_prediction(sales_agent, monthly_sales)
        forecast_confidence = 70  # مقدار پیش‌فرض
    
    # تعداد مشتریان جدید این ماه
    new_customers_this_month = Customer.objects.filter(
        sales_agent=sales_agent,
        created_at__month=today.month  # مشتریان ایجاد شده در این ماه
    ).count()

    # محاسبه خریدها بر اساس استان
    province_purchases = defaultdict(int)
    purchases_this_month = Purchase.objects.filter(
        customer__sales_agent=sales_agent,
    )

    for purchase in purchases_this_month:
        city = purchase.customer.city
        if city:
            province = find_province_by_city(city)
            if province:
                province_purchases[province] += 1

    # استفاده از متد جدید get_this_month_sales_stats برای آمار فروش ماه جاری
    sales_stats = sales_agent.get_this_month_sales_stats()
    
    # استفاده از متد جدید get_sales_by_product برای آمار فروش بر اساس محصول
    product_sales = sales_agent.get_sales_by_product()

    context = {
        'sales_agent': sales_agent,
        'new_customers_this_month': new_customers_this_month,
        'province_purchases': dict(province_purchases),
        'monthly_sales': monthly_sales[::-1],  # معکوس برای نمایش از قدیم به جدید
        'task_stats': {
            'pending': len(sales_agent.get_all_undone_tasks()),
            'completed': len([task for task in sales_agent.get_all_tasks() if task.status]),
            'overdue': len(sales_agent.get_overdue_tasks())
        },
        'sales_prediction': round(sales_prediction, 2),
        'forecast_confidence': round(forecast_confidence, 1),
        'sales_stats': sales_stats,
        'product_sales': product_sales,
        'target_achievement': round(sales_stats['target_achievement'], 1),
    }
    return render(request, 'sales_dashboard.html', context)
