#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import requests
import xmltodict
from django.conf import settings
from django.utils import timezone
from datetime import datetime
from core.PurchaseModel import Purchase
from core.CustomerModel import Customer, PhoneNumber
from core.CargoProductModel import CargoProduct
from .models import BKILog
from django_jalali.db import models as jmodels
import urllib3
import json
import xml.etree.ElementTree as ET

# غیرفعال کردن هشدارهای SSL برای اطمینان از کارکرد درست با API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# چاپ نسخه کتابخانه‌های مورد استفاده برای دیباگ
print(f"نسخه کتابخانه requests: {requests.__version__}")
try:
    print(f"نسخه کتابخانه xmltodict: {xmltodict.__version__}")
except AttributeError:
    print("نسخه کتابخانه xmltodict نامشخص است")

# بارگذاری فایل استان‌ها برای تبدیل کد به نام استان
def load_province_mapping():
    """بارگذاری نگاشت کد استان به نام استان از فایل XML"""
    province_mapping = {}
    try:
        # مسیر فایل XML استان‌ها
        file_path = os.path.join(os.path.dirname(__file__), 'Ostan-City-Codes', 'ostan_list_response.xml')
        
        # بررسی وجود فایل
        if not os.path.exists(file_path):
            print(f"خطا: فایل استان‌ها در مسیر {file_path} یافت نشد")
            return {}
            
        # خواندن و تجزیه فایل XML
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # فضای نام XML
        namespaces = {
            'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
            'diffgr': 'urn:schemas-microsoft-com:xml-diffgram-v1'
        }
        
        # استخراج داده‌های استان‌ها
        for table in root.findall('.//Table1', namespaces):
            code_elem = table.find('bazargahostancode')
            name_elem = table.find('nameostan')
            
            if code_elem is not None and name_elem is not None:
                code = int(code_elem.text)
                name = name_elem.text
                province_mapping[code] = name
        
        return province_mapping
    except Exception as e:
        print(f"خطا در بارگذاری فایل استان‌ها: {str(e)}")
        return {}

# بارگذاری نگاشت استان‌ها
PROVINCE_MAPPING = load_province_mapping()

def get_province_name(province_code):
    """تبدیل کد استان به نام استان"""
    if not province_code:
        return None
    
    try:
        code = int(province_code)
        return PROVINCE_MAPPING.get(code)
    except (ValueError, TypeError):
        return None

def get_bki_credentials():
    """دریافت اطلاعات کاربری API بازارگاه از تنظیمات جنگو"""
    username = getattr(settings, 'BKI_USERNAME', None)
    password = getattr(settings, 'BKI_PASSWORD', None)
    
    # بررسی اعتبار نام کاربری و رمز عبور
    if not username or username.strip() == '':
        print("خطا: نام کاربری API بازارگاه تنظیم نشده است")
        return None, None
        
    if not password or password.strip() == '':
        print("خطا: رمز عبور API بازارگاه تنظیم نشده است")
        return None, None
    
    return username, password

def send_soap_request(kharid_id):
    """ارسال درخواست SOAP به API بازارگاه و دریافت پاسخ"""
    username, password = get_bki_credentials()
    if not username or not password:
        raise ValueError("اطلاعات کاربری API بازارگاه در تنظیمات وجود ندارد")

    # آدرس API با HTTPS
    url = "https://spsws.bki.ir/spsws.asmx"

    # ایجاد درخواست SOAP 1.1
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidInfo xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <kharidId>{kharid_id}</kharidId>
    </getKharidInfo>
  </soap:Body>
