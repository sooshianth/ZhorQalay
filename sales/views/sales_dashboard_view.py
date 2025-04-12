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

        # جمع وزن فروش‌های هر ماه
        sales_weight = sum(
            purchase.weight for purchase in sales_agent.get_all_active_sales()
            if month_start <= purchase.created_at <= month_end
        )

        monthly_sales.append({
            'month': month_start.strftime('%Y-%m'),
            'sales': sales_weight
        })

    # پیش‌بینی فروش ماه بعد (میانگین 6 ماه گذشته)
    total_sales = sum(m['sales'] for m in monthly_sales)
    sales_prediction = calculate_ml_prediction(sales_agent, monthly_sales)
    
    # تعداد مشتریان جدید این ماه
    new_customers_this_month = Customer.objects.filter(
        sales_agent=sales_agent,
        created_at__month=today.month  # مشتریان ایجاد شده در این ماه
    ).count()

    # محاسبه نوع مشتریان خرید کننده ماه اخیر
    customer_purchase_counts = defaultdict(int)
    purchases_this_month = Purchase.objects.filter(
        customer__sales_agent=sales_agent,
        created_at__month=today.month
    )

    for purchase in purchases_this_month:
        customer_purchase_counts[purchase.customer.id] += 1

    # دسته‌بندی مشتریان بر اساس تعداد خرید
    purchase_types = {
        '1': 0,  # یک بار خرید کرده‌اند
        '2': 0,  # دو بار خرید کرده‌اند
        '3+': 0  # سه بار یا بیشتر خرید کرده‌اند
    }

    for count in customer_purchase_counts.values():
        if count == 1:
            purchase_types['1'] += 1
        elif count == 2:
            purchase_types['2'] += 1
        else:
            purchase_types['3+'] += 1

    # محاسبه خریدها بر اساس استان
    province_purchases = defaultdict(int)
    purchases_this_month = Purchase.objects.filter(
        customer__sales_agent=sales_agent,
    )

    for purchase in purchases_this_month:
        city = purchase.customer.city  # فرض کنید فیلد city در مدل Customer وجود دارد
        if city:
            print(f"شهر از دیتابیس: {city}")
            province = find_province_by_city(city)
            print(f"شهر: {city}, استان: {province}")
            if province:
                province_purchases[province] += 1
        else:
            print(f"خرید بدون شهر: {purchase.id}")

    # چاپ نتیجه نهایی
    print("تعداد خریدها بر اساس استان:")
    for province, count in province_purchases.items():
        print(f"{province}: {count}")

    context = {
        'sales_agent': sales_agent,
        'new_customers_this_month': new_customers_this_month,
        'purchase_types': purchase_types,
        'province_purchases': dict(province_purchases),
        'monthly_sales': monthly_sales[::-1],  # معکوس برای نمایش از قدیم به جدید
        'task_stats': {
            'pending': len(sales_agent.get_all_undone_tasks()),
            'completed': len([task for task in sales_agent.get_all_tasks() if task.status])
        },
        'sales_prediction': round(sales_prediction, 2),
        'this_month_sales_weight': sales_agent.get_this_month_sales_weight(),
        'this_month_sales_count': sales_agent.get_this_month_sales_count(),
    }
    logger.info(f"Dashboard loaded for {sales_agent.name}")
    return render(request, 'sales_dashboard.html', context)