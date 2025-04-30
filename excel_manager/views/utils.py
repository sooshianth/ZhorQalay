"""
این ماژول شامل توابع کمکی مورد استفاده در پردازش فایل‌های اکسل بازارگاه است.
توابع این ماژول شامل موارد زیر است:
- نرمال‌سازی متن و شماره تلفن
- استخراج استان از آدرس
- مدیریت ستون‌های فایل اکسل
- تبدیل داده‌ها بین قالب‌های مختلف
"""

import os
import pandas as pd
import logging
import re
from django.contrib.auth.models import User
from ..models import CargoProduct
from core.CustomerModel import FIELD_OF_ACTIVITY
from core.decorators.decorators import role_required
from django.contrib.auth.decorators import login_required
# ایجاد یک لاگر برای دیباگ و ثبت وقایع
logger = logging.getLogger(__name__)

# لیست استان‌های ایران برای استخراج استان از آدرس‌ها
IRAN_PROVINCES = [
    'آذربايجان شرقی', 'آذربايجان غربی', 'اردبیل', 'اصفهان', 'البرز', 'ایلام',
    'بوشهر', 'تهران', 'چهارمحال و بختیاری', 'خراسان جنوبی', 'خراسان رضوی',
    'خراسان شمالی', 'خوزستان', 'زنجان', 'سمنان', 'سیستان و بلوچستان',
    'فارس', 'قزوین', 'قم', 'کردستان', 'کرمان', 'کرمانشاه', 'کهگیلویه و بویراحمد',
    'گلستان', 'گیلان', 'لرستان', 'مازندران', 'مرکزی', 'هرمزگان', 'همدان', 'یزد'
]

# حالت‌های مختلف نوشتاری استان‌ها در آدرس‌ها
# این dictionary برای تبدیل املاهای مختلف به فرمت استاندارد استفاده می‌شود
PROVINCE_VARIANTS = {
    'چهارمحال وبختیاری': 'چهارمحال و بختیاری',
    'چهارمحال': 'چهارمحال و بختیاری',
    'سیستان': 'سیستان و بلوچستان',
    'كهگیلویه': 'کهگیلویه و بویراحمد',
    'كهکیلویه': 'کهگیلویه و بویراحمد',
    'کهکیلویه': 'کهگیلویه و بویراحمد',
    'آذربایجان شرقی': 'آذربايجان شرقی',
    'آذربايجان شرقي': 'آذربايجان شرقی',
    'آذربایجان غربی': 'آذربايجان غربی',
    'آذربايجان غربي': 'آذربايجان غربی',
    'مركزی': 'مرکزی',
    'کرمانشاه': 'کرمانشاه',
    'كرمانشاه': 'کرمانشاه',
}

def normalize_text(text):
    """
    نرمال‌سازی متن برای مقایسه بهتر:
    1. تبدیل ی و ک عربی به فارسی 
    2. حذف فاصله‌های اضافی از ابتدا و انتهای متن
    
    ورودی:
        text: متن مورد نظر برای نرمال‌سازی
    خروجی:
        متن نرمال‌سازی شده
    """
    if not text or not isinstance(text, str):
        return ""
    
    text = text.replace('ي', 'ی').replace('ك', 'ک').strip()
    return text

