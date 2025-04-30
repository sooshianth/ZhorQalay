from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
from core._models import Customer, Purchase
import logging
import json
import os
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from django.core.cache import cache
from core.decorators.decorators import role_required
logger = logging.getLogger(__name__)

file_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'iran_cities_fa.json')
with open(file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

def normalize_city_name(city_name):
    """نرمال‌سازی نام شهرها برای تطبیق با دیتای GeoJSON"""
    if not city_name:
        return ""
    replacements = {
        'ي': 'ی',
        'ك': 'ک',
        'ة': 'ه',
        'آ': 'ا',
        ' ': '',
        '\u200c': '',  # حذف نیم‌فاصله
        '‌': '',  # حذف نیم‌فاصله
        'ئ': 'ی',
        'ؤ': 'و',
        'إ': 'ا',
        'أ': 'ا',
        'ء': '',
        '١': '1',
        '٢': '2',
        '٣': '3',
        '٤': '4',
        '٥': '5',
        '٦': '6',
        '٧': '7',
        '٨': '8',
        '٩': '9',
        '٠': '0',
    }
    normalized = city_name.strip()
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized.lower()

def find_province_by_city(target_city):
    """پیدا کردن استان بر اساس نام شهر"""
    if not target_city:
        return None
        
    target_city = normalize_city_name(target_city)
    
    # اول در شهرهای هر استان جستجو می‌کنیم
    for province in data:
        for city in province.get('cities', []):
            if normalize_city_name(city.get('name', '')) == target_city:
                return province['name']
    
    # اگر پیدا نشد، بررسی می‌کنیم که آیا خود نام، نام استان است
    for province in data:
        if normalize_city_name(province['name']) == target_city:
            return province['name']
    
    # اگر پیدا نشد، دنبال تطابق نسبی می‌گردیم
    for province in data:
        for city in province.get('cities', []):
            if target_city in normalize_city_name(city.get('name', '')):
                return province['name']
    
    # در نهایت تلاش می‌کنیم با نام استان تطبیق نسبی پیدا کنیم
    for province in data:
        if target_city in normalize_city_name(province['name']):
            return province['name']
    
    return None

def calculate_ml_prediction(sales_agent, monthly_sales):
    cache_key = f"sales_pred_{sales_agent.id}_{monthly_sales[-1]['month']}"
    cached_pred = cache.get(cache_key)
    if cached_pred:
        return cached_pred
    
    try:
        X = []
        y = []
        for i in range(1, len(monthly_sales)):
            prev_month = monthly_sales[i-1]
            current_month = monthly_sales[i]
            features = [
                prev_month.get('sales', 0),
                np.mean([m.get('sales', 0) for m in monthly_sales[max(0, i-3):i]]),
                i
            ]
            X.append(features)
            y.append(current_month['sales'])
        
        if len(X) < 3:
            logger.warning("Insufficient data for ML prediction, falling back to simple average")
            avg_sales = np.mean([m['sales'] for m in monthly_sales]) if monthly_sales else 0
            cache.set(cache_key, avg_sales, 604800)
            return avg_sales
        
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X, y)
        
        last_month_features = [
            monthly_sales[-1]['sales'],
            np.mean([m['sales'] for m in monthly_sales[-3:]]),
            len(monthly_sales)
        ]
        
        prediction = max(0, model.predict([last_month_features])[0])
        cache.set(cache_key, prediction, 604800)
        return prediction
        
    except Exception as e:
        logger.error(f"ML prediction error: {str(e)}")
        avg_sales = np.mean([m['sales'] for m in monthly_sales]) if monthly_sales else 0
        cache.set(cache_key, avg_sales, 604800)
        return avg_sales

@role_required('sales_agent', 'admin')
@login_required
def sales_dashboard_view(request):

    sales_agent = request.user.sales_agent
    today = timezone.now()

    # داده‌های فروش برای 6 ماه گذشته
    monthly_sales = []
    for i in range(6):
        month_date = today - timedelta(days=i * 30)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=31)).replace(day=1) - timedelta(seconds=1)

        sales = sales_agent.get_sales_in_period(start_date=month_start, end_date=month_end)
        total_weight = sum(purchase.order_weight for purchase in sales)

        monthly_sales.append({
            'month': month_start.strftime('%Y-%m'),
            'sales': total_weight / 1000  # تبدیل به تن
        })

    # پیش‌بینی فروش ماه بعد
    try:
        forecast_data = sales_agent.forecast_sales(days_ahead=30)
        sales_prediction = forecast_data['total_forecast'] / 1000  # تبدیل به تن
        forecast_confidence = forecast_data['confidence']
    except Exception as e:
        logger.error(f"Error in forecast_sales: {str(e)}")
        sales_prediction = calculate_ml_prediction(sales_agent, monthly_sales)
        forecast_confidence = 70

    # تعداد مشتریان جدید این ماه
    new_customers_this_month = Customer.objects.filter(
        sales_agent=sales_agent,
        created_at__gte=today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ).count()

    purchases_this_month = sales_agent.get_this_month_sales()
    
    unmatched_cities = set()
    province_purchases = defaultdict(int)
    
    for purchase in purchases_this_month:
        if purchase.customer and purchase.customer.city:  # بررسی وجود مشتری و شهر
            province = find_province_by_city(purchase.customer.city)
            if province:
                province_purchases[province] += purchase.order_weight / 1000  # تبدیل به تن
                logger.info(f"Added {purchase.order_weight/1000} tons for province {province} from city {purchase.customer.city}")
            else:
                unmatched_cities.add(purchase.customer.city)
                logger.warning(f"City not found: {purchase.customer.city} for purchase {purchase.id}")
    
    if unmatched_cities:
        logger.warning(f"Cities without province match: {unmatched_cities}")
        
    # برای دیباگ
    logger.info(f"Final province_purchases: {dict(province_purchases)}")


    # آمار فروش ماه جاری
    sales_stats = sales_agent.get_this_month_sales_stats()
    this_month_sales_weight = sales_agent.get_this_month_sales_weight() / 1000  # تبدیل به تن
    this_month_sales_count = len(sales_agent.get_this_month_sales())

    # آمار فروش بر اساس محصول
    product_sales = sales_agent.get_sales_by_product()

    # آمار تعداد خریدهای مشتریان
    customers = sales_agent.get_all_customers()
    purchase_counts = {1: 0, 2: 0, 3: 0}
    for customer in customers:
        count = customer.purchases_made.filter(
            created_at__gte=today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ).count()
        if count == 1:
            purchase_counts[1] += 1
        elif count == 2:
            purchase_counts[2] += 1
        elif count >= 3:
            purchase_counts[3] += 1

    context = {
        'sales_agent': sales_agent,
        'new_customers_this_month': new_customers_this_month,
        'province_purchases': dict(province_purchases),
        'monthly_sales': monthly_sales[::-1],
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
        'this_month_sales_weight': round(this_month_sales_weight, 2),
        'this_month_sales_count': this_month_sales_count,
        'purchase_types': purchase_counts
    }
    return render(request, 'sales_dashboard.html', context)