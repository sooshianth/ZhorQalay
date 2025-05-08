#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import xml.dom.minidom
import xmltodict
import os
import datetime
from django.conf import settings
from jdatetime import datetime as jdatetime
from .models import BKILog
import json
import xml.etree.ElementTree as ET
from datetime import timedelta

def send_kharid_list_by_date_request(from_date="1403/11/05", to_date="1403/11/05"):
    """
    ارسال درخواست SOAP به API بازارگاه برای دریافت لیست خریدها بر اساس تاریخ
    
    Args:
        from_date: تاریخ شروع به فرمت شمسی (YYYY/MM/DD)
        to_date: تاریخ پایان به فرمت شمسی (YYYY/MM/DD)
    
    Returns:
        tuple: (purchases_data, log_entry, error)
            purchases_data: لیست خریدها یا None در صورت خطا
            log_entry: رکورد لاگ ایجاد شده
            error: پیام خطا یا None در صورت موفقیت
    """
    # دریافت اطلاعات کاربری API بازارگاه از تنظیمات جنگو
    username = getattr(settings, 'BKI_USERNAME', None)
    password = getattr(settings, 'BKI_PASSWORD', None)
    
    # بررسی اعتبار نام کاربری و رمز عبور
    if not username or username.strip() == '':
        return None, None, "نام کاربری API بازارگاه تنظیم نشده است"
        
    if not password or password.strip() == '':
        return None, None, "رمز عبور API بازارگاه تنظیم نشده است"
    
    # آدرس API با HTTPS
    url = "https://spsws.bki.ir/spsws.asmx"
    
    # ایجاد درخواست SOAP 1.1 برای getKharidListByDate
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidListByDate xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <fromDate>{from_date}</fromDate>
      <toDate>{to_date}</toDate>
    </getKharidListByDate>
  </soap:Body>