def extract_province_from_address(address):
    """
    استخراج نام استان از آدرس، با بررسی قالب‌های مختلف آدرس:
    
    1. آدرس‌های با فرمت underscore (آدرس‌های بازارگاه)
    2. آدرس‌هایی که با نام استان شروع می‌شوند
    3. آدرس‌هایی که با خط تیره یا علامت‌های خاص جدا شده‌اند
    
    ورودی:
        address: آدرس کامل
    خروجی:
        نام استان استخراج شده یا None در صورت عدم شناسایی
    """
    if not address or not isinstance(address, str):
        return None
        
    # پاکسازی و نرمالیزه کردن آدرس
    address = address.strip()
    
    # بررسی آدرس‌های با فرمت underscore (بیشتر آدرس‌های بازارگاه)
    if '_' in address:
        # استان معمولا اولین قسمت آدرس قبل از اولین underscore است
        parts = address.split('_')
        if parts and parts[0]:
            province_candidate = parts[0].strip()
            
            # نرمال‌سازی متن استان
            normalized_candidate = normalize_text(province_candidate)
            
            # بررسی در لیست استان‌ها
            for province in IRAN_PROVINCES:
                if normalize_text(province) == normalized_candidate:
                    return province
            
            # بررسی در متغیرهای مختلف استان‌ها
            for variant, standard in PROVINCE_VARIANTS.items():
                if normalize_text(variant) == normalized_candidate:
                    return standard
                    
            # اگر مطابقت دقیق پیدا نشد، بررسی کنیم آیا استان شامل نام استانی هست
            for province in IRAN_PROVINCES:
                if normalize_text(province) in normalized_candidate:
                    return province
            
            # برای استان‌هایی که بخشی از آن‌ها در آدرس آمده
            for variant, standard in PROVINCE_VARIANTS.items():
                if normalize_text(variant) in normalized_candidate:
                    return standard
                    
            # برگشت خود متن اولیه اگر هیچکدام از موارد بالا مطابقت نداشت
            return province_candidate
    
    # بررسی اینکه آیا آدرس با یکی از استان‌ها شروع می‌شود
    for province in IRAN_PROVINCES:
        if address.startswith(province):
            return province
            
    # بررسی متغیرهای مختلف استان‌ها
    for variant, standard in PROVINCE_VARIANTS.items():
        if address.startswith(variant):
            return standard
            
    # جستجو برای الگوهای رایج - آدرس‌هایی که با خط تیره جدا شده‌اند
    address_parts = address.split("-")
    if len(address_parts) > 0:
        first_part = address_parts[0].strip()
        for province in IRAN_PROVINCES:
            if province in first_part:
                return province
                
        for variant, standard in PROVINCE_VARIANTS.items():
            if variant in first_part:
                return standard
    
    # جستجو برای آدرس‌هایی که با کاما جدا شده‌اند            
    address_parts = address.split("،")
    if len(address_parts) > 0:
        first_part = address_parts[0].strip()
        for province in IRAN_PROVINCES:
            if province in first_part:
                return province
                
        for variant, standard in PROVINCE_VARIANTS.items():
            if variant in first_part:
                return standard
    
    # اگر استان پیدا نشد
    return None

