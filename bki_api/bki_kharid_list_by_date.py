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
from .bki_api_utils.data_processing import process_purchase_data, group_purchase_data_by_id, process_grouped_purchase_data
import logging

logger = logging.getLogger("bugs")

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

    soap_redacted_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidListByDate xmlns="http://tempuri.org/">
      <userName>***</userName>
      <pass>***</pass>
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
        request_data=soap_redacted_request
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
            logger.error(f"HTTP Error: {response.status_code} {response.text}")
            return None, log_entry, f"خطای HTTP: {response.status_code}"
        
        # تجزیه پاسخ XML با استفاده از تابع analyze_api_response
        try:
            logger.info("XML response received. Parsing...")
            from .bki_api_utils.api_client   import analyze_api_response
            
            # تحلیل ساختار پاسخ
            analysis = analyze_api_response(response.text)
            
            if not analysis['is_valid']:
                log_entry.is_successful = False
                log_entry.error_message = f"خطا در تحلیل پاسخ: {analysis['error']}"
                log_entry.save()
                logger.error(f"Error analyzing API response: {analysis['error']}")
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
                        logger.debug(f"Table1 is a list with {len(table1)} items")
                        log_entry.is_successful = True
                        log_entry.save()
                        return table1, log_entry, None
                    else:
                        logger.debug(f"Table1 is a dict with keys: {', '.join(table1.keys())}")
                        log_entry.is_successful = True
                        log_entry.save()
                        return [table1], log_entry, None
            
            # اگر به اینجا رسیدیم، داده‌های مورد انتظار پیدا نشد
            log_entry.is_successful = False
            log_entry.error_message = "هیچ داده خرید در پاسخ یافت نشد"
            log_entry.save()
            logger.warning("No purchase data found in the response")
            return None, log_entry, "هیچ داده خرید در پاسخ یافت نشد"
        
        except Exception as e:
            logger.error(f"Error parsing response: {str(e)}")
            import traceback
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}\n{traceback.format_exc()}"
            log_entry.save()
            return None, log_entry, f"خطا در تجزیه پاسخ: "
    
    except Exception as e:
        logger.error(f"Error sending request: {str(e)}")
        log_entry.is_successful = False
        log_entry.error_message = f"خطا در ارسال درخواست: "
        log_entry.save()
        return None, log_entry, f"خطا در ارسال درخواست:"

def get_all_purchases_by_date_range(start_date, end_date):
    """
    دریافت همه خریدهای بازه زمانی مشخص و ثبت آنها در دیتابیس
    
    Args:
        start_date: تاریخ شروع به فرمت شمسی (YYYY/MM/DD)
        end_date: تاریخ پایان به فرمت شمسی (YYYY/MM/DD)
    
    Returns:
        tuple: (تعداد کل, تعداد موفق, تعداد ایجاد شده, تعداد به‌روزرسانی شده, تعداد خطا, لیست خطاها)
    """
    # ارسال درخواست SOAP با استفاده از تابع موجود
    purchases_data, log_entry, error = send_kharid_list_by_date_request(start_date, end_date)
    
    if error:
        logger.error(f"Error sending SOAP request: {error}")
        return 0, 0, 0, 0, 0, [f"خطا در ارسال درخواست SOAP: {error}"]
    
    # بررسی اگر هیچ داده خریدی یافت نشد
    if not purchases_data:
        logger.warning("No purchase data found in the response")
        return 0, 0, 0, 0, 0, ["هیچ داده خرید در پاسخ یافت نشد"]
    
    # چاپ تعداد خریدهای یافت شده
    logger.debug(f"Number of purchases found: {len(purchases_data)}")
    
    # گروه‌بندی داده‌ها بر اساس شناسه خرید
    grouped_data = group_purchase_data_by_id(purchases_data)
    logger.debug(f"Purchases divided into {len(grouped_data)} groups")

    # پردازش گروه‌های خرید
    total_count = len(grouped_data)
    success_count = 0
    created_count = 0
    updated_count = 0
    failed_count = 0
    errors = []
    
    
    for purchase_id, entries in grouped_data.items():
        # استخراج اطلاعات از اولین ردیف هر گروه
        first_entry = entries[0]
        customer_name = first_entry.get('buyername', first_entry.get('byername', 'نامشخص'))
        product_type = first_entry.get('goodtitle', first_entry.get('productname', 'نامشخص'))
        goodtag = first_entry.get('goodtag', 'نامشخص')
        
        # محاسبه مجموع وزن‌ها
        total_order_weight = sum(int(entry.get('qty', 0) or 0) for entry in entries)
        total_delivered_weight = sum(int(entry.get('wbarnameshode', 0) or 0) for entry in entries)
        
        try:
            # پردازش گروه داده‌های خرید
            purchase, created, error = process_grouped_purchase_data(entries)
            
            if error:
                logger.error(f"Error processing purchase {purchase_id}: {error}")
                failed_count += 1
                errors.append(f"Purchase {purchase_id}: {error}")
            else:
                success_count += 1
                if created:
                    created_count += 1
                    logger.debug(f"New purchase created: {purchase_id}")
                else:
                    updated_count += 1
                    logger.debug(f"Purchase updated: {purchase_id}")

        except Exception as e:
            logger.error(f"Error processing purchase {purchase_id}: {str(e)}")
            failed_count += 1
            errors.append(f"خرید {purchase_id}: {str(e)}")
    
    logger.debug(f"Result: total={total_count}, successful={success_count}, created={created_count}, updated={updated_count}, failed={failed_count}")
    
    return total_count, success_count, created_count, updated_count, failed_count, errors