</soap:Envelope>"""
    
    # تنظیم هدرهای درخواست
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidListByDate',
        'Host': 'spsws.bki.ir'
    }
    
    # ایجاد لاگ برای درخواست
    log_entry = BKILog(
        request_type='getKharidListByDate',
        request_data=soap_request
    )
    
    try:
        # ارسال درخواست با verify=False برای رد کردن بررسی گواهی SSL در صورت نیاز
        response = requests.post(url, data=soap_request, headers=headers, verify=False)
        
        # ذخیره پاسخ در لاگ
        log_entry.response_data = response.text
        
        if response.status_code != 200:
            log_entry.is_successful = False
            log_entry.error_message = f"خطای HTTP: {response.status_code}"
            log_entry.save()
            return None, log_entry, f"خطای HTTP: {response.status_code}"
        
        # تجزیه پاسخ XML با استفاده از تابع analyze_api_response
        try:
            print("پاسخ XML دریافت شد. در حال تجزیه...")
            from .bki_api_utils import analyze_api_response
            
            # تحلیل ساختار پاسخ
            analysis = analyze_api_response(response.text)
            print(f"نتیجه تحلیل پاسخ API: {analysis}")
            
            if not analysis['is_valid']:
                log_entry.is_successful = False
                log_entry.error_message = f"خطا در تحلیل پاسخ: {analysis['error']}"
                log_entry.save()
                return None, log_entry, f"خطا در تحلیل پاسخ: {analysis['error']}"
            
            # تجزیه پاسخ XML
            response_dict = xmltodict.parse(response.text)
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidListByDateResponse']['getKharidListByDateResult']
            diffgram = result['diffgr:diffgram']
            
            if 'NewDataSet' in diffgram and diffgram['NewDataSet']:
                if 'Table1' in diffgram['NewDataSet']:
                    table1 = diffgram['NewDataSet']['Table1']
                    
                    # Table1 ممکن است یک لیست یا یک دیکشنری باشد
                    if isinstance(table1, list):
                        print(f"Table1 یک لیست با {len(table1)} آیتم است")
                        for i, item in enumerate(table1):
                            print(f"آیتم {i+1}: کلیدهای موجود: {', '.join(item.keys())}")
                        log_entry.is_successful = True
                        log_entry.save()
                        return table1, log_entry, None
                    else:
                        print(f"Table1 یک دیکشنری با کلیدهای: {', '.join(table1.keys())}")
                        log_entry.is_successful = True
                        log_entry.save()
                        return [table1], log_entry, None
            
            # اگر به اینجا رسیدیم، داده‌های مورد انتظار پیدا نشد
            log_entry.is_successful = False
            log_entry.error_message = "هیچ داده خرید در پاسخ یافت نشد"
            log_entry.save()
            return None, log_entry, "هیچ داده خرید در پاسخ یافت نشد"
        
        except Exception as e:
            print(f"خطا در تجزیه پاسخ: {str(e)}")
            import traceback
            print(traceback.format_exc())
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}"
            log_entry.save()
            return None, log_entry, f"خطا در تجزیه پاسخ: {str(e)}"
    
    except Exception as e:
        print(f"خطا در ارسال درخواست: {str(e)}")
        log_entry.is_successful = False
        log_entry.error_message = f"خطا در ارسال درخواست: {str(e)}"
        log_entry.save()
        return None, log_entry, f"خطا در ارسال درخواست: {str(e)}"

def get_all_purchases_by_date_range(start_date, end_date):
    """
    دریافت همه خریدهای بازه زمانی مشخص و ثبت آنها در دیتابیس
    
    Args:
        start_date: تاریخ شروع به فرمت شمسی (YYYY/MM/DD)
        end_date: تاریخ پایان به فرمت شمسی (YYYY/MM/DD)
    
    Returns:
        tuple: (تعداد کل, تعداد موفق, تعداد ایجاد شده, تعداد به‌روزرسانی شده, تعداد خطا, لیست خطاها)
    """
    from bki_api.bki_api_utils import process_purchase_data_new
    
    # ارسال درخواست SOAP با استفاده از تابع موجود
    purchases_data, log_entry, error = send_kharid_list_by_date_request(start_date, end_date)
    
    if error:
        print(f"خطا در ارسال درخواست SOAP: {error}")
        return 0, 0, 0, 0, 0, [f"خطا در ارسال درخواست SOAP: {error}"]
    
    # بررسی اگر هیچ داده خریدی یافت نشد
    if not purchases_data:
        print("هیچ داده خرید در پاسخ یافت نشد")
        return 0, 0, 0, 0, 0, ["هیچ داده خرید در پاسخ یافت نشد"]
    
    # چاپ تعداد خریدهای یافت شده
    print(f"تعداد خریدهای یافت شده: {len(purchases_data)}")
    
    # پردازش خریدها
    total_count = len(purchases_data)
    success_count = 0
    created_count = 0
    updated_count = 0
    failed_count = 0
    errors = []
    
    # چاپ اطلاعات خریدها
    print("\nاطلاعات خریدها:")
    print("-" * 80)
    print(f"{'شناسه خرید':<15} {'نام مشتری':<25} {'نوع محصول':<15} {'شماره کوتاژ':<15} {'وزن سفارش':<15} {'وزن تحویلی':<15} {'اختلاف':<10}")
    print("-" * 80)
    
    for purchase_data in purchases_data:
        # استخراج شناسه خرید
        purchase_id = purchase_data.get('idkharid', purchase_data.get('kharididentity', 'نامشخص'))
        
        # استخراج نام مشتری
        customer_name = purchase_data.get('buyername', purchase_data.get('byername', 'نامشخص'))
        
        # استخراج نوع محصول
        product_type = purchase_data.get('goodtitle', purchase_data.get('productname', 'نامشخص'))
        
        # استخراج شماره کوتاژ
        cottage_number = purchase_data.get('kutajnumber', purchase_data.get('goodno', 'نامشخص'))
        
        # استخراج وزن سفارش
        order_weight = int(purchase_data.get('qty', purchase_data.get('orderedweight', 0)) or 0)
        
        # استخراج وزن تحویلی
        delivered_weight = int(purchase_data.get('wbarnamehshode', purchase_data.get('faktorshode', purchase_data.get('weight', 0))) or 0)
        
        # محاسبه اختلاف وزن
        weight_diff = delivered_weight - order_weight
        diff_type = 'سرک' if weight_diff > 0 else 'کسری' if weight_diff < 0 else '-'
        diff_display = f"{diff_type} {abs(weight_diff)}" if weight_diff != 0 else "-"
        
        # چاپ اطلاعات خرید
        print(f"{purchase_id:<15} {customer_name[:23]:<25} {product_type[:13]:<15} {cottage_number:<15} {order_weight:<15} {delivered_weight:<15} {diff_display:<10}")
        
        try:
            # پردازش داده‌های خرید
            purchase, created, error = process_purchase_data_new(purchase_data)
            
            if error:
                print(f"خطا در پردازش خرید {purchase_id}: {error}")
                failed_count += 1
                errors.append(f"خرید {purchase_id}: {error}")
            else:
                success_count += 1
                if created:
                    created_count += 1
                    print(f"خرید جدید ایجاد شد: {purchase_id}")
                else:
                    updated_count += 1
                    print(f"خرید به‌روزرسانی شد: {purchase_id}")
        
        except Exception as e:
            print(f"خطا در پردازش خرید {purchase_id}: {str(e)}")
            failed_count += 1
            errors.append(f"خرید {purchase_id}: {str(e)}")
    
    print("-" * 80)
    print(f"نتیجه: کل={total_count}, موفق={success_count}, جدید={created_count}, به‌روزرسانی={updated_count}, خطا={failed_count}")
    
    return total_count, success_count, created_count, updated_count, failed_count, errors

def get_purchases_last_24_hours():
    """
    دریافت خریدهای 24 ساعت اخیر از API بازارگاه و ثبت آنها در دیتابیس
    
    Returns:
        tuple: (تعداد کل, تعداد موفق, تعداد ایجاد شده, تعداد به‌روزرسانی شده, تعداد خطا, لیست خطاها)
    """
    # محاسبه تاریخ امروز و دیروز به فرمت شمسی
    today = jdatetime.now().strftime('%Y/%m/%d')
    yesterday = (jdatetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
    
    print(f"دریافت خریدهای از {yesterday} تا {today}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص
    return get_all_purchases_by_date_range(yesterday, today)

def get_purchases_last_week():
    """
    دریافت خریدهای هفته اخیر از API بازارگاه و ثبت آنها در دیتابیس
    
    Returns:
        tuple: (تعداد کل, تعداد موفق, تعداد ایجاد شده, تعداد به‌روزرسانی شده, تعداد خطا, لیست خطاها)
    """
    # محاسبه تاریخ امروز و یک هفته قبل به فرمت شمسی
    today = jdatetime.now().strftime('%Y/%m/%d')
    last_week = (jdatetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
    
    print(f"دریافت خریدهای از {last_week} تا {today}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص
    return get_all_purchases_by_date_range(last_week, today)

def get_purchases_last_month():
    """
    دریافت خریدهای یک ماه اخیر از API بازارگاه
    
    Returns:
        tuple: (total_count, success_count, created_count, updated_count, failed_count, errors)
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    
    # تبدیل تاریخ یک ماه قبل به شمسی
    month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
    month_ago_jalali = jdatetime.fromgregorian(date=month_ago.date()).strftime("%Y/%m/%d")
    
    print(f"دریافت خریدها از {month_ago_jalali} تا {today_jalali}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص شده
    return get_all_purchases_by_date_range(
        from_date=month_ago_jalali, 
        to_date=today_jalali
    )

def get_purchases_all_time():
    """
    دریافت تمام خریدها از تاریخ شروع (1403/11/05) تا امروز
    
    Returns:
        tuple: (total_count, success_count, created_count, updated_count, failed_count, errors)
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    
    # تاریخ شروع ثابت
    start_date = "1403/11/05"
    
    print(f"دریافت خریدها از {start_date} تا {today_jalali}")
    
    # فراخوانی تابع دریافت خریدها با بازه زمانی مشخص شده
    return get_all_purchases_by_date_range(
        from_date=start_date, 
        to_date=today_jalali
    )

def main():
    """
    تابع اصلی برای اجرای مستقیم اسکریپت
    """
    print("Sending request to Bank Keshavarzi API (getKharidListByDate SOAP 1.1 over HTTPS)...")
    
    # تاریخ‌های پیش‌فرض
    from_date = "1403/11/05"
    to_date = "1403/11/05"
    
    purchases_data, log_entry, error = send_kharid_list_by_date_request(from_date, to_date)
    
    if error:
        print(f"Error: {error}")
        return False
    
    print(f"Successfully retrieved {len(purchases_data)} purchases.")
    
    # ذخیره پاسخ XML به صورت زیبا
    try:
        xml_response = xml.dom.minidom.parseString(log_entry.response_data)
        pretty_xml = xml_response.toprettyxml(indent="  ")
        
        with open("kharid_list_response.xml", "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        
        print(f"API call successful! Response saved to kharid_list_response.xml")
        return True
    except Exception as e:
        print(f"Warning: Could not save formatted XML response: {str(e)}")
        return False

if __name__ == "__main__":
    main() 