</soap:Envelope>"""

    # تنظیم هدرهای درخواست
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo',
        'Host': 'spsws.bki.ir'
    }

    # ایجاد لاگ برای درخواست
    log_entry = BKILog(
        request_type='getKharidInfo',
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
        
        # تجزیه پاسخ XML
        try:
            response_dict = xmltodict.parse(response.text)
            # دریافت نتیجه از پاسخ
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidInfoResponse']['getKharidInfoResult']
            
            if not result or not isinstance(result, dict):
                log_entry.is_successful = False
                log_entry.error_message = "فرمت پاسخ نامعتبر است"
                log_entry.save()
                return None, log_entry, "فرمت پاسخ نامعتبر است"
            
            # بررسی داده‌های diffgram
            if 'diffgr:diffgram' in result:
                diffgram = result['diffgr:diffgram']
                if 'NewDataSet' in diffgram and diffgram['NewDataSet']:
                    if 'Table1' in diffgram['NewDataSet']:
                        table1 = diffgram['NewDataSet']['Table1']
                        # Table1 ممکن است یک لیست یا یک دیکشنری باشد
                        if isinstance(table1, list):
                            log_entry.is_successful = True
                            log_entry.save()
                            return table1, log_entry, None
                        else:
                            log_entry.is_successful = True
                            log_entry.save()
                            return [table1], log_entry, None
            
            # اگر به اینجا رسیدیم، داده‌های مورد انتظار پیدا نشد
            log_entry.is_successful = False
            log_entry.error_message = "هیچ داده خرید در پاسخ یافت نشد"
            log_entry.save()
            return None, log_entry, "هیچ داده خرید در پاسخ یافت نشد"
        
        except Exception as e:
            log_entry.is_successful = False
            log_entry.error_message = f"خطا در تجزیه پاسخ: {str(e)}"
            log_entry.save()
            return None, log_entry, f"خطا در تجزیه پاسخ: {str(e)}"
    
    except Exception as e:
        log_entry.is_successful = False
        log_entry.error_message = f"خطا در ارسال درخواست: {str(e)}"
        log_entry.save()
        return None, log_entry, f"خطا در ارسال درخواست: {str(e)}"

def determine_product_type(product_title):
    """تعیین نوع محصول براساس عنوان"""
    if not product_title:
        return 'other'
    
    product_title = product_title.lower()
    
    if 'ذرت' in product_title:
        return 'corn'
    elif 'جو' in product_title:
        return 'barley'
    elif 'سویا' in product_title and 'کنجاله' in product_title:
        if 'دانه داخلی' in product_title:
            return 'local_extracted_soy'
        elif 'دانه خارجی' in product_title:
            return 'foreign_extracted_soy'
        else:
            return 'soy_meal'
    elif 'آفتابگردان' in product_title:
        return 'sunflower_meal'
    elif 'کلزا' in product_title:
        return 'rapeseed_meal'
    elif 'پنبه' in product_title:
        return 'cotton_seed'
    elif 'یونجه' in product_title:
        return 'alfalfa'
    elif 'سویا' in product_title and 'دان' in product_title:
        return 'soy_grain'
    else:
        return 'other'

def clean_phone_number(phone):
    """پاکسازی شماره تلفن برای استفاده در دیتابیس"""
    # ایجاد یک شماره تلفن پیش‌فرض برای مواقعی که شماره ورودی معتبر نیست
    default_number = "9000000000"
    
    if not phone:
        # اگر شماره خالی است، شماره پیش‌فرض را برگردان
        return default_number, None
        
    # تبدیل اعداد فارسی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    phone = str(phone).strip().translate(translation_table)
    
    # پاکسازی شماره از کاراکترهای غیرعددی
    cleaned_number = ''.join(c for c in phone if c.isdigit())
    
    # اگر هیچ رقمی استخراج نشد، شماره پیش‌فرض را برگردان
    if not cleaned_number:
        return default_number, None
    
    # حذف صفر ابتدایی اگر وجود داشته باشد
    if cleaned_number.startswith('0'):
        cleaned_number = cleaned_number[1:]
    
    # حذف کد کشور ایران اگر وجود داشته باشد (98)
    if cleaned_number.startswith('98'):
        cleaned_number = cleaned_number[2:]
        
    # اگر شماره بیشتر از 10 رقم دارد، 10 رقم آخر را نگه داریم
    if len(cleaned_number) > 10:
        cleaned_number = cleaned_number[-10:]
        
    # بررسی اینکه شماره با 9 شروع شود (برای تبدیل به موبایل)
    if not cleaned_number.startswith('9'):
        # اگر طول کافی دارد (حداقل 7 رقم)، 9 را اضافه کرده و آخرین 9 رقم را نگه می‌داریم
        if len(cleaned_number) >= 7:
            cleaned_number = '9' + cleaned_number[:9]
        else:
            # اگر کوتاه است، با صفر پر می‌کنیم
            cleaned_number = '9' + cleaned_number.zfill(9)[:9]
    
    # اطمینان از اینکه طول شماره دقیقاً 10 رقم است
    if len(cleaned_number) < 10:
        # اگر کمتر از 10 رقم است، با صفر پر می‌کنیم
        cleaned_number = cleaned_number + '0' * (10 - len(cleaned_number))
    elif len(cleaned_number) > 10:
        # اگر بیشتر از 10 رقم است، اضافه‌ها را حذف می‌کنیم
        cleaned_number = cleaned_number[:10]
    
    # همیشه یک شماره معتبر برمی‌گرداند
    return cleaned_number, None

def convert_persian_date_to_gregorian(persian_date_str):
    """
    تبدیل تاریخ فارسی (شمسی) به میلادی با فرمت استاندارد
    ورودی: رشته تاریخ فارسی با فرمت YYYY/MM/DD
    خروجی: آبجکت datetime میلادی یا None در صورت بروز خطا
    """
    if not persian_date_str:
        return None
        
    try:
        # پاکسازی تاریخ و تقسیم آن به اجزا
        parts = persian_date_str.strip().split('/')
        if len(parts) != 3:
            return None
            
        # تبدیل اعداد فارسی به انگلیسی در صورت نیاز
        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        english_digits = "0123456789"
        translation_table = str.maketrans(persian_digits, english_digits)
        
        persian_year = int(parts[0].translate(translation_table))
        persian_month = int(parts[1].translate(translation_table))
        persian_day = int(parts[2].translate(translation_table))
        
        # سال و ماه و روز باید در محدوده مجاز باشند
        if persian_year < 1300 or persian_year > 1500:
            return None
        if persian_month < 1 or persian_month > 12:
            return None
        if persian_day < 1 or persian_day > 31:
            return None
            
        # استفاده از کتابخانه django-jalali برای تبدیل تاریخ
        from jdatetime import datetime as jdatetime
        
        # ایجاد تاریخ جلالی
        jdt = jdatetime(persian_year, persian_month, persian_day, 12, 0, 0)
        
        # تبدیل به تاریخ میلادی
        dt = jdt.togregorian()
        
        # ساخت آبجکت datetime با منطقه زمانی
        return timezone.make_aware(dt)
    except (ValueError, ImportError, AttributeError) as e:
        # در صورت هر خطایی، None برگردان
        return None

def process_purchase_data(purchase_data, create_if_not_exists=True):
    """
    پردازش داده‌های خرید و به‌روزرسانی یا ایجاد رکورد خرید
    برمی‌گرداند: (purchase, created, error_message)
    """
    # ذخیره اطلاعات خرید برای لاگ
    purchase_id = purchase_data.get('kharididentity', 'نامشخص')
    
    # نگاشت فیلدهای XML به فیلدهای دیتابیس
    field_mappings = {
        'kharididentity': 'purchase_number',
        'kutajnumber': 'cargo__cottage',
        'goodtitle': 'cargo__product_type',
        'weight': 'delivered_weight',
        'buydate': 'created_at',
        'rrn': 'tracking_number',
        'byername': 'customer__name',
        'buyeraddress': 'address',
        'delphone': 'tahvil_phone_number',
        'totalamount': 'amount_paid',
        'paymenttype': 'payment_method',
        'fi': 'customer_price',
        'buyermobile': 'customer__phone_number',
        'buyermellicode': 'code_melli_tahvil',
        'ostanname': 'customer__city',
        'cityname': 'customer__city_detail',
    }
    
    # استخراج مقادیر از داده‌های خرید
    data = {}
    for xml_field, db_field in field_mappings.items():
        if xml_field in purchase_data:
            data[db_field] = purchase_data[xml_field]
    
    # بررسی وجود شماره خرید
    purchase_number = data.get('purchase_number')
    if not purchase_number:
        return None, False, "شماره خرید در پاسخ یافت نشد"
    
    # پاکسازی شماره تلفن
    mobile_number = None
    phone_error = None
    
    if 'customer__phone_number' in data:
        mobile_number, phone_error = clean_phone_number(data['customer__phone_number'])
        # تابع clean_phone_number اصلاح شده همیشه یک شماره معتبر برمی‌گرداند
        data['customer__phone_number'] = mobile_number
    else:
        print(f"هشدار: هیچ شماره تلفنی برای خرید {purchase_number} ارائه نشده است")
        # استفاده از تابع clean_phone_number برای ایجاد شماره پیش‌فرض
        mobile_number, _ = clean_phone_number('')
        data['customer__phone_number'] = mobile_number
        print(f"ایجاد شماره تلفن پیش‌فرض: {mobile_number}")
    
    try:
        # سعی در یافتن خرید موجود
        purchase = Purchase.objects.get(purchase_number=purchase_number)
        created = False
        
        # به‌روزرسانی فیلدهای ساده
        simple_fields = [
            'delivered_weight', 'tracking_number', 'address', 
            'tahvil_phone_number', 'amount_paid', 'payment_method', 
            'customer_price', 'code_melli_tahvil'
        ]
        
        for field in simple_fields:
            if field in data and data[field]:
                setattr(purchase, field, data[field])
        
        # به‌روزرسانی فیلدهای مشتری
        if purchase.customer:
            if 'customer__name' in data and data['customer__name']:
                purchase.customer.name = data['customer__name']
            
            if 'customer__city' in data and data['customer__city']:
                purchase.customer.city = data['customer__city']
            
            if mobile_number and 'customer__phone_number' in data:
                primary_phone = purchase.customer.get_primary_phone()
                
                if primary_phone != mobile_number:
                    # به‌روزرسانی شماره تلفن اصلی
                    phone = purchase.customer.phone_numbers.filter(is_primary=True).first()
                    if phone:
                        try:
                            phone.number = mobile_number
                            phone.save()
                        except Exception as e:
                            # خطا در به‌روزرسانی شماره تلفن را نادیده می‌گیریم
                            print(f"خطا در به‌روزرسانی شماره تلفن: {str(e)}")
                    else:
                        # ایجاد شماره تلفن جدید
                        try:
                            PhoneNumber.objects.create(
                                customer=purchase.customer,
                                number=mobile_number,
                                is_primary=True
                            )
                        except Exception as e:
                            # خطا در ایجاد شماره تلفن را نادیده می‌گیریم
                            print(f"خطا در ایجاد شماره تلفن: {str(e)}")
            
            # ذخیره تغییرات مشتری
            purchase.customer.save()
        
        # به‌روزرسانی تاریخ‌ها در صورت نیاز
        if 'created_at' in data and data['created_at']:
            # استفاده از تابع جدید برای تبدیل تاریخ
            persian_date = data['created_at']
            gregorian_date = convert_persian_date_to_gregorian(persian_date)
            if gregorian_date:
                purchase.created_at = gregorian_date
        
        # به‌روزرسانی خرید
        purchase.updated_at = timezone.now()
        purchase.save()
        
        return purchase, created, None
    
    except Purchase.DoesNotExist:
        if not create_if_not_exists:
            return None, False, f"خرید با شماره {purchase_number} یافت نشد"
        
        # ایجاد خرید جدید
        try:
            # واردات مدل SalesAgent
            from core.SalesAgentModel import SalesAgent
            
            # 1. یافتن یا ایجاد مشتری
            if not mobile_number:
                # این نباید هرگز اتفاق بیفتد چون همیشه یک شماره موبایل معتبر ایجاد می‌کنیم
                return None, False, "خطای داخلی در پردازش شماره موبایل مشتری"
            
            customer = None
            customer_existed = False
            
            # جستجوی مشتری با شماره تلفن
            customer = Customer.get_customer_by_phone(mobile_number)
            customer_existed = customer is not None
            
            if not customer:
                # ایجاد مشتری جدید
                customer = Customer.objects.create(
                    name=data.get('customer__name', 'مشتری ناشناس'),
                    city=data.get('customer__city'),
                    phone_number=mobile_number,  # تنظیم فیلد موروثی شماره تلفن برای حفظ سازگاری با کد قدیمی
                )
                
                # یافتن کارشناس فروش "مدیریت سیستم"
                try:
                    system_admin = SalesAgent.objects.get(user__username='admin')
                    customer.sales_agent.add(system_admin)
                except (SalesAgent.DoesNotExist, SalesAgent.MultipleObjectsReturned) as e:
                    # اگر کارشناس فروش مورد نظر پیدا نشد، سعی می‌کنیم اولین کارشناس فروش موجود را انتخاب کنیم
                    try:
                        first_agent = SalesAgent.objects.first()
                        if first_agent:
                            customer.sales_agent.add(first_agent)
                    except Exception:
                        pass  # اگر هیچ کارشناس فروشی موجود نبود، ادامه می‌دهیم
                
                # ایجاد شماره تلفن برای مشتری
                try:
                    PhoneNumber.objects.create(
                        customer=customer,
                        number=mobile_number,
                        is_primary=True
                    )
                except Exception as e:
                    # اگر ایجاد شماره تلفن با خطا مواجه شد، مشتری را حذف می‌کنیم
                    customer.delete()
                    return None, False, f"خطا در ایجاد شماره تلفن: {str(e)}"
            
            # 2. یافتن یا ایجاد محصول
            cottage_number = data.get('cargo__cottage')
            cargo = None
            cargo_existed = False
            
            if cottage_number:
                try:
                    cargo = CargoProduct.objects.get(cottage=cottage_number)
                    cargo_existed = True
                except CargoProduct.DoesNotExist:
                    # ایجاد محصول جدید
                    product_type = 'other'
                    if 'cargo__product_type' in data:
                        product_type = determine_product_type(data['cargo__product_type'])
                    
                    cargo = CargoProduct.objects.create(
                        type='bazaargah',
                        cottage=cottage_number,
                        company_price=0,  # همیشه صفر
                        customer_price=data.get('customer_price', 0),
                        product_type=product_type,
                        country='iran',  # پیش‌فرض
                        port='امام خمینی',  # پیش‌فرض
                        weight=1000000  # پیش‌فرض: 1000 تن
                    )
            
            # 3. ایجاد خرید جدید
            new_purchase = Purchase.objects.create(
                purchase_number=purchase_number,
                customer=customer,
                cargo=cargo,
                address=data.get('address'),
                delivered_weight=data.get('delivered_weight', 0),
                tracking_number=data.get('tracking_number'),
                tahvil_phone_number=data.get('tahvil_phone_number'),
                amount_paid=data.get('amount_paid', 0),
                payment_method=data.get('payment_method', 'نقدی'),
                customer_price=data.get('customer_price', 0),
                company_price=0,  # همیشه صفر
                code_melli_tahvil=data.get('code_melli_tahvil'),
                type='bazaargah',
                state='PAYMENT_VERIFIED'
            )
            
            # افزودن پرچم‌ها برای پیگیری وجود قبلی اشیاء (برای گزارش‌دهی)
            new_purchase._customer_existed = customer_existed
            new_purchase._cargo_existed = cargo_existed
            
            # تنظیم تاریخ ایجاد در صورت وجود
            if 'created_at' in data and data['created_at']:
                # استفاده از تابع جدید برای تبدیل تاریخ
                persian_date = data['created_at']
                gregorian_date = convert_persian_date_to_gregorian(persian_date)
                if gregorian_date:
                    new_purchase.created_at = gregorian_date
                    new_purchase.save(update_fields=['created_at'])
            
            return new_purchase, True, None
        
        except Exception as e:
            return None, False, f"خطا در ایجاد خرید: {str(e)}"

def get_purchase_info(kharid_id, create_if_not_exists=True):
    """
    دریافت اطلاعات خرید از API بازارگاه و به‌روزرسانی یا ایجاد در دیتابیس
    """
    # ارسال درخواست SOAP
    purchases_data, log_entry, error = send_soap_request(kharid_id)
    if error:
        return None, False, error
    
    results = []
    for purchase_data in purchases_data:
        purchase, created, error = process_purchase_data(purchase_data, create_if_not_exists)
        if purchase:
            # به‌روزرسانی مرجع خرید در لاگ
            if log_entry and not log_entry.purchase:
                log_entry.purchase = purchase
                log_entry.save()
                
            results.append({
                'purchase': purchase,
                'created': created,
                'error': error
            })
        elif error:
            results.append({
                'purchase': None,
                'created': False,
                'error': error
            })
    
    # برگرداندن اولین نتیجه یا None اگر نتیجه‌ای وجود نداشت
    if results:
        return results[0]['purchase'], results[0]['created'], results[0]['error']
    return None, False, "هیچ خریدی در پاسخ API یافت نشد"

def bulk_update_purchase_info(kharid_ids):
    """
    به‌روزرسانی چند خرید از API بازارگاه
    """
    if isinstance(kharid_ids, str):
        # تقسیم رشته شناسه‌ها با کاما، فاصله یا خط جدید
        import re
        kharid_ids = re.split(r'[,\s]+', kharid_ids)
    
    # فیلتر کردن رشته‌های خالی
    kharid_ids = [kid.strip() for kid in kharid_ids if kid.strip()]
    
    results = []
    for kharid_id in kharid_ids:
        try:
            purchase, created, error = get_purchase_info(kharid_id)
            
            if purchase:
                result = {
                    'kharid_id': kharid_id,
                    'success': True,
                    'created': created,
                    'is_new': created,  # قالب انتظار is_new به جای created دارد
                    'purchase': purchase
                }
                
                if created:
                    # برای خریدهای جدید، ارائه اطلاعات اشیاء ایجاد شده
                    result['message'] = f'خرید جدید با شماره {purchase.purchase_number} با موفقیت ایجاد شد'
                    result['created_objects'] = {
                        'customer': {
                            'status': 'found' if hasattr(purchase, '_customer_existed') and purchase._customer_existed else 'created',
                            'id': purchase.customer.id
                        },
                        'cargo': {
                            'status': 'found' if hasattr(purchase, '_cargo_existed') and purchase._cargo_existed else 'created' if purchase.cargo else 'not_created',
                            'id': purchase.cargo.id if purchase.cargo else None,
                            'reason': 'cottage_number_missing' if not purchase.cargo else None
                        },
                        'purchase': {
                            'status': 'created',
                            'id': purchase.id
                        }
                    }
                else:
                    # برای خریدهای موجود، ارائه اطلاعات به‌روزرسانی
                    result['message'] = f'اطلاعات خرید {purchase.purchase_number} با موفقیت به‌روزرسانی شد'
                    # این فیلدها توسط update_purchase_info تنظیم می‌شوند اما ما نیاز داریم آنها را ارائه دهیم
                    # زیرا از آن تابع عبور می‌کنیم - فعلاً از آرایه‌های خالی استفاده می‌کنیم
                    result['purchase_updates'] = []
                    result['customer_updates'] = {}
            else:
                # حالت خطا
                result = {
                    'kharid_id': kharid_id,
                    'success': False,
                    'error': error or 'خطای نامشخص در دریافت اطلاعات خرید'
                }
            
            results.append(result)
        except Exception as e:
            results.append({
                'kharid_id': kharid_id,
                'success': False,
                'error': str(e)
            })
    
    return results

def test_api_connection():
    """
    تست اتصال به API بازارگاه با یک درخواست SOAP ساده
    
    این تابع یک درخواست SOAP ساده به API بازارگاه ارسال می‌کند تا اتصال را تست کند.
    
    برمی‌گرداند: (is_successful, message)
    """
    # دریافت اطلاعات کاربری API بازارگاه
    username, password = get_bki_credentials()
    if not username or not password:
        return False, "اطلاعات کاربری API بازارگاه در تنظیمات وجود ندارد"
    
    # آدرس API با HTTPS
    url = "https://spsws.bki.ir/spsws.asmx"
    
    # ایجاد درخواست SOAP 1.1 برای تست اتصال
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <getKharidInfo xmlns="http://tempuri.org/">
      <userName>{username}</userName>
      <pass>{password}</pass>
      <kharidId>123456</kharidId>
    </getKharidInfo>
  </soap:Body>
</soap:Envelope>"""
    
    # تنظیم هدرهای درخواست
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo',
        'Host': 'spsws.bki.ir'
    }
    
    try:
        # ارسال درخواست با verify=False برای رد کردن بررسی گواهی SSL در صورت نیاز
        print("تست اتصال به API بازارگاه...")
        response = requests.post(url, data=soap_request, headers=headers, verify=False, timeout=10)
        print(f"وضعیت پاسخ API: {response.status_code}")
        
        if response.status_code != 200:
            return False, f"خطای HTTP: {response.status_code}"
        
        # بررسی اگر پاسخ خالی است
        if not response.text or response.text.strip() == '':
            return False, "پاسخ API خالی است"
            
        # تجزیه پاسخ XML
        try:
            response_dict = xmltodict.parse(response.text)
            # دریافت نتیجه از پاسخ
            soap_body = response_dict['soap:Envelope']['soap:Body']
            
            # بررسی وجود کلید getKharidInfoResponse در پاسخ
            if 'getKharidInfoResponse' not in soap_body:
                return False, "فرمت پاسخ نامعتبر است - کلید getKharidInfoResponse یافت نشد"
                
            # بررسی وجود کلید getKharidInfoResult در پاسخ
            if 'getKharidInfoResult' not in soap_body['getKharidInfoResponse']:
                return False, "فرمت پاسخ نامعتبر است - کلید getKharidInfoResult یافت نشد"
            
            # اتصال موفق بود
            return True, "اتصال به API بازارگاه با موفقیت انجام شد"
            
        except Exception as e:
            return False, f"خطا در تجزیه پاسخ: {str(e)}"
    
    except Exception as e:
        return False, f"خطا در ارسال درخواست: {str(e)}"

