#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
from celery import shared_task
from jdatetime import datetime as jdatetime
from config.celery import app
from .bki_kharid_list_by_date import get_purchases_last_24_hours, get_purchases_last_week, get_purchases_last_month, get_purchases_all_time
from django.utils import timezone
from datetime import timedelta
from .models import BKIApiLog

@shared_task
def update_purchases_last_24_hours():
    """
    به‌روزرسانی خریدها از 24 ساعت گذشته تا زمان حال
    """
    result = get_purchases_last_24_hours()
    
    return {
        "total_count": result[0],
        "success_count": result[1],
        "created_count": result[2],
        "updated_count": result[3],
        "failed_count": result[4],
        "errors": result[5],
        "period": "24_hours"
    }

@shared_task
def update_purchases_last_week():
    """
    به‌روزرسانی خریدها از یک هفته گذشته تا زمان حال
    """
    result = get_purchases_last_week()
    
    return {
        "total_count": result[0],
        "success_count": result[1],
        "created_count": result[2],
        "updated_count": result[3],
        "failed_count": result[4],
        "errors": result[5],
        "period": "week"
    }

@shared_task
def update_purchases_last_month():
    """
    به‌روزرسانی خریدها از یک ماه گذشته تا زمان حال
    """
    result = get_purchases_last_month()
    
    return {
        "total_count": result[0],
        "success_count": result[1],
        "created_count": result[2],
        "updated_count": result[3],
        "failed_count": result[4],
        "errors": result[5],
        "period": "month"
    }

@shared_task
def update_purchases_all_time():
    """
    به‌روزرسانی تمام خریدها از ابتدا تا کنون
    """
    result = get_purchases_all_time()
    
    return {
        "total_count": result[0],
        "success_count": result[1],
        "created_count": result[2],
        "updated_count": result[3],
        "failed_count": result[4],
        "errors": result[5],
        "period": "all_time"
    }

@shared_task
def cleanup_old_api_logs():
    cutoff = timezone.now() - timedelta(hours=24)
    BKIApiLog.objects.filter(
        created_at__lt=cutoff
    ).delete()