def get_excel_columns(file_path):
    """
    نمایش ستون‌های موجود در فایل اکسل - کمک به شناسایی ساختار فایل
    
    این تابع بررسی می‌کند که آیا فایل HTML است یا یک فایل اکسل معمولی،
    و سپس ستون‌های آن را استخراج می‌کند.
    
    ورودی:
        file_path: مسیر فایل اکسل
    خروجی:
        لیستی از نام ستون‌های فایل
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '<html' in content.lower():
            df = pd.read_html(content)[0]
            
            # پیدا کردن ردیف header
            header_row = None
            for idx, row in df.iterrows():
                if any('ثبت اطلاعات حمل' in str(val) for val in row.values):
                    continue
                if any(col in str(row.values) for col in ['کد', 'شناسه تخصیص']):
                    header_row = idx
                    break
            
            if header_row is not None:
                df.columns = df.iloc[header_row]
                df = df.iloc[header_row + 1:].reset_index(drop=True)
            
            return df.columns.tolist()
    except Exception as e:
        logger.error(f"خطا در خواندن ستون‌های فایل: {str(e)}")
        return []

def fix_excel_headers(df):
    """
    تشخیص و اصلاح سربرگ‌های فایل اکسل
    
    در بازارگاه، سربرگ‌ها در فایل‌های مختلف ممکن است در ردیف‌های متفاوت باشند.
    این تابع سعی می‌کند سربرگ واقعی را شناسایی کند.
    
    الگوریتم:
    1. بررسی وجود ستون‌های مهم در دیتافریم
    2. جستجو در ردیف‌های ابتدایی برای یافتن سربرگ
    3. شناسایی سربرگ‌ها بر اساس الگوی "ثبت اطلاعات حمل"
    
    ورودی:
        df: دیتافریم پاندا
    خروجی:
        دیتافریم با سربرگ‌های صحیح
    """
    # بررسی اینکه آیا ستون‌های مهم در فایل وجود دارند
    important_columns = ['کد', 'شناسه تخصیص', 'کد کوتاژ', 'کوتاژ']
    has_headers = any(col in df.columns for col in important_columns)
    
    if has_headers:
        # سربرگ‌ها به درستی شناسایی شده‌اند
        return df
    
    # بررسی ردیف‌های اول برای یافتن سربرگ‌ها
    for idx in range(min(5, len(df))):  # بررسی 5 ردیف اول
        # بررسی وجود متن "ثبت اطلاعات حمل" که معمولا قبل از سربرگ‌ها است
        row_values = df.iloc[idx].astype(str).tolist()
        if any('ثبت اطلاعات حمل' in str(val) for val in row_values):
            # ردیف بعدی احتمالا سربرگ‌ها هستند
            if idx + 1 < len(df):
                header_idx = idx + 1
                # تنظیم سربرگ‌ها و حذف ردیف‌های اضافی
                df.columns = df.iloc[header_idx]
                df = df.iloc[header_idx + 1:].reset_index(drop=True)
                return df
        
        # بررسی وجود ستون‌های مهم در ردیف
        row = df.iloc[idx].astype(str)
        if any(col in row.values for col in important_columns):
            # این ردیف احتمالا سربرگ‌ها هستند
            df.columns = df.iloc[idx]
            df = df.iloc[idx + 1:].reset_index(drop=True)
            return df
    
    # اگر سربرگ‌ها پیدا نشدند، دیتافریم را بدون تغییر برگردان
    return df

def map_excel_field_to_model(field_value):
    """
    نگاشت نوع کاربری (زمینه فعالیت) از فایل اکسل به فیلد مدل مشتری
    
    این تابع مقادیر مختلف زمینه فعالیت در فایل اکسل را به مقادیر
    استاندارد مدل Customer نگاشت می‌کند.
    
    ورودی:
        field_value: مقدار زمینه فعالیت در فایل اکسل
    خروجی:
        لیستی از کدهای زمینه فعالیت (مثل ['chicken', 'factory'])
    """
    # اگر مقدار None یا تهی بود
    if not field_value or not isinstance(field_value, str):
        return ['chicken']  # مقدار پیش‌فرض

    field_value = field_value.strip()
    
    # لیستی برای نگهداری همه کدهای مرتبط با زمینه فعالیت
    activity_codes = []
    
    FIELD_MAP = {
        'مرغداری': 'chicken',
        'مرغدار': 'chicken',
        'دامداری': 'livestock',
        'دامدار': 'livestock',
        'گاوداری': 'livestock',
        'تولیدی مرغ': 'chicken',
        'تعاونی': 'corporation',
        'دلال': 'dealer',
        'بازرگان': 'dealer',
        'کارخانه': 'factory',
        'کارخانه خوراک': 'factory',
        'خریداران كارخانه خوراك': 'factory',
        'آبزی': 'fish',
        'پرورش آبزیان': 'fish',
        'ماهی': 'fish',
        'اتحادیه': 'association',
    }
    
    # بررسی تمام کلیدواژه‌ها و اضافه کردن کدهای مرتبط به لیست
    for k, v in FIELD_MAP.items():
        if k in field_value and v not in activity_codes:
            activity_codes.append(v)
    
    # اگر هیچ کدی پیدا نشد، مقدار پیش‌فرض را برگردان
    if not activity_codes:
        activity_codes = ['chicken']
        
    return activity_codes

def get_super_user_agent():
    """
    دریافت کارشناس فروش برای مشتریان جدید
    
    این تابع یک کاربر ادمین (superuser) را پیدا می‌کند
    و کارشناس فروش مرتبط با آن را برمی‌گرداند.
    
    خروجی:
        نمونه sales_agent مربوط به superuser یا None
    """
    # super_user = User.objects.filter(is_superuser=True).first()
    # super_agent = None
    # if super_user and hasattr(super_user, 'sales_agent'):
    #     super_agent = super_user.sales_agent
    # return super_agent 
    super_agent = User.objects.filter(username='Ms_Sadri').first()
    return super_agent.sales_agent

def test_manytomany_fields():
    """
    تابع تست برای امتحان کردن تبدیل فیلدهای ManyToMany در مدل Customer
    
    این تابع می‌تواند به صورت زیر فراخوانی شود:
    
    از داخل پوسته جنگو:
    from excel_manager.views.utils import test_manytomany_fields
    test_manytomany_fields()
    """
    from core.CustomerModel import Customer, ActivityField, PaymentPreference, ProductPreference
    
    # نمونه‌هایی از مقادیر از فایل اکسل
    sample_activities = [
        "مرغداری",
        "دامداری و تعاونی",
        "کارخانه خوراک",
        "اتحادیه مرغداران"
    ]
    
    # نتایج تبدیل
    results = []
    for activity in sample_activities:
        # تبدیل به کد
        codes = map_excel_field_to_model(activity)
        
        # ایجاد یک مشتری آزمایشی با این کدها
        test_customer = Customer(name=f"Test for {activity}")
        test_customer.save()
        
        # تنظیم زمینه فعالیت
        test_customer.field_of_activity_list = codes
        
        # دریافت مقادیر نمایشی
        display_value = test_customer.get_field_of_activity_display()
        
        # حذف مشتری آزمایشی
        test_customer.delete()
        
        # ذخیره نتایج
        results.append(f"""
        متن اصلی: {activity}
        کدهای تبدیل شده: {codes}
        نمایش: {display_value}
        """)
    
    return "\n".join(results)