def get_all_bazaargah_purchases():
    """
    دریافت تمام خریدهای موجود در بازارگاه و ثبت آنها در دیتابیس
    
    این تابع با استفاده از API بازارگاه، تمام خریدهای موجود را دریافت کرده و در دیتابیس ثبت می‌کند.
    خریدهای موجود به‌روزرسانی شده و خریدهای جدید ایجاد می‌شوند.
    
    برمی‌گرداند: (total_count, success_count, created_count, updated_count, failed_count, errors)
    """
    # دریافت اطلاعات کاربری API بازارگاه
    username, password = get_bki_credentials()
    if not username or not password:
        return 0, 0, 0, 0, 0, ["اطلاعات کاربری API بازارگاه در تنظیمات وجود ندارد"]
    
    # تست اتصال به سرور API
    is_connected, connection_message = test_api_connection()
    if not is_connected:
        return 0, 0, 0, 0, 0, [f"خطا در اتصال به API بازارگاه: {connection_message}"]
    
    print("تست اتصال به API بازارگاه موفقیت‌آمیز بود. درحال دریافت خریدها...")
    
    # برای دریافت تمام خریدها، از یک شناسه خرید نمونه استفاده می‌کنیم
    # از تابع send_soap_request استفاده می‌کنیم که به خوبی کار می‌کند
    sample_kharid_id = "1"  # یک شناسه خرید نمونه
    
    # ارسال درخواست SOAP با استفاده از تابع send_soap_request
    purchases_data, log_entry, error = send_soap_request(sample_kharid_id)
    
    if error:
        print(f"خطا در ارسال درخواست SOAP: {error}")
        return 0, 0, 0, 0, 0, [f"خطا در ارسال درخواست SOAP: {error}"]
    
    # بررسی اگر هیچ داده خریدی یافت نشد
    if not purchases_data:
        print("هیچ داده خرید در پاسخ یافت نشد")
        return 0, 0, 0, 0, 0, ["هیچ داده خرید در پاسخ یافت نشد"]
    
    # چاپ تعداد خریدهای یافت شده برای دیباگ
    print(f"تعداد خریدهای یافت شده: {len(purchases_data)}")
    
    # پردازش داده‌های خرید با استفاده از تابع process_purchase_data موجود
    total_count = len(purchases_data)
    success_count = 0
    created_count = 0
    updated_count = 0
    failed_count = 0
    errors = []
    
    for purchase_data in purchases_data:
        try:
            # چاپ شناسه خرید برای دیباگ
            purchase_id = purchase_data.get('kharididentity', 'نامشخص')
            print(f"پردازش خرید با شناسه: {purchase_id}")
            
            # استفاده از تابع موجود process_purchase_data برای پردازش هر خرید
            purchase, created, error = process_purchase_data(purchase_data, create_if_not_exists=True)
            if purchase:
                success_count += 1
                if created:
                    created_count += 1
                    print(f"خرید جدید ایجاد شد: {purchase_id}")
                else:
                    updated_count += 1
                    print(f"خرید موجود به‌روزرسانی شد: {purchase_id}")
            else:
                failed_count += 1
                if error:
                    errors.append(f"خطا در پردازش خرید {purchase_id}: {error}")
                    print(f"خطا در پردازش خرید {purchase_id}: {error}")
        except Exception as e:
            failed_count += 1
            purchase_id = purchase_data.get('kharididentity', 'نامشخص')
            errors.append(f"خطا در پردازش خرید {purchase_id}: {str(e)}")
            print(f"خطا در پردازش خرید {purchase_id}: {str(e)}")
    
    print(f"نتیجه نهایی: کل={total_count}, موفق={success_count}, جدید={created_count}, بروزرسانی={updated_count}, خطا={failed_count}")
    return total_count, success_count, created_count, updated_count, failed_count, errors

