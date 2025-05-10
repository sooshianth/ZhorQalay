#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from celery import shared_task
from jdatetime import datetime as jdatetime
from config.celery import app
from .bki_kharid_list_by_date import get_all_purchases_by_date_range

@shared_task
def update_purchases_last_24_hours():
    """
    به‌روزرسانی خریدها از 24 ساعت گذشته تا زمان حال
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    
    # تبدیل تاریخ دیروز به شمسی
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    yesterday_jalali = jdatetime.fromgregorian(date=yesterday.date()).strftime("%Y/%m/%d")
    
    print(f"دریافت خریدها از {yesterday_jalali} تا {today_jalali}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص شده
    total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(
        from_date=yesterday_jalali, 
        to_date=today_jalali
    )
    
    return {
        "total_count": total_count,
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "errors": errors,
        "from_date": yesterday_jalali,
        "to_date": today_jalali
    }

@shared_task
def update_purchases_last_week():
    """
    به‌روزرسانی خریدها از یک هفته گذشته تا زمان حال
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    
    # تبدیل تاریخ یک هفته قبل به شمسی
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    week_ago_jalali = jdatetime.fromgregorian(date=week_ago.date()).strftime("%Y/%m/%d")
    
    print(f"دریافت خریدها از {week_ago_jalali} تا {today_jalali}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص شده
    total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(
        from_date=week_ago_jalali, 
        to_date=today_jalali
    )
    
    return {
        "total_count": total_count,
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "errors": errors,
        "from_date": week_ago_jalali,
        "to_date": today_jalali
    }

@shared_task
def update_purchases_last_month():
    """
    به‌روزرسانی خریدها از یک ماه گذشته تا زمان حال
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    
    # تبدیل تاریخ یک ماه قبل به شمسی
    month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    month_ago_jalali = jdatetime.fromgregorian(date=month_ago.date()).strftime("%Y/%m/%d")
    
    print(f"دریافت خریدها از {month_ago_jalali} تا {today_jalali}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص شده
    total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(
        from_date=month_ago_jalali, 
        to_date=today_jalali
    )
    
    return {
        "total_count": total_count,
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "errors": errors,
        "from_date": month_ago_jalali,
        "to_date": today_jalali
    }

@shared_task
def update_purchases_all_time():
    """
    به‌روزرسانی تمام خریدها از تاریخ شروع (1403/11/05) تا زمان حال
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    
    # تاریخ شروع ثابت
    start_date = "1403/11/05"
    
    print(f"دریافت خریدها از {start_date} تا {today_jalali}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص شده
    total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(
        from_date=start_date, 
        to_date=today_jalali
    )
    
    return {
        "total_count": total_count,
        "success_count": success_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "errors": errors,
        "from_date": start_date,
        "to_date": today_jalali
    }