def get_purchases_recent_period(period_days=1):
    """
    دریافت خریدهای بازه زمانی اخیر
    
    Args:
        period_days: تعداد روزهای قبل تا امروز
    
    Returns:
        tuple: نتیجه فراخوانی get_all_purchases_by_date_range
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now()
    today_str = today_jalali.strftime("%Y/%m/%d")
    
    # تبدیل تاریخ روزهای قبل به شمسی
    past_date = jdatetime.now() - timedelta(days=period_days)
    past_str = past_date.strftime("%Y/%m/%d")
    
    return get_all_purchases_by_date_range(past_str, today_str)

def get_purchases_last_24_hours():
    """
    دریافت خریدهای 24 ساعت گذشته
    """
    return get_purchases_recent_period(1)

def get_purchases_last_week():
    """
    دریافت خریدهای یک هفته گذشته
    """
    return get_purchases_recent_period(7)

def get_purchases_last_month():
    """
    دریافت خریدهای یک ماه گذشته
    """
    return get_purchases_recent_period(30)

def get_purchases_all_time():
    """
    دریافت همه خریدها از تاریخ شروع تا امروز
    """
    # تبدیل تاریخ امروز به شمسی
    today_jalali = jdatetime.now()
    today_str = today_jalali.strftime("%Y/%m/%d")
    
    # تاریخ شروع ثابت
    start_date = "1403/01/01"
    
    return get_all_purchases_by_date_range(start_date, today_str)

def main():
    """
    تابع اصلی برای اجرای مستقیم اسکریپت
    """
    logger.critical("RUNNING SOAP REQUEST DIRECTLY")
    logger.info("Sending request to Bank Keshavarzi API (getKharidListByDate SOAP 1.1 over HTTPS)...")
    
    # تاریخ‌های پیش‌فرض
    from_date = "1403/11/05"
    to_date = "1403/11/05"
    
    purchases_data, log_entry, error = send_kharid_list_by_date_request(from_date, to_date)
    
    if error:
        logger.error(f"Error: {error}")
        return False
    
    logger.debug(f"Successfully retrieved {len(purchases_data)} purchases.")
    
    # ذخیره پاسخ XML به صورت زیبا
    try:
        xml_response = xml.dom.minidom.parseString(log_entry.response_data)
        pretty_xml = xml_response.toprettyxml(indent="  ")
        
        with open("kharid_list_response.xml", "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        
        logger.info(f"API call successful! Response saved to kharid_list_response.xml")
        return True
    except Exception as e:
        logger.error(f"Warning: Could not save formatted XML response: {str(e)}")
        return False

if __name__ == "__main__":
    main() 