def process_purchase_data_new(purchase_data, create_if_not_exists=True):
    """
    پردازش داده‌های خرید از API جدید و به‌روزرسانی یا ایجاد رکورد خرید
    
    Args:
        purchase_data: دیکشنری داده‌های خرید از API جدید
        create_if_not_exists: آیا در صورت عدم وجود خرید، ایجاد شود
    
    Returns:
        tuple: (purchase, created, error_message)
    """
    # دیباگ: چاپ کلیدهای موجود در داده خرید
    print(f"کلیدهای موجود در داده خرید: {', '.join(purchase_data.keys())}")
    print(f"داده‌های خرید: {purchase_data}")
    
    # ذخیره اطلاعات خرید برای لاگ
    purchase_id = purchase_data.get('idkharid', purchase_data.get('kharididentity', 'نامشخص'))
    print(f"شناسه خرید استخراج شده: {purchase_id}")
    
    # نگاشت فیلدهای XML به فیلدهای دیتابیس - شامل هر دو فرمت قدیم و جدید
    field_mappings = {
        # فرمت جدید
        'idkharid': 'purchase_number',
        'goodno': 'cargo__cottage',
        'kutajnumber': 'cargo__cottage',  # اضافه کردن kutajnumber
        'goodtag': 'cargo__cottage',  # اضافه کردن goodtag به عنوان کوتاژ
        'productname': 'cargo__product_type',
        'goodtitle': 'cargo__product_type',  # اضافه کردن goodtitle
        'faktorshode': 'delivered_weight',
        'wbarnamehshode': 'delivered_weight',  # اضافه کردن wbarnamehshode
        'date': 'created_at',
        'tracecode': 'tracking_number',
        'buyername': 'customer__name',
        'buyeraddress': 'address',
        'receiverphone': 'tahvil_phone_number',
        'totalvalue': 'amount_paid',
        'paymentterm': 'payment_method',
        'fee': 'customer_price',
        'buyerphone': 'customer__phone_number',
        'receiveruniqueid': 'code_melli_tahvil',
        'provincename': 'customer__city',
        'cityname': 'customer__city_detail',
        'orderedweight': 'order_weight',  # وزن درخواستی
        'qty': 'order_weight',  # اضافه کردن qty
        'allocationid': 'shenase_takhsis',  # اضافه کردن شناسه تخصیص
        'activityfield': 'customer__activity_field',  # اضافه کردن حیطه فعالیت
        
        # فرمت قدیم
        'kharididentity': 'purchase_number',
        'weight': 'delivered_weight',
        'buydate': 'created_at',
        'rrn': 'tracking_number',
        'byername': 'customer__name',
        'buyeraddress': 'address',
        'delphone': 'tahvil_phone_number',
        'totalamount': 'amount_paid',
        'paymenttype': 'payment_method',
        'fi': 'customer_price',
        'buyermobile': 'customer__phone_number',
        'buyermellicode': 'code_melli_tahvil',
        'ostanname': 'customer__city',
    }
    
    # استخراج مقادیر از داده‌های خرید
    data = {}
    for xml_field, db_field in field_mappings.items():
        if xml_field in purchase_data:
            data[db_field] = purchase_data[xml_field]
            print(f"یافت شد: {xml_field} -> {db_field} = {purchase_data[xml_field]}")
    
    # بررسی وجود شماره خرید
    purchase_number = data.get('purchase_number')
    if not purchase_number:
        print("خطا: شماره خرید در داده‌های دریافتی یافت نشد")
        print(f"داده‌های استخراج شده: {data}")
        return None, False, "شماره خرید در پاسخ یافت نشد"
    
    # تبدیل کد استان به نام استان
    if 'customer__city' in data:
        province_name = get_province_name(data['customer__city'])
        if province_name:
            data['customer__city'] = province_name
    
    # پاکسازی شماره تلفن
    mobile_number = None
    phone_error = None
    
    if 'customer__phone_number' in data:
        mobile_number, phone_error = clean_phone_number(data['customer__phone_number'])
        # تابع clean_phone_number اصلاح شده همیشه یک شماره معتبر برمی‌گرداند
        data['customer__phone_number'] = mobile_number
    else:
        print(f"هشدار: هیچ شماره تلفنی برای خرید {purchase_number} ارائه نشده است")
        # استفاده از تابع clean_phone_number برای ایجاد شماره پیش‌فرض
        mobile_number, _ = clean_phone_number('')
        data['customer__phone_number'] = mobile_number
        print(f"ایجاد شماره تلفن پیش‌فرض: {mobile_number}")
    
    try:
        # سعی در یافتن خرید موجود
        purchase = Purchase.objects.get(purchase_number=purchase_number)
        created = False
        
        # به‌روزرسانی فیلدهای ساده
        simple_fields = [
            'delivered_weight', 'tracking_number', 'address', 
            'tahvil_phone_number', 'amount_paid', 'payment_method', 
            'customer_price', 'code_melli_tahvil', 'order_weight'
        ]
        
        for field in simple_fields:
            if field in data and data[field]:
                setattr(purchase, field, data[field])
        
        # به‌روزرسانی فیلدهای مشتری
        if purchase.customer:
            if 'customer__name' in data and data['customer__name']:
                purchase.customer.name = data['customer__name']
            
            if 'customer__city' in data and data['customer__city']:
                purchase.customer.city = data['customer__city']
            
            if mobile_number and 'customer__phone_number' in data:
                primary_phone = purchase.customer.get_primary_phone()
                
                if primary_phone != mobile_number:
                    # به‌روزرسانی شماره تلفن اصلی
                    phone = purchase.customer.phone_numbers.filter(is_primary=True).first()
                    if phone:
                        try:
                            phone.number = mobile_number
                            phone.save()
                        except Exception as e:
                            # خطا در به‌روزرسانی شماره تلفن را نادیده می‌گیریم
                            print(f"خطا در به‌روزرسانی شماره تلفن: {str(e)}")
                    else:
                        # ایجاد شماره تلفن جدید
                        try:
                            PhoneNumber.objects.create(
                                customer=purchase.customer,
                                number=mobile_number,
                                is_primary=True
                            )
                        except Exception as e:
                            # خطا در ایجاد شماره تلفن را نادیده می‌گیریم
                            print(f"خطا در ایجاد شماره تلفن: {str(e)}")
            
            # به‌روزرسانی حیطه فعالیت مشتری
            if 'customer__activity_field' in data and data['customer__activity_field']:
                try:
                    from core.CustomerModel import ActivityField
                    activity_field_code = data['customer__activity_field'].lower()
                    
                    # تبدیل کد حیطه فعالیت به کد استاندارد
                    if 'دام' in activity_field_code or 'دامدار' in activity_field_code:
                        activity_field_code = 'livestock'
                    elif 'طیور' in activity_field_code or 'مرغدار' in activity_field_code:
                        activity_field_code = 'poultry'
                    elif 'آبزی' in activity_field_code or 'ماهی' in activity_field_code:
                        activity_field_code = 'aquaculture'
                    else:
                        activity_field_code = 'other'
                    
                    # یافتن یا ایجاد حیطه فعالیت
                    activity_field, created = ActivityField.objects.get_or_create(code=activity_field_code)
                    
                    # اضافه کردن حیطه فعالیت به مشتری اگر وجود نداشته باشد
                    if not purchase.customer.field_of_activity.filter(code=activity_field_code).exists():
                        purchase.customer.field_of_activity.add(activity_field)
                        print(f"حیطه فعالیت {activity_field_code} به مشتری {purchase.customer.name} اضافه شد")
                except Exception as e:
                    print(f"خطا در به‌روزرسانی حیطه فعالیت: {str(e)}")
            
            # ذخیره تغییرات مشتری
            purchase.customer.save()
        
        # به‌روزرسانی تاریخ‌ها در صورت نیاز
        if 'created_at' in data and data['created_at']:
            # استفاده از تابع جدید برای تبدیل تاریخ
            persian_date = data['created_at']
            gregorian_date = convert_persian_date_to_gregorian(persian_date)
            if gregorian_date:
                purchase.created_at = gregorian_date
        
        # به‌روزرسانی اطلاعات کوتاژ
        if 'cargo__cottage' in data and data['cargo__cottage']:
            cottage_number = data.get('cargo__cottage')
            try:
                # بررسی وجود محصول با شماره کوتاژ
                cargo = CargoProduct.objects.get(cottage=cottage_number)
                # فقط کوتاژ را به خرید اختصاص می‌دهیم، به قیمت کوتاژ دست نمی‌زنیم
                purchase.cargo = cargo
                print(f"کوتاژ موجود {cottage_number} به خرید {purchase_number} اختصاص داده شد")
            except CargoProduct.DoesNotExist:
                # ایجاد محصول جدید اگر وجود نداشت
                product_type = 'other'
                if 'cargo__product_type' in data:
                    product_type = determine_product_type(data['cargo__product_type'])
                
                # ایجاد کوتاژ جدید با قیمت پیش‌فرض صفر - قیمت باید توسط ادمین سیستم تنظیم شود
                cargo = CargoProduct.objects.create(
                    type='bazaargah',
                    cottage=cottage_number,
                    company_price=0,  # همیشه صفر
                    customer_price=0,  # قیمت پیش‌فرض صفر - باید توسط ادمین تنظیم شود
                    product_type=product_type,
                    country='australia',  # پیش‌فرض: استرالیا
                    port='امام خمینی',  # پیش‌فرض
                    weight=1000000  # پیش‌فرض: 1000 تن
                )
                purchase.cargo = cargo
                print(f"محصول جدید با کوتاژ {cottage_number} و نوع {product_type} ایجاد شد - قیمت باید توسط ادمین تنظیم شود")
        
        # ثبت شناسه تخصیص
        if 'shenase_takhsis' in data and data['shenase_takhsis']:
            from core.PurchaseModel import ShenaseTakhsis
            
            # شناسه تخصیص ممکن است یک رشته حاوی چندین شناسه باشد
            allocation_ids = str(data['shenase_takhsis']).split(',')
            
            for allocation_id in allocation_ids:
                allocation_id = allocation_id.strip()
                if allocation_id:
                    # بررسی وجود شناسه تخصیص
                    try:
                        ShenaseTakhsis.objects.get_or_create(
                            purchase=purchase,
                            code=allocation_id
                        )
                        print(f"شناسه تخصیص {allocation_id} برای خرید {purchase_number} ثبت شد")
                    except Exception as e:
                        print(f"خطا در ثبت شناسه تخصیص {allocation_id}: {str(e)}")
            
            # به‌روزرسانی فیلد shenase_takhsis در خرید
            purchase.shenase_takhsis = data['shenase_takhsis']
        
        # محاسبه و به‌روزرسانی اختلاف (سرک/کسری)
        if 'order_weight' in data and 'delivered_weight' in data:
            order_weight = int(data.get('order_weight', 0))
            delivered_weight = int(data.get('delivered_weight', 0))
            
            if order_weight > 0 and delivered_weight > 0:
                # محاسبه اختلاف وزن
                weight_diff = delivered_weight - order_weight
                
                if weight_diff != 0:
                    # تعیین نوع اختلاف (سرک یا کسری)
                    extelaf_type = 'سرک' if weight_diff > 0 else 'کسری'
                    
                    # مقدار مطلق اختلاف وزن
                    extelaf_weight = abs(weight_diff)
                    
                    # محاسبه مبلغ اختلاف
                    customer_price = int(data.get('customer_price', 0))
                    if customer_price <= 0 and purchase.customer_price > 0:
                        customer_price = purchase.customer_price
                        
                    if customer_price <= 0 and purchase.cargo and purchase.cargo.customer_price > 0:
                        customer_price = purchase.cargo.customer_price
                        
                    extelaf_amount = extelaf_weight * customer_price
                    
                    # ذخیره اطلاعات اختلاف
                    purchase.extelaf_type = extelaf_type
                    purchase.extelaf_weight = extelaf_weight
                    purchase.extelaf_amount = extelaf_amount
                    
                    print(f"اختلاف محاسبه شد: نوع={extelaf_type}, وزن={extelaf_weight}, مبلغ={extelaf_amount}")
                    
                    # تغییر وضعیت به DIFFERENCE_APPROVED اگر وزن بارنامه شده داشته باشیم
                    if delivered_weight > 0:
                        purchase.state = 'DIFFERENCE_APPROVED'
                        print(f"وضعیت خرید به DIFFERENCE_APPROVED تغییر کرد")
        
        # به‌روزرسانی خرید
        purchase.updated_at = timezone.now()
        purchase.save()
        
        return purchase, created, None
    
    except Purchase.DoesNotExist:
        if not create_if_not_exists:
            return None, False, f"خرید با شماره {purchase_number} یافت نشد"
        
        # ایجاد خرید جدید
        try:
            # واردات مدل‌های مورد نیاز
            from core.SalesAgentModel import SalesAgent
            from core.CustomerModel import ActivityField
            from core.PurchaseModel import ShenaseTakhsis
            
            # 1. یافتن یا ایجاد مشتری
            if not mobile_number:
                # این نباید هرگز اتفاق بیفتد چون همیشه یک شماره موبایل معتبر ایجاد می‌کنیم
                return None, False, "خطای داخلی در پردازش شماره موبایل مشتری"
            
            customer = None
            customer_existed = False
            
            # جستجوی مشتری با شماره تلفن
            customer = Customer.get_customer_by_phone(mobile_number)
            customer_existed = customer is not None
            
            if not customer:
                # ایجاد مشتری جدید
                customer = Customer.objects.create(
                    name=data.get('customer__name', 'مشتری ناشناس'),
                    city=data.get('customer__city'),
                    phone_number=mobile_number,  # تنظیم فیلد موروثی شماره تلفن برای حفظ سازگاری با کد قدیمی
                )
                
                # یافتن کارشناس فروش "مدیریت سیستم"
                try:
                    system_admin = SalesAgent.objects.get(user__username='admin')
                    customer.sales_agent.add(system_admin)
                except (SalesAgent.DoesNotExist, SalesAgent.MultipleObjectsReturned) as e:
                    # اگر کارشناس فروش مورد نظر پیدا نشد، سعی می‌کنیم اولین کارشناس فروش موجود را انتخاب کنیم
                    try:
                        first_agent = SalesAgent.objects.first()
                        if first_agent:
                            customer.sales_agent.add(first_agent)
                    except Exception:
                        pass  # اگر هیچ کارشناس فروشی موجود نبود، ادامه می‌دهیم
                
                # ایجاد شماره تلفن برای مشتری
                try:
                    PhoneNumber.objects.create(
                        customer=customer,
                        number=mobile_number,
                        is_primary=True
                    )
                except Exception as e:
                    # اگر ایجاد شماره تلفن با خطا مواجه شد، مشتری را حذف می‌کنیم
                    customer.delete()
                    return None, False, f"خطا در ایجاد شماره تلفن: {str(e)}"
            
            # تنظیم حیطه فعالیت مشتری
            if 'customer__activity_field' in data and data['customer__activity_field']:
                try:
                    activity_field_code = data['customer__activity_field'].lower()
                    
                    # تبدیل کد حیطه فعالیت به کد استاندارد
                    if 'دام' in activity_field_code or 'دامدار' in activity_field_code:
                        activity_field_code = 'livestock'
                    elif 'طیور' in activity_field_code or 'مرغدار' in activity_field_code:
                        activity_field_code = 'poultry'
                    elif 'آبزی' in activity_field_code or 'ماهی' in activity_field_code:
                        activity_field_code = 'aquaculture'
                    else:
                        activity_field_code = 'other'
                    
                    # یافتن یا ایجاد حیطه فعالیت
                    activity_field, created = ActivityField.objects.get_or_create(code=activity_field_code)
                    
                    # اضافه کردن حیطه فعالیت به مشتری
                    customer.field_of_activity.add(activity_field)
                    print(f"حیطه فعالیت {activity_field_code} به مشتری {customer.name} اضافه شد")
                except Exception as e:
                    print(f"خطا در تنظیم حیطه فعالیت: {str(e)}")
            else:
                # تنظیم حیطه فعالیت پیش‌فرض (دامداری)
                try:
                    default_activity = ActivityField.objects.get_or_create(code='livestock')[0]
                    customer.field_of_activity.add(default_activity)
                except Exception as e:
                    print(f"خطا در تنظیم حیطه فعالیت پیش‌فرض: {str(e)}")
            
            # 2. یافتن یا ایجاد محصول
            cottage_number = data.get('cargo__cottage')
            cargo = None
            cargo_existed = False
            
            if cottage_number:
                try:
                    cargo = CargoProduct.objects.get(cottage=cottage_number)
                    cargo_existed = True
                except CargoProduct.DoesNotExist:
                    # ایجاد محصول جدید
                    product_type = 'other'
                    if 'cargo__product_type' in data:
                        product_type = determine_product_type(data['cargo__product_type'])
                    
                    # ایجاد کوتاژ جدید با قیمت پیش‌فرض صفر - قیمت باید توسط ادمین سیستم تنظیم شود
                    cargo = CargoProduct.objects.create(
                        type='bazaargah',
                        cottage=cottage_number,
                        company_price=0,  # همیشه صفر
                        customer_price=0,  # قیمت پیش‌فرض صفر - باید توسط ادمین تنظیم شود
                        product_type=product_type,
                        country='australia',  # پیش‌فرض: استرالیا
                        port='امام خمینی',  # پیش‌فرض
                        weight=1000000  # پیش‌فرض: 1000 تن
                    )
                    print(f"محصول جدید با کوتاژ {cottage_number} و نوع {product_type} ایجاد شد - قیمت باید توسط ادمین تنظیم شود")
            
            # تعیین وضعیت اولیه خرید
            initial_state = 'PAYMENT_VERIFIED'
            delivered_weight = int(data.get('delivered_weight', 0))
            if delivered_weight > 0:
                initial_state = 'DIFFERENCE_APPROVED'
                print(f"وضعیت اولیه خرید به DIFFERENCE_APPROVED تنظیم شد (وزن بارنامه شده: {delivered_weight})")
            
            # 3. ایجاد خرید جدید
            new_purchase = Purchase.objects.create(
                purchase_number=purchase_number,
                customer=customer,
                cargo=cargo,
                address=data.get('address'),
                delivered_weight=data.get('delivered_weight', 0),
                order_weight=data.get('order_weight', 0),
                tracking_number=data.get('tracking_number'),
                tahvil_phone_number=data.get('tahvil_phone_number'),
                amount_paid=data.get('amount_paid', 0),
                payment_method=data.get('payment_method', 'نقدی'),
                customer_price=data.get('customer_price', 0),
                company_price=0,  # همیشه صفر
                code_melli_tahvil=data.get('code_melli_tahvil'),
                type='bazaargah',
                state=initial_state
            )
            
            # ثبت شناسه تخصیص
            if 'shenase_takhsis' in data and data['shenase_takhsis']:
                # شناسه تخصیص ممکن است یک رشته حاوی چندین شناسه باشد
                allocation_ids = str(data['shenase_takhsis']).split(',')
                
                for allocation_id in allocation_ids:
                    allocation_id = allocation_id.strip()
                    if allocation_id:
                        # ثبت شناسه تخصیص
                        try:
                            ShenaseTakhsis.objects.create(
                                purchase=new_purchase,
                                code=allocation_id
                            )
                            print(f"شناسه تخصیص {allocation_id} برای خرید {purchase_number} ثبت شد")
                        except Exception as e:
                            print(f"خطا در ثبت شناسه تخصیص {allocation_id}: {str(e)}")
                
                # به‌روزرسانی فیلد shenase_takhsis در خرید
                new_purchase.shenase_takhsis = data['shenase_takhsis']
                new_purchase.save(update_fields=['shenase_takhsis'])
            
            # محاسبه و ذخیره اختلاف (سرک/کسری)
            order_weight = int(data.get('order_weight', 0))
            delivered_weight = int(data.get('delivered_weight', 0))
            
            if order_weight > 0 and delivered_weight > 0:
                # محاسبه اختلاف وزن
                weight_diff = delivered_weight - order_weight
                
                if weight_diff != 0:
                    # تعیین نوع اختلاف (سرک یا کسری)
                    extelaf_type = 'سرک' if weight_diff > 0 else 'کسری'
                    
                    # مقدار مطلق اختلاف وزن
                    extelaf_weight = abs(weight_diff)
                    
                    # محاسبه مبلغ اختلاف
                    customer_price = int(data.get('customer_price', 0))
                    if customer_price <= 0 and cargo and cargo.customer_price > 0:
                        customer_price = cargo.customer_price
                    
                    extelaf_amount = extelaf_weight * customer_price
                    
                    # ذخیره اطلاعات اختلاف
                    new_purchase.extelaf_type = extelaf_type
                    new_purchase.extelaf_weight = extelaf_weight
                    new_purchase.extelaf_amount = extelaf_amount
                    new_purchase.save(update_fields=['extelaf_type', 'extelaf_weight', 'extelaf_amount'])
                    
                    print(f"اختلاف محاسبه شد: نوع={extelaf_type}, وزن={extelaf_weight}, مبلغ={extelaf_amount}")
            
            # افزودن پرچم‌ها برای پیگیری وجود قبلی اشیاء (برای گزارش‌دهی)
            new_purchase._customer_existed = customer_existed
            new_purchase._cargo_existed = cargo_existed
            
            # تنظیم تاریخ ایجاد در صورت وجود
            if 'created_at' in data and data['created_at']:
                # استفاده از تابع جدید برای تبدیل تاریخ
                persian_date = data['created_at']
                gregorian_date = convert_persian_date_to_gregorian(persian_date)
                if gregorian_date:
                    new_purchase.created_at = gregorian_date
                    new_purchase.save(update_fields=['created_at'])
            
            return new_purchase, True, None
        
        except Exception as e:
            return None, False, f"خطا در ایجاد خرید: {str(e)}"

