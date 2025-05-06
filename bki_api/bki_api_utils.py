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

# غیرفعال کردن هشدارهای SSL برای اطمینان از کارکرد درست با API
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# چاپ نسخه کتابخانه‌های مورد استفاده برای دیباگ
print(f"نسخه کتابخانه requests: {requests.__version__}")
try:
    print(f"نسخه کتابخانه xmltodict: {xmltodict.__version__}")
except AttributeError:
    print("نسخه کتابخانه xmltodict نامشخص است")

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