def analyze_api_response(response_text):
    """
    بررسی و تحلیل پاسخ API بازارگاه برای شناسایی ساختار و فرمت داده‌ها
    
    Args:
        response_text: متن پاسخ XML از API
        
    Returns:
        dict: اطلاعات تحلیل شده از پاسخ API
    """
    result = {
        'is_valid': False,
        'format': 'unknown',
        'error': None,
        'structure': {},
        'sample_keys': []
    }
    
    try:
        # تجزیه پاسخ XML
        response_dict = xmltodict.parse(response_text)
        
        # بررسی ساختار اصلی
        if 'soap:Envelope' not in response_dict:
            result['error'] = "ساختار SOAP Envelope یافت نشد"
            return result
            
        if 'soap:Body' not in response_dict['soap:Envelope']:
            result['error'] = "ساختار SOAP Body یافت نشد"
            return result
            
        soap_body = response_dict['soap:Envelope']['soap:Body']
        result['structure']['soap_body_keys'] = list(soap_body.keys())
        
        # بررسی نوع پاسخ (getKharidInfo یا getKharidListByDate)
        if 'getKharidInfoResponse' in soap_body:
            result['format'] = 'getKharidInfo'
            response_key = 'getKharidInfoResponse'
            result_key = 'getKharidInfoResult'
        elif 'getKharidListByDateResponse' in soap_body:
            result['format'] = 'getKharidListByDate'
            response_key = 'getKharidListByDateResponse'
            result_key = 'getKharidListByDateResult'
        else:
            result['error'] = f"نوع پاسخ API ناشناخته است. کلیدهای موجود: {', '.join(soap_body.keys())}"
            return result
            
        # بررسی وجود نتیجه
        if result_key not in soap_body[response_key]:
            result['error'] = f"کلید {result_key} در پاسخ یافت نشد"
            return result
            
        api_result = soap_body[response_key][result_key]
        
        if not api_result or not isinstance(api_result, dict):
            result['error'] = "نتیجه API خالی یا نامعتبر است"
            return result
            
        result['structure']['result_keys'] = list(api_result.keys())
        
        # بررسی ساختار diffgram
        if 'diffgr:diffgram' not in api_result:
            result['error'] = "ساختار diffgram در نتیجه یافت نشد"
            return result
            
        diffgram = api_result['diffgr:diffgram']
        result['structure']['diffgram_keys'] = list(diffgram.keys())
        
        if 'NewDataSet' not in diffgram or not diffgram['NewDataSet']:
            result['error'] = "ساختار NewDataSet در diffgram یافت نشد یا خالی است"
            return result
            
        dataset = diffgram['NewDataSet']
        result['structure']['dataset_keys'] = list(dataset.keys())
        
        if 'Table1' not in dataset:
            result['error'] = "ساختار Table1 در NewDataSet یافت نشد"
            return result
            
        table1 = dataset['Table1']
        
        # بررسی نوع داده Table1 (لیست یا دیکشنری)
        if isinstance(table1, list):
            result['structure']['table_type'] = 'list'
            result['structure']['table_count'] = len(table1)
            if table1:
                result['sample_keys'] = list(table1[0].keys())
                
                # بررسی کلیدهای شناسایی فرمت
                if 'idkharid' in table1[0]:
                    result['format'] = 'new_format'
                elif 'kharididentity' in table1[0]:
                    result['format'] = 'old_format'
        else:
            result['structure']['table_type'] = 'dict'
            result['sample_keys'] = list(table1.keys())
            
            # بررسی کلیدهای شناسایی فرمت
            if 'idkharid' in table1:
                result['format'] = 'new_format'
            elif 'kharididentity' in table1:
                result['format'] = 'old_format'
        
        result['is_valid'] = True
        return result
        
    except Exception as e:
        result['error'] = f"خطا در تجزیه و تحلیل پاسخ: {str(e)}"
        import traceback
        result['traceback'] = traceback.format_exc()
        return result 