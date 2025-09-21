from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
import io
import xlsxwriter

from major.models.NonBazargahPurchase import NonBazargahPurchase
from major.models.NonBazargahAllocation import NonBazargahAllocation
from major.models.NonBazargahProduct import NonBazargahProduct
from core.CustomerModel import Customer
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from ERP.views.managers_profile_view import get_client_ip
from ERP.models.NotificationService import NotificationService
from bki_barnameh.models.BarnamehModel import Barnameh

from collections import OrderedDict
import logging
import pandas as pd
import os
from django.conf import settings

logger = logging.getLogger("major_non_bazargah_crud")


class ExcelAllocationUploadForm(forms.Form):
    """فرم آپلود فایل اکسل برای تخصیص‌های دسته‌ای"""
    
    excel_file = forms.FileField(
        label='فایل اکسل',
        help_text='فایل اکسل حاوی اطلاعات تخصیص‌ها (فرمت‌های مجاز: .xls, .xlsx)',
        widget=forms.FileInput(attrs={
            'accept': '.xls,.xlsx',
            'class': 'form-control'
        })
    )
    
    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            # بررسی فرمت فایل
            if not file.name.endswith(('.xls', '.xlsx')):
                raise ValidationError('فایل باید با فرمت اکسل (.xls یا .xlsx) باشد.')
            
            # بررسی حجم فایل (حداکثر 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError('حجم فایل نباید از 5 مگابایت بیشتر باشد.')
        
        return file


class ExcelBarnamehUploadForm(forms.Form):
    """فرم آپلود فایل اکسل برای بارنامه‌های دسته‌ای"""
    
    excel_file = forms.FileField(
        label='فایل اکسل',
        help_text='فایل اکسل حاوی اطلاعات بارنامه‌ها (فرمت‌های مجاز: .xls, .xlsx)',
        widget=forms.FileInput(attrs={
            'accept': '.xls,.xlsx',
            'class': 'form-control'
        })
    )
    
    def clean_excel_file(self):
        file = self.cleaned_data.get('excel_file')
        if file:
            # بررسی فرمت فایل
            if not file.name.endswith(('.xls', '.xlsx')):
                raise ValidationError('فایل باید با فرمت اکسل (.xls یا .xlsx) باشد.')
            
            # بررسی حجم فایل (حداکثر 5MB)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError('حجم فایل نباید از 5 مگابایت بیشتر باشد.')
        
        return file


def clean_numeric_value(value):
    """پاکسازی مقادیر عددی از فایل اکسل"""
    if pd.isna(value) or value is None:
        return None
    
    try:
        # تبدیل به رشته و حذف کاراکترهای غیر عددی
        if isinstance(value, str):
            cleaned = ''.join(c for c in value if c.isdigit() or c in '.-')
            if cleaned:
                return float(cleaned)
        else:
            return float(value)
    except (ValueError, TypeError):
        return None
    
    return None


def clean_postal_code(postal_code):
    """پاکسازی کد پستی"""
    if pd.isna(postal_code) or postal_code is None:
        return ''
    
    # تبدیل به رشته و حذف همه کاراکترهای غیر عددی
    cleaned = ''.join(c for c in str(postal_code) if c.isdigit())
    return cleaned


def clean_datetime_value(datetime_value):
    """پاکسازی و تبدیل مقادیر زمانی از فایل اکسل"""
    if pd.isna(datetime_value) or datetime_value is None:
        return None
    
    try:
        # اگر مقدار از نوع datetime است، مستقیماً برگردان
        if isinstance(datetime_value, pd.Timestamp):
            return datetime_value.to_pydatetime()
        
        # اگر رشته است، سعی کن پارس کنی
        if isinstance(datetime_value, str):
            datetime_value = datetime_value.strip()
            if not datetime_value:
                return None
            
            # فرمت‌های مختلف تاریخ و زمان
            datetime_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
                '%Y/%m/%d %H:%M:%S',
                '%Y/%m/%d %H:%M',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%d-%m-%Y %H:%M:%S',
                '%d-%m-%Y %H:%M',
                # فرمت‌های جلالی
                '%Y/%m/%d %H:%M',
                '%Y-%m-%d %H:%M',
            ]
            
            from datetime import datetime
            for fmt in datetime_formats:
                try:
                    return datetime.strptime(datetime_value, fmt)
                except ValueError:
                    continue
        
        # اگر هیچ فرمتی کار نکرد، None برگردان
        return None
        
    except Exception:
        return None


def process_barnameh_excel(file, purchase):
    """پردازش فایل اکسل و ایجاد بارنامه‌ها"""
    try:
        # خواندن فایل اکسل با تنظیمات مناسب
        df = pd.read_excel(file, dtype=str)  # همه ستون‌ها را به صورت رشته بخوان
        
        # بررسی وجود ستون‌های ضروری
        required_columns = ['شناسه تخصیص', 'نام راننده', 'شماره تلفن راننده', 'پلاک خودرو']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                'success': False,
                'message': f'ستون‌های زیر در فایل اکسل یافت نشد: {", ".join(missing_columns)}. ستون‌های موجود: {", ".join(df.columns.tolist())}'
            }
        
        # مرحله اول: اعتبارسنجی همه داده‌ها بدون ایجاد بارنامه
        validation_errors = []
        valid_rows = []
        
        logger.info(f"شروع پردازش فایل اکسل بارنامه‌ها با {len(df)} ردیف")
        
        # دریافت لیست تخصیص‌های موجود برای این خرید
        existing_allocations = list(purchase.allocations.values_list('allocation_number', flat=True))
        # حذف مقادیر None و خالی
        existing_allocations = [str(x) for x in existing_allocations if x is not None and str(x).strip()]
        logger.info(f"شماره‌های تخصیص موجود برای این خرید: {existing_allocations}")
        
        for index, row in df.iterrows():
            try:
                # استخراج داده‌ها از ردیف اکسل
                allocation_number_raw = row.get('شناسه تخصیص', '')
                allocation_number = str(allocation_number_raw).strip()
                
                # لاگ برای دیباگ
                if index < 3:  # فقط برای 3 ردیف اول لاگ کن
                    logger.info(f"ردیف {index + 2}: شماره تخصیص خام: '{allocation_number_raw}', پاک شده: '{allocation_number}'")
                
                driver_name = str(row.get('نام راننده', '')).strip()
                driver_phone = str(row.get('شماره تلفن راننده', '')).strip()
                vehicle_plate = str(row.get('پلاک خودرو', '')).strip()
                barnameh_number = str(row.get('شماره بارنامه', '')).strip() or None
                empty_weight = clean_numeric_value(row.get('وزن خالی', 0))
                loaded_weight = clean_numeric_value(row.get('وزن پر', 0))
                delivered_weight = clean_numeric_value(row.get('وزن تحویلی', 0))
                notes = str(row.get('توضیحات', '')).strip() or None
                
                # استخراج زمان‌های اختیاری از اکسل
                vehicle_arrival_time = clean_datetime_value(row.get('زمان ورود ماشین', None))
                empty_weigh_time = clean_datetime_value(row.get('زمان وزن خالی', None))
                loaded_weigh_time = clean_datetime_value(row.get('زمان وزن پر', None))
                departure_time = clean_datetime_value(row.get('زمان خروج از انبار', None))
                delivery_time = clean_datetime_value(row.get('زمان تحویل', None))
                
                # اعتبارسنجی داده‌ها
                if not allocation_number:
                    validation_errors.append(f'ردیف {index + 2}: شماره تخصیص نمی‌تواند خالی باشد')
                    continue
                
                if not driver_name:
                    validation_errors.append(f'ردیف {index + 2}: نام راننده نمی‌تواند خالی باشد')
                    continue
                
                if not driver_phone:
                    validation_errors.append(f'ردیف {index + 2}: شماره تلفن راننده نمی‌تواند خالی باشد')
                    continue
                
                if not vehicle_plate:
                    validation_errors.append(f'ردیف {index + 2}: پلاک خودرو نمی‌تواند خالی باشد')
                    continue
                
                # بررسی شماره تلفن (حداقل 10 رقم)
                phone_digits = ''.join(c for c in driver_phone if c.isdigit())
                if len(phone_digits) < 10:
                    validation_errors.append(f'ردیف {index + 2}: شماره تلفن راننده باید حداقل 10 رقم باشد')
                    continue
                
                # بررسی وجود تخصیص
                try:
                    allocation = NonBazargahAllocation.objects.get(allocation_number=allocation_number, purchase=purchase)
                    logger.info(f"ردیف {index + 2}: تخصیص با شماره {allocation_number} یافت شد")
                except NonBazargahAllocation.DoesNotExist:
                    validation_errors.append(f'ردیف {index + 2}: تخصیص با شماره {allocation_number} یافت نشد. شماره‌های موجود: {existing_allocations}')
                    continue
                
                # ذخیره ردیف معتبر
                valid_rows.append({
                    'allocation': allocation,
                    'driver_name': driver_name,
                    'driver_phone': driver_phone,
                    'vehicle_plate': vehicle_plate,
                    'barnameh_number': barnameh_number,
                    'empty_weight': empty_weight,
                    'loaded_weight': loaded_weight,
                    'delivered_weight': delivered_weight,
                    'notes': notes,
                    'vehicle_arrival_time': vehicle_arrival_time,
                    'empty_weigh_time': empty_weigh_time,
                    'loaded_weigh_time': loaded_weigh_time,
                    'departure_time': departure_time,
                    'delivery_time': delivery_time,
                    'row_number': index + 2
                })
                
            except Exception as e:
                validation_errors.append(f'ردیف {index + 2}: خطا در پردازش - {str(e)}')
                continue
        
        # اگر خطای اعتبارسنجی وجود دارد، فقط آن‌ها را برگردان
        if validation_errors:
            return {
                'success': False,
                'message': f'{len(validation_errors)} خطا در اعتبارسنجی داده‌ها',
                'errors': validation_errors[:10]  # فقط 10 خطای اول
            }
        
        # مرحله دوم: ایجاد بارنامه‌ها (همه ردیف‌ها معتبر هستند)
        created_barnamehs = 0
        creation_errors = []
        
        # تعیین حداکثر مرحله بر اساس اطلاعات موجود
        max_stage = 'carrier_notified'  # مرحله پایه
        has_empty_weights = any(row['empty_weight'] and row['empty_weight'] > 0 for row in valid_rows)
        has_loaded_weights = any(row['loaded_weight'] and row['loaded_weight'] > 0 for row in valid_rows)
        has_delivered_weights = any(row['delivered_weight'] and row['delivered_weight'] > 0 for row in valid_rows)
        
        # تعیین مرحله نهایی بر اساس اطلاعات موجود
        # برای رفتن به مرحله delivered، باید همه بارنامه‌ها وزن تحویلی داشته باشند
        all_have_delivered_weights = all(row['delivered_weight'] and row['delivered_weight'] > 0 for row in valid_rows)
        
        if all_have_delivered_weights:
            max_stage = 'delivered'
        elif has_loaded_weights:
            max_stage = 'loaded_weighed'
        elif has_empty_weights:
            max_stage = 'empty_weighed'
        else:
            max_stage = 'vehicle_arrived'
        
        logger.info(f"مراحل تشخیص داده شده: empty={has_empty_weights}, loaded={has_loaded_weights}, delivered={has_delivered_weights}, all_delivered={all_have_delivered_weights} -> مرحله نهایی: {max_stage}")
        
        for row_data in valid_rows:
            try:
                # تولید شماره بارنامه: اگر شماره دستی وارد نشده، شماره خودکار بساز
                allocation = row_data['allocation']
                barnameh_number = row_data['barnameh_number']
                
                if not barnameh_number:
                    barnameh_count = allocation.barnamehs.count() + 1
                    allocation_number = allocation.allocation_number or allocation.id
                    barnameh_number = f"{allocation_number}-{barnameh_count}"
                
                # تعیین تاریخ بارنامه بر اساس مرحله نهایی
                barnameh_date = None
                if max_stage in ['loaded_weighed', 'barnameh_issued', 'delivered']:
                    barnameh_date = timezone.now().date()
                
                barnameh = Barnameh.objects.create(
                    non_bazargah_allocation=allocation,
                    non_bazargah_purchase=purchase,
                    type='Non_Bazargah',
                    number=barnameh_number,
                    driver_name=row_data['driver_name'],
                    driver_phone=row_data['driver_phone'],
                    vehicle_plate=row_data['vehicle_plate'],
                    empty_vehicle_weight=row_data['empty_weight'],
                    loaded_vehicle_weight=row_data['loaded_weight'],
                    final_delivered_weight=row_data['delivered_weight'],
                    vehicle_arrival_time=row_data.get('vehicle_arrival_time'),
                    empty_weigh_time=row_data.get('empty_weigh_time'),
                    loaded_weigh_time=row_data.get('loaded_weigh_time'),
                    departure_time=row_data.get('departure_time'),
                    delivery_time=row_data.get('delivery_time'),
                    barnameh_date=barnameh_date
                )
                created_barnamehs += 1
                
            except Exception as e:
                creation_errors.append(f'ردیف {row_data["row_number"]}: خطا در ایجاد بارنامه - {str(e)}')
                continue
        
        # بروزرسانی وضعیت خرید بر اساس اطلاعات بارنامه‌ها
        if created_barnamehs > 0:
            try:
                # بررسی وضعیت فعلی و بروزرسانی در صورت نیاز
                current_state = purchase.state
                state_transition_map = {
                    'carrier_notified': 'vehicle_arrived',
                    'vehicle_arrived': 'empty_weighed',
                    'empty_weighed': 'loaded_weighed',
                    'loaded_weighed': 'barnameh_issued',
                    'barnameh_issued': 'delivered',
                    'delivered': 'delivered'
                }
                
                # تعیین وضعیت جدید بر اساس اطلاعات موجود
                target_states = []
                if all_have_delivered_weights:
                    target_states = ['delivered', 'barnameh_issued', 'loaded_weighed', 'empty_weighed', 'vehicle_arrived']
                elif has_loaded_weights:
                    target_states = ['loaded_weighed', 'empty_weighed', 'vehicle_arrived']
                elif has_empty_weights:
                    target_states = ['empty_weighed', 'vehicle_arrived']
                else:
                    target_states = ['vehicle_arrived']
                
                # پیدا کردن بالاترین وضعیت مناسب
                state_priority = {
                    'carrier_notified': 1,
                    'vehicle_arrived': 2,
                    'empty_weighed': 3,
                    'loaded_weighed': 4,
                    'barnameh_issued': 5,
                    'delivered': 6
                }
                
                # انتخاب وضعیت با بالاترین اولویت
                new_state = current_state
                for state in target_states:
                    if state_priority.get(state, 0) > state_priority.get(new_state, 0):
                        new_state = state
                
                # بروزرسانی وضعیت در صورت نیاز
                if new_state != current_state:
                    purchase.state = new_state
                    purchase.save(update_fields=['state'])
                    logger.info(f"وضعیت خرید {purchase.id} از {current_state} به {new_state} تغییر کرد")
                    
                    # محاسبه وزن‌ها در صورت رسیدن به مرحله مناسب
                    if new_state in ['loaded_weighed', 'barnameh_issued']:
                        try:
                            purchase.update_weights_from_barnamehs(save=False)
                            weight_difference = purchase.calculate_net_weight_difference()
                            weight_difference_amount = purchase.calculate_weight_difference_amount()
                            
                            if weight_difference is not None:
                                purchase.weight_difference = weight_difference
                            if weight_difference_amount is not None:
                                purchase.weight_difference_amount = weight_difference_amount
                            
                            purchase.save()
                            logger.info(f"وزن‌های خرید {purchase.id} بروزرسانی شد")
                        except Exception as e:
                            logger.error(f"خطا در بروزرسانی وزن‌ها: {str(e)}")
                
            except Exception as e:
                logger.error(f"خطا در بروزرسانی وضعیت خرید: {str(e)}")
                creation_errors.append(f"خطا در بروزرسانی وضعیت خرید: {str(e)}")
        
        # نتیجه نهایی
        if created_barnamehs > 0:
            # تعیین مرحله نهایی برای نمایش
            stage_names = {
                'carrier_notified': 'اعلام بار به باربری',
                'vehicle_arrived': 'ورود ماشین',
                'empty_weighed': 'وزن خالی',
                'loaded_weighed': 'وزن پر',
                'barnameh_issued': 'صدور بارنامه',
                'delivered': 'تحویل به مشتری'
            }
            
            message = f'{created_barnamehs} بارنامه با موفقیت ایجاد شد'
            
            # اضافه کردن اطلاعات مرحله
            if all_have_delivered_weights:
                message += f' - وضعیت خرید به "تحویل به مشتری" تغییر کرد'
            elif has_loaded_weights:
                message += f' - وضعیت خرید به "وزن پر" تغییر کرد'
            elif has_empty_weights:
                message += f' - وضعیت خرید به "وزن خالی" تغییر کرد'
            else:
                message += f' - وضعیت خرید به "ورود ماشین" تغییر کرد'
            
            if creation_errors:
                message += f' - {len(creation_errors)} خطا در ایجاد بارنامه‌ها'
            
            return {
                'success': True,
                'message': message,
                'created_count': created_barnamehs,
                'final_stage': max_stage,
                'stage_name': stage_names.get(max_stage, max_stage),
                'errors': creation_errors[:5] if creation_errors else []  # فقط 5 خطای اول
            }
        else:
            return {
                'success': False,
                'message': 'هیچ بارنامه‌ای ایجاد نشد',
                'errors': creation_errors
            }
            
    except Exception as e:
        logger.error(f"خطا در پردازش فایل اکسل بارنامه‌ها: {str(e)}")
        return {
            'success': False,
            'message': f'خطا در پردازش فایل اکسل: {str(e)}'
        }


def process_allocation_excel(file, purchase):
    """پردازش فایل اکسل و ایجاد تخصیص‌ها"""
    try:
        # خواندن فایل اکسل با تنظیمات مناسب
        df = pd.read_excel(file, dtype=str)  # همه ستون‌ها را به صورت رشته بخوان
        
        # بررسی وجود ستون‌های ضروری
        required_columns = ['آدرس تحویل', 'کد پستی', 'نام گیرنده', 'شماره هماهنگی', 'وزن تخصیص یافته']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return {
                'success': False,
                'message': f'ستون‌های زیر در فایل اکسل یافت نشد: {", ".join(missing_columns)}. ستون‌های موجود: {", ".join(df.columns.tolist())}'
            }
        
        # مرحله اول: اعتبارسنجی همه داده‌ها بدون ایجاد تخصیص
        validation_errors = []
        valid_rows = []
        total_weight_to_add = 0
        
        logger.info(f"شروع پردازش فایل اکسل با {len(df)} ردیف")
        
        for index, row in df.iterrows():
            try:
                # استخراج داده‌ها از ردیف اکسل
                delivery_address = str(row.get('آدرس تحویل', '')).strip()
                
                # پردازش کد پستی - ممکنه به صورت عدد ذخیره شده باشه
                postal_code_raw = row.get('کد پستی', '')
                delivery_postal_code = clean_postal_code(postal_code_raw)
                
                # لاگ برای دیباگ
                if index < 3:  # فقط برای 3 ردیف اول لاگ کن
                    logger.info(f"ردیف {index + 2}: کد پستی خام: '{postal_code_raw}', پاک شده: '{delivery_postal_code}', طول: {len(delivery_postal_code)}")
                
                delivery_receiver_name = str(row.get('نام گیرنده', '')).strip()
                
                # پردازش شماره تلفن - ممکنه به صورت عدد ذخیره شده باشه
                phone_raw = row.get('شماره هماهنگی', '')
                if pd.isna(phone_raw):
                    coordination_phone = ''
                else:
                    coordination_phone = str(phone_raw).strip()
                
                allocated_weight = clean_numeric_value(row.get('وزن تخصیص یافته', 0))
                allocation_number = str(row.get('شماره تخصیص', '')).strip() or None
                notes = str(row.get('توضیحات', '')).strip() or None
                
                # اعتبارسنجی داده‌ها
                if not delivery_address:
                    validation_errors.append(f'ردیف {index + 2}: آدرس تحویل نمی‌تواند خالی باشد')
                    continue
                
                if not delivery_postal_code:
                    validation_errors.append(f'ردیف {index + 2}: کد پستی نمی‌تواند خالی باشد')
                    continue
                
                if not delivery_receiver_name:
                    validation_errors.append(f'ردیف {index + 2}: نام گیرنده نمی‌تواند خالی باشد')
                    continue
                
                if not coordination_phone:
                    validation_errors.append(f'ردیف {index + 2}: شماره هماهنگی نمی‌تواند خالی باشد')
                    continue
                
                if not allocated_weight or allocated_weight <= 0:
                    validation_errors.append(f'ردیف {index + 2}: وزن تخصیص یافته باید بزرگتر از صفر باشد')
                    continue
                
                # بررسی کد پستی (10 رقم)
                if len(delivery_postal_code) != 10:
                    validation_errors.append(f'ردیف {index + 2}: کد پستی باید 10 رقم باشد (ورودی: "{delivery_postal_code}" -> طول: {len(delivery_postal_code)})')
                    continue
                
                # بررسی شماره تلفن (حداقل 10 رقم)
                phone_digits = ''.join(c for c in coordination_phone if c.isdigit())
                if len(phone_digits) < 10:
                    validation_errors.append(f'ردیف {index + 2}: شماره هماهنگی باید حداقل 10 رقم باشد')
                    continue
                
                # ذخیره ردیف معتبر
                valid_rows.append({
                    'delivery_address': delivery_address,
                    'delivery_postal_code': delivery_postal_code,  # استفاده از کد پستی پاک شده
                    'delivery_receiver_name': delivery_receiver_name,
                    'coordination_phone': coordination_phone,
                    'allocated_weight': int(allocated_weight),
                    'allocation_number': allocation_number,
                    'notes': notes,
                    'row_number': index + 2
                })
                
                total_weight_to_add += int(allocated_weight)
                
            except Exception as e:
                validation_errors.append(f'ردیف {index + 2}: خطا در پردازش - {str(e)}')
                continue
        
        # بررسی وزن کل قبل از ایجاد تخصیص‌ها
        current_remaining_weight = purchase.get_remaining_weight_for_allocation()
        if total_weight_to_add > current_remaining_weight:
            return {
                'success': False,
                'message': f'وزن کل تخصیص‌های اکسل ({total_weight_to_add} کیلوگرم) از وزن باقی‌مانده ({current_remaining_weight} کیلوگرم) بیشتر است. لطفاً وزن‌ها را کاهش دهید.'
            }
        
        # اگر خطای اعتبارسنجی وجود دارد، فقط آن‌ها را برگردان
        if validation_errors:
            return {
                'success': False,
                'message': f'{len(validation_errors)} خطا در اعتبارسنجی داده‌ها',
                'errors': validation_errors[:10]  # فقط 10 خطای اول
            }
        
        # مرحله دوم: ایجاد تخصیص‌ها (همه ردیف‌ها معتبر هستند)
        created_allocations = 0
        creation_errors = []
        
        for row_data in valid_rows:
            try:
                allocation = NonBazargahAllocation.objects.create(
                    purchase=purchase,
                    allocation_number=row_data['allocation_number'],
                    delivery_address=row_data['delivery_address'],
                    delivery_postal_code=row_data['delivery_postal_code'],
                    delivery_receiver_name=row_data['delivery_receiver_name'],
                    coordination_phone=row_data['coordination_phone'],
                    allocated_weight=row_data['allocated_weight'],
                    notes=row_data['notes']
                )
                created_allocations += 1
                
            except Exception as e:
                creation_errors.append(f'ردیف {row_data["row_number"]}: خطا در ایجاد تخصیص - {str(e)}')
                continue
        
        # نتیجه نهایی
        if created_allocations > 0:
            message = f'{created_allocations} تخصیص با موفقیت ایجاد شد (مجموع وزن: {total_weight_to_add} کیلوگرم)'
            if creation_errors:
                message += f' - {len(creation_errors)} خطا در ایجاد تخصیص‌ها'
            
            return {
                'success': True,
                'message': message,
                'created_count': created_allocations,
                'total_weight': total_weight_to_add,
                'errors': creation_errors[:5] if creation_errors else []  # فقط 5 خطای اول
            }
        else:
            return {
                'success': False,
                'message': 'هیچ تخصیصی ایجاد نشد',
                'errors': creation_errors
            }
            
    except Exception as e:
        logger.error(f"خطا در پردازش فایل اکسل: {str(e)}")
        return {
            'success': False,
            'message': f'خطا در پردازش فایل اکسل: {str(e)}'
        }


class NonBazargahAllocationForm(forms.ModelForm):
    """فرم تخصیص آدرس - جایگزین دسته‌بندی اطلاعات تحویل"""
    
    class Meta:
        model = NonBazargahAllocation
        fields = [
            'allocation_number', 'delivery_address', 'delivery_postal_code', 'delivery_receiver_name',
            'coordination_phone', 'allocated_weight', 'notes'
        ]
        widgets = {
            'allocation_number': forms.TextInput(attrs={'placeholder': 'شماره تخصیص (اختیاری)'}),
            'delivery_address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'آدرس کامل محل تحویل کالا'}),
            'delivery_postal_code': forms.TextInput(attrs={'placeholder': 'کد پستی 10 رقمی'}),
            'delivery_receiver_name': forms.TextInput(attrs={'placeholder': 'نام شخص گیرنده کالا'}),
            'coordination_phone': forms.TextInput(attrs={'placeholder': 'شماره تماس برای هماهنگی'}),
            'allocated_weight': forms.NumberInput(attrs={'placeholder': 'وزن به کیلوگرم'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'توضیحات اضافی (اختیاری)'}),
        }
        labels = {
            'allocation_number': 'شماره تخصیص',
            'delivery_address': 'آدرس تحویل',
            'delivery_postal_code': 'کد پستی',
            'delivery_receiver_name': 'نام گیرنده',
            'coordination_phone': 'شماره هماهنگی',
            'allocated_weight': 'وزن تخصیص یافته (کیلوگرم)',
            'notes': 'توضیحات',
        }
    
    def __init__(self, *args, purchase=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.purchase = purchase
        
        if purchase:
            # تنظیم حداکثر وزن قابل تخصیص
            remaining_weight = purchase.get_remaining_weight_for_allocation()
            if remaining_weight > 0:
                self.fields['allocated_weight'].help_text = f'حداکثر وزن قابل تخصیص: {remaining_weight} کیلوگرم'
                self.fields['allocated_weight'].widget.attrs['max'] = remaining_weight
            else:
                self.fields['allocated_weight'].help_text = 'همه وزن تخصیص شده است'
                self.fields['allocated_weight'].widget.attrs['readonly'] = True
                self.fields['allocated_weight'].widget.attrs['disabled'] = True
    
    def clean_allocated_weight(self):
        allocated_weight = self.cleaned_data.get('allocated_weight')
        
        # استفاده از purchase که در __init__ تنظیم شده
        if self.purchase and allocated_weight:
            # محاسبه وزن باقی‌مانده
            remaining_weight = self.purchase.get_remaining_weight_for_allocation()
            
            # اگر در حال ویرایش هستیم، وزن فعلی instance را به باقی‌مانده اضافه کنیم
            if self.instance and self.instance.pk and hasattr(self.instance, 'allocated_weight'):
                remaining_weight += (self.instance.allocated_weight or 0)
            
            if allocated_weight > remaining_weight:
                raise ValidationError(f'وزن تخصیص یافته نمی‌تواند از {remaining_weight} کیلوگرم بیشتر باشد')
        
        return allocated_weight


class BarnamehForm(forms.ModelForm):
    """فرم مدیریت بارنامه‌ها"""
    
    # تعریف فیلدهای datetime به صورت جداگانه
    vehicle_arrival_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control time-input'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        label='زمان ورود ماشین'
    )
    empty_weigh_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control time-input'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        label='زمان وزن‌گیری خالی'
    )
    loaded_weigh_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control time-input'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        label='زمان وزن‌گیری پر'
    )
    departure_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control time-input'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        label='زمان خروج از انبار'
    )
    delivery_time = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control time-input'}),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        label='زمان تحویل'
    )
    
    class Meta:
        model = Barnameh
        fields = [
            'number', 'driver_name', 'driver_phone', 'vehicle_plate', 
            'empty_vehicle_weight', 'loaded_vehicle_weight',
            'final_delivered_weight', 'tonnage', 'barnameh_date',
            'vehicle_arrival_time', 'empty_weigh_time', 'loaded_weigh_time',
            'departure_time', 'delivery_time'
        ]
        widgets = {
            'number': forms.TextInput(attrs={'placeholder': 'شماره بارنامه'}),
            'driver_name': forms.TextInput(attrs={'placeholder': 'نام راننده'}),
            'driver_phone': forms.TextInput(attrs={'placeholder': 'شماره تماس راننده'}),
            'vehicle_plate': forms.TextInput(attrs={'placeholder': 'پلاک ماشین'}),
            'empty_vehicle_weight': forms.NumberInput(attrs={'placeholder': 'وزن خالی (کیلوگرم)', 'step': '0.01'}),
            'loaded_vehicle_weight': forms.NumberInput(attrs={'placeholder': 'وزن پر (کیلوگرم)', 'step': '0.01'}),
            'final_delivered_weight': forms.NumberInput(attrs={'placeholder': 'وزن نهایی تحویل (کیلوگرم)', 'step': '0.01'}),
            'tonnage': forms.NumberInput(attrs={'placeholder': 'وزن (تن)', 'step': '0.01'}),
            'barnameh_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        labels = {
            'number': 'شماره بارنامه',
            'driver_name': 'نام راننده',
            'driver_phone': 'شماره راننده', 
            'vehicle_plate': 'پلاک ماشین',
            'empty_vehicle_weight': 'وزن خالی',
            'loaded_vehicle_weight': 'وزن پر',
            'final_delivered_weight': 'وزن تحویلی',
            'tonnage': 'وزن (تن)',
            'barnameh_date': 'تاریخ بارنامه',
        }
    
    def clean_empty_vehicle_weight(self):
        weight = self.cleaned_data.get('empty_vehicle_weight')
        if weight and weight <= 0:
            raise ValidationError('وزن خالی باید بزرگتر از صفر باشد')
        return weight
    
    def clean_loaded_vehicle_weight(self):
        loaded = self.cleaned_data.get('loaded_vehicle_weight')
        empty = self.cleaned_data.get('empty_vehicle_weight')
        
        if loaded and loaded <= 0:
            raise ValidationError('وزن پر باید بزرگتر از صفر باشد')
        
        if loaded and empty and loaded <= empty:
            raise ValidationError('وزن پر باید از وزن خالی بیشتر باشد')
        
        return loaded


class RoleBasedNonBazargahPurchaseForm(forms.ModelForm):
    # فیلد بایپس برای اعتبارسنجی
    bypass_validation = forms.BooleanField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = NonBazargahPurchase
        fields = '__all__'
        widgets = {
            'payment_document': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'logistics_notes': forms.Textarea(attrs={'rows': 2}),
            'payment_notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # اطمینان از وجود مقادیر اولیه (جلوگیری از خطای required)
        if self.instance and self.instance.pk:
            # تنظیم فی خرید از محصول در instance
            if self.instance.product and not self.instance.company_price:
                product_price = self.instance.get_product_purchase_price()
                if product_price:
                    self.instance.company_price = product_price
        
        # حذف فیلدهای قیمت از فرم (اطلاعات محرمانه)
        price_fields = ['company_price']
        for field_name in price_fields:
            if field_name in self.fields:
                del self.fields[field_name]
        
        # فیلدهای همیشه قفل را اختیاری کن
        readonly_fields = ['customer', 'product', 'quantity', 'customer_price', 'amount_paid', 'bag_weight', 'unit']
        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
                # تنظیم مقدار اولیه برای فیلدهای readonly
                if self.instance and self.instance.pk and hasattr(self.instance, field_name):
                    self.initial[field_name] = getattr(self.instance, field_name)
        
        # فیلدهای وزن‌گیری را نیز اختیاری کن و مقدار اولیه تنظیم کن
        weight_fields = ['empty_weight', 'loaded_weight', 'delivered_weight', 'weight_difference', 'weight_difference_amount']
        for field_name in weight_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
                if self.instance and self.instance.pk and hasattr(self.instance, field_name):
                    self.initial[field_name] = getattr(self.instance, field_name)
        
        # تنظیم فیلدها بر اساس نقش کاربر
        if user_role == 'sales_agent':
            # کارشناس فروش فقط اطلاعات اولیه و اطلاعات خریدار
            allowed_fields = [
                'customer', 'product', 'unit', 'quantity', 'bag_weight',
                'customer_price', 'description',
                'buyer_name', 'buyer_postal_code', 'buyer_national_id',
                'buyer_user_type', 'address', 'tahvil_phone_number', 
                'code_melli_tahvil', 'barbary_confidential_number', 
                'barbary_customer_number', 'vehicle_type'
            ]
            
        elif user_role == 'financial_manager':
            # مدیر مالی - تایید پرداخت و فیلدهای مالی
            allowed_fields = [
                'customer', 'product', 'unit', 'quantity',
                'customer_price', 'amount_paid', 'payment_document',
                'payment_notes', 'description', 'state'
            ]
            
        elif user_role == 'logistics_manager':
            # مدیر لجستیک - مدیریت وزن‌گیری و لجستیک
            allowed_fields = [
                'customer', 'product', 'unit', 'quantity',
                'customer_price', 'logistics_notes', 'empty_weight', 'loaded_weight',
                'delivered_weight', 'weight_difference', 'weight_difference_amount', 'description',
                'state', 'vehicle_type', 'barbary_confidential_number',
                'barbary_customer_number', 'warehouse_contact_person',
                'warehouse_contact_phone'
            ]
            
        elif user_role == 'admin':
            # ادمین - دسترسی کامل
            allowed_fields = list(self.fields.keys())
            
        else:
            # سایر نقش‌ها - فقط مشاهده
            allowed_fields = []
        
        # اضافه کردن bypass_validation
        allowed_fields.append('bypass_validation')
        
        # حذف فیلدهای غیر مجاز
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]
        
        # قفل کردن فیلدها بر اساس وضعیت
        self._lock_fields_based_on_state()
        
        # مرتب کردن فیلدها
        custom_order_fields = [
            'customer', 'product', 'unit', 'quantity', 'bag_weight',
            'customer_price', 'amount_paid',
            'buyer_name', 'buyer_postal_code', 'buyer_national_id',
            'buyer_user_type', 'address', 'tahvil_phone_number', 
            'code_melli_tahvil', 'warehouse_contact_person', 
            'warehouse_contact_phone', 'empty_weight', 'loaded_weight',
            'delivered_weight', 'weight_difference', 'weight_difference_amount', 
            'payment_document', 'state',
            'description', 'logistics_notes', 'payment_notes'
        ]
        ordered_field_names = [f for f in custom_order_fields if f in self.fields]
        self.fields = OrderedDict((f, self.fields[f]) for f in ordered_field_names)
    
    def _lock_fields_based_on_state(self):
        """قفل کردن فیلدها بر اساس وضعیت خرید"""
        if not self.instance or not self.instance.pk:
            return
            
        state = self.instance.state
        
        # فیلدهای همیشه قفل (غیرقابل ادیت)
        always_readonly_fields = [
            'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
            'bag_weight', 'unit', 'state'
        ]
        for field_name in always_readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'readonly': 'readonly', 'disabled': True
                })
        
        # فیلدهای اساسی بعد از تایید پرداخت قفل می‌شوند
        payment_verified_states = [
            'payment_verified', 'address_assigned', 'sent_to_warehouse',
            'carrier_notified', 'vehicle_arrived', 'empty_weighed',
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]
        
        if state in payment_verified_states:
            readonly_fields = [
                'product'
            ]
            for field_name in readonly_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
        
        # فیلدهای اطلاعات خریدار بعد از تخصیص آدرس قفل می‌شوند
        address_assigned_states = [
            'address_assigned', 'sent_to_warehouse', 'carrier_notified',
            'vehicle_arrived', 'empty_weighed', 'loaded_weighed',
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]
        
        if state in address_assigned_states:
            buyer_info_fields = [
                'buyer_name', 'buyer_postal_code', 'buyer_national_id',
                'buyer_user_type', 'address', 'tahvil_phone_number', 
                'code_melli_tahvil'
            ]
            for field_name in buyer_info_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
        
        # فیلدهای وزن‌گیری فقط در مراحل مناسب قابل ویرایش
        weight_fields = ['empty_weight', 'loaded_weight', 'delivered_weight']
        if state not in ['vehicle_arrived', 'empty_weighed', 'loaded_weighed', 'barnameh_issued']:
            for field_name in weight_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
        
        # بعد از صدور بارنامه، فیلدهای وزن‌گیری قفل می‌شوند اما مقادیرشان حفظ می‌شود
        if state in ['barnameh_issued', 'delivered', 'purchase_closed']:
            for field_name in weight_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
                    # اطمینان از اینکه مقدار اولیه تنظیم شده است
                    if self.instance and self.instance.pk and hasattr(self.instance, field_name):
                        self.initial[field_name] = getattr(self.instance, field_name)
        
        # بعد از بستن خرید، فیلدهای محاسبات نهایی نیز قفل می‌شوند
        if state == 'purchase_closed':
            calculation_fields = ['weight_difference', 'weight_difference_amount']
            for field_name in calculation_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
                    if self.instance and self.instance.pk and hasattr(self.instance, field_name):
                        self.initial[field_name] = getattr(self.instance, field_name)
    
    def clean(self):
        cleaned_data = super().clean()
        
        # بایپس اعتبارسنجی برای دکمه‌های اکشن
        if cleaned_data.get('bypass_validation'):
            # بازگردانی مقادیر فیلدهای readonly از instance اصلی
            if self.instance and self.instance.pk:
                readonly_fields = [
                    'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
                    'bag_weight', 'unit', 'state'
                ]
                for field_name in readonly_fields:
                    if hasattr(self.instance, field_name):
                        cleaned_data[field_name] = getattr(self.instance, field_name)
                
                # بازگردانی فیلدهای وزن‌گیری نیز
                weight_fields = ['empty_weight', 'loaded_weight', 'delivered_weight', 'weight_difference', 'weight_difference_amount']
                for field_name in weight_fields:
                    if hasattr(self.instance, field_name):
                        cleaned_data[field_name] = getattr(self.instance, field_name)
            
            return cleaned_data
        
        # تنظیم فی خرید از محصول (فقط برای instance، نه برای فرم)
        if self.instance and self.instance.pk and self.instance.product:
            product_price = self.instance.get_product_purchase_price()
            if product_price:
                # تنظیم مستقیم در instance، نه در cleaned_data
                self.instance.company_price = product_price
        
        # اطمینان از وجود customer_price
        customer_price = cleaned_data.get('customer_price')
        
        # اگر فیلدهای readonly خالی هستند، از instance بگیر
        if self.instance and self.instance.pk:
            if not customer_price:
                cleaned_data['customer_price'] = self.instance.customer_price
            
            # اطمینان از وجود سایر فیلدهای ضروری
            essential_fields = ['customer', 'product', 'quantity', 'unit', 'bag_weight', 'amount_paid']
            for field_name in essential_fields:
                if not cleaned_data.get(field_name) and hasattr(self.instance, field_name):
                    cleaned_data[field_name] = getattr(self.instance, field_name)
            
            # اطمینان از وجود فیلدهای وزن‌گیری
            weight_fields = ['empty_weight', 'loaded_weight', 'delivered_weight', 'weight_difference', 'weight_difference_amount']
            for field_name in weight_fields:
                if field_name in self.fields and not cleaned_data.get(field_name) and hasattr(self.instance, field_name):
                    cleaned_data[field_name] = getattr(self.instance, field_name)
        
        # اعتبارسنجی وزن‌ها
        empty_weight = cleaned_data.get('empty_weight')
        loaded_weight = cleaned_data.get('loaded_weight')
        
        if empty_weight and loaded_weight and loaded_weight <= empty_weight:
            raise ValidationError('وزن پر باید از وزن خالی بیشتر باشد')
        
        return cleaned_data


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
@login_required
def non_bazargah_purchase_CRUD_view(request, purchase_id):
    """صفحه مدیریت خرید خارج بازارگاه"""
    logger.warning(f"دسترسی به خرید خارج بازارگاه {purchase_id} توسط {request.user.username}, IP: {get_client_ip(request)}")
    
    purchase = get_object_or_404(NonBazargahPurchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کارشناس فروش
    if user_role == 'sales_agent':
        if not purchase.customer or not hasattr(request.user, 'sales_agent'):
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
        
        # بررسی که کارشناس فروش مربوط به این مشتری است
        if not purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
    
    # تعریف مراحل پیشرفت
    progress_steps = [
        {'name': 'شروع شده', 'status': True},
        {'name': 'انتظار تایید پرداخت', 'status': purchase.state != 'initiated'},
        {'name': 'تایید پرداخت', 'status': purchase.state in [
            'payment_verified', 'address_assigned', 'sent_to_warehouse',
            'carrier_notified', 'vehicle_arrived', 'empty_weighed',
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'تخصیص آدرس', 'status': purchase.state in [
            'address_assigned', 'sent_to_warehouse', 'carrier_notified',
            'vehicle_arrived', 'empty_weighed', 'loaded_weighed',
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'ارسال به انبار', 'status': purchase.state in [
            'sent_to_warehouse', 'carrier_notified', 'vehicle_arrived',
            'empty_weighed', 'loaded_weighed', 'barnameh_issued',
            'delivered', 'purchase_closed'
        ]},
        {'name': 'اعلام بار به باربری', 'status': purchase.state in [
            'carrier_notified', 'vehicle_arrived', 'empty_weighed',
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'ورود ماشین', 'status': purchase.state in [
            'vehicle_arrived', 'empty_weighed', 'loaded_weighed',
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'وزن خالی', 'status': purchase.state in [
            'empty_weighed', 'loaded_weighed', 'barnameh_issued',
            'delivered', 'purchase_closed'
        ]},
        {'name': 'بارگیری و وزن پر', 'status': purchase.state in [
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'صدور بارنامه', 'status': purchase.state in [
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'تحویل به مشتری', 'status': purchase.state in [
            'delivered', 'purchase_closed'
        ]},
        {'name': 'بستن خرید', 'status': purchase.state == 'purchase_closed'},
    ]
    
    # دریافت تخصیص‌های موجود
    allocations = purchase.allocations.all().order_by('-id')
    
    # محاسبه وزن‌های کلیدی
    total_allocated_weight = purchase.get_total_allocated_weight() or 0
    remaining_weight = purchase.get_remaining_weight_for_allocation() or 0
    
    # تبدیل وزن درخواستی به کیلوگرم برای نمایش
    requested_weight_kg = purchase.quantity or 0
    if purchase.unit == 'Ton' and purchase.quantity:
        requested_weight_kg = purchase.quantity * 1000
    elif purchase.unit == 'Kiseh' and purchase.quantity and purchase.bag_weight:
        requested_weight_kg = purchase.quantity * purchase.bag_weight
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        
        # بررسی دکمه‌های اکشن
        action_buttons = [
            'approve_payment', 'add_allocation', 'approve_allocations', 'send_to_warehouse',
            'notify_carrier', 'confirm_vehicle_arrival', 'record_empty_weight',
            'record_loaded_weight', 'issue_barnameh', 'confirm_delivery',
            'close_purchase', 'cancel_purchase', 'archive_purchase', 'upload_document',
            'delete_allocation', 'add_barnameh', 'update_barnameh', 'delete_barnameh'
        ]
        
        is_action_button_pressed = any(action in request.POST for action in action_buttons)
        
        # پردازش آپلود مدرک
        if 'upload_document' in request.POST:
            document_file = request.FILES.get('payment_document_upload')
            if document_file:
                purchase.payment_document = document_file
                # تنظیم company_price از محصول
                if purchase.product:
                    product_price = purchase.get_product_purchase_price()
                    if product_price:
                        purchase.company_price = product_price
                purchase.save()
                messages.success(request, 'مدرک پرداخت با موفقیت بارگذاری شد - حالا می‌توانید پرداخت را تایید کنید')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            else:
                messages.error(request, 'لطفاً یک فایل انتخاب کنید')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش آپلود فایل اکسل تخصیص‌ها
        if 'upload_allocation_excel' in request.POST and user_role in ['logistics_manager', 'admin']:
            if not purchase.can_assign_addresses():
                messages.error(request, 'برای تخصیص آدرس ابتدا باید پرداخت تایید شود')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            
            excel_file = request.FILES.get('excel_file')
            if not excel_file:
                messages.error(request, 'لطفاً یک فایل اکسل انتخاب کنید')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            
            try:
                with transaction.atomic():
                    result = process_allocation_excel(excel_file, purchase)
                    
                    if result['success']:
                        messages.success(request, result['message'])
                        if result.get('errors'):
                            for error in result['errors']:
                                messages.warning(request, error)
                    else:
                        messages.error(request, result['message'])
                        if result.get('errors'):
                            for error in result['errors'][:3]:  # فقط 3 خطای اول
                                messages.error(request, error)
                
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                
            except Exception as e:
                logger.error(f"خطا در آپلود فایل اکسل تخصیص‌ها: {str(e)}")
                messages.error(request, f'خطا در پردازش فایل اکسل: {str(e)}')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش آپلود فایل اکسل بارنامه‌ها
        if 'upload_barnameh_excel' in request.POST and user_role in ['logistics_manager', 'admin']:
            logger.info(f"درخواست آپلود اکسل بارنامه‌ها برای خرید {purchase_id}")
            logger.info(f"فایل‌های دریافتی: {list(request.FILES.keys())}")
            
            # بررسی اینکه خرید در مرحله مناسب باشد
            if purchase.state not in ['carrier_notified', 'vehicle_arrived']:
                messages.error(request, 'برای اضافه کردن بارنامه، خرید باید در مرحله "اعلام بار به باربری" یا "ورود ماشین" باشد')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            
            excel_file = request.FILES.get('barnameh_excel_file')
            logger.info(f"فایل دریافتی: {excel_file}")
            
            if not excel_file:
                logger.warning("فایل اکسل بارنامه دریافت نشد")
                messages.error(request, 'لطفاً یک فایل اکسل انتخاب کنید')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            
            try:
                with transaction.atomic():
                    result = process_barnameh_excel(excel_file, purchase)
                    
                    if result['success']:
                        messages.success(request, result['message'])
                        if result.get('errors'):
                            for error in result['errors']:
                                messages.warning(request, error)
                    else:
                        messages.error(request, result['message'])
                        if result.get('errors'):
                            for error in result['errors'][:3]:  # فقط 3 خطای اول
                                messages.error(request, error)
                
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                
            except Exception as e:
                logger.error(f"خطا در آپلود فایل اکسل بارنامه‌ها: {str(e)}")
                messages.error(request, f'خطا در پردازش فایل اکسل: {str(e)}')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش اضافه کردن تخصیص جدید
        if 'add_allocation' in request.POST and user_role in ['logistics_manager', 'admin']:
            if not purchase.can_assign_addresses():
                messages.error(request, 'برای تخصیص آدرس ابتدا باید پرداخت تایید شود')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            
            # ایجاد فرم با داده‌های POST و تنظیم purchase
            allocation_form_data = NonBazargahAllocationForm(request.POST, purchase=purchase)
            if allocation_form_data.is_valid():
                try:
                    allocation = allocation_form_data.save(commit=False)
                    allocation.purchase = purchase  # تنظیم صریح خرید
                    allocation.save()
                    messages.success(request, f'تخصیص جدید با وزن {allocation.allocated_weight} کیلوگرم اضافه شد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except Exception as e:
                    messages.error(request, f'خطا در ذخیره تخصیص: {str(e)}')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            else:
                for field, errors in allocation_form_data.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش حذف تخصیص
        if 'delete_allocation' in request.POST and user_role in ['logistics_manager', 'admin']:
            allocation_id = request.POST.get('allocation_id')
            if allocation_id:
                try:
                    allocation = NonBazargahAllocation.objects.get(id=allocation_id, purchase=purchase)
                    allocation.delete()
                    messages.success(request, 'تخصیص حذف شد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except NonBazargahAllocation.DoesNotExist:
                    messages.error(request, 'تخصیص مورد نظر یافت نشد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش اضافه کردن بارنامه جدید
        if 'add_barnameh' in request.POST and user_role in ['logistics_manager', 'admin']:
            allocation_id = request.POST.get('allocation_id')
            if allocation_id:
                try:
                    allocation = NonBazargahAllocation.objects.get(id=allocation_id, purchase=purchase)
                    # ایجاد بارنامه با اطلاعات اولیه - پردازش دستی به دلیل محدودیت فرم
                    try:
                        from datetime import datetime
                        # دریافت اطلاعات پایه
                        number = request.POST.get('number', '').strip()
                        driver_name = request.POST.get('driver_name', '').strip()
                        driver_phone = request.POST.get('driver_phone', '').strip()
                        vehicle_plate = request.POST.get('vehicle_plate', '').strip()
                        vehicle_arrival_time = request.POST.get('vehicle_arrival_time', '').strip()
                        
                        # اعتبارسنجی فیلدهای ضروری
                        if not driver_name:
                            messages.error(request, 'نام راننده الزامی است')
                            return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                        if not driver_phone:
                            messages.error(request, 'شماره تلفن راننده الزامی است')
                            return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                        if not vehicle_plate:
                            messages.error(request, 'پلاک ماشین الزامی است')
                            return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                        
                        # ایجاد بارنامه
                        barnameh = Barnameh(
                            non_bazargah_allocation=allocation,
                            non_bazargah_purchase=purchase,
                            type='Non_Bazargah',
                            driver_name=driver_name,
                            driver_phone=driver_phone,
                            vehicle_plate=vehicle_plate
                        )
                        
                        # تنظیم شماره بارنامه
                        if number:
                            barnameh.number = number
                        else:
                            barnameh_count = allocation.barnamehs.count() + 1
                            allocation_number = allocation.allocation_number or allocation.id
                            barnameh.number = f"{allocation_number}-{barnameh_count}"
                        
                        # تنظیم زمان ورود ماشین (اگر وارد شده باشد)
                        if vehicle_arrival_time:
                            try:
                                barnameh.vehicle_arrival_time = datetime.fromisoformat(vehicle_arrival_time)
                            except (ValueError, TypeError):
                                pass  # اگر فرمت نادرست باشد، خالی بگذار
                        
                        barnameh.save()
                        messages.success(request, f'بارنامه جدید #{barnameh.number} برای تخصیص {allocation.id} اضافه شد')
                        return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                        
                    except Exception as e:
                        messages.error(request, f'خطا در ایجاد بارنامه: {str(e)}')
                        return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except NonBazargahAllocation.DoesNotExist:
                    messages.error(request, 'تخصیص مورد نظر یافت نشد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش بروزرسانی بارنامه
        if 'update_barnameh' in request.POST and user_role in ['logistics_manager', 'admin']:
            barnameh_id = request.POST.get('barnameh_id')
            if barnameh_id:
                try:
                    barnameh = Barnameh.objects.get(id=barnameh_id)
                    if barnameh.non_bazargah_allocation and barnameh.non_bazargah_allocation.purchase == purchase:
                        barnameh_form = BarnamehForm(request.POST, instance=barnameh)
                        if barnameh_form.is_valid():
                            barnameh_updated = barnameh_form.save(commit=False)
                            
                            # فیلدهای زمانی حالا توسط فرم به درستی پردازش می‌شوند
                            # نیازی به پردازش دستی نیست
                            
                            barnameh_updated.save()
                            messages.success(request, 'اطلاعات بارنامه بروزرسانی شد')
                        else:
                            for field, errors in barnameh_form.errors.items():
                                for error in errors:
                                    messages.error(request, f'{field}: {error}')
                        return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except Barnameh.DoesNotExist:
                    messages.error(request, 'بارنامه مورد نظر یافت نشد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش حذف بارنامه
        if 'delete_barnameh' in request.POST and user_role in ['logistics_manager', 'admin']:
            barnameh_id = request.POST.get('barnameh_id')
            if barnameh_id:
                try:
                    barnameh = Barnameh.objects.get(id=barnameh_id)
                    if barnameh.non_bazargah_allocation and barnameh.non_bazargah_allocation.purchase == purchase:
                        barnameh.delete()
                        messages.success(request, 'بارنامه حذف شد')
                        return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except Barnameh.DoesNotExist:
                    messages.error(request, 'بارنامه مورد نظر یافت نشد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش بروزرسانی همه بارنامه‌ها
        if 'update_all_barnamehs' in request.POST and user_role in ['logistics_manager', 'admin']:
            try:
                updated_count = 0
                errors = []
                
                # لاگ همه کلیدهای POST برای دیباگ
                barnameh_keys = [k for k in request.POST.keys() if k.startswith('barnameh_')]
                logger.info(f"کلیدهای بارنامه در POST: {barnameh_keys}")
                logger.info(f"همه کلیدهای POST: {list(request.POST.keys())}")
                
                # دریافت همه بارنامه‌های مربوط به این خرید
                all_barnamehs = purchase.get_all_barnamehs()
                logger.info(f"تعداد بارنامه‌های موجود: {len(all_barnamehs)}, IDs: {[b.id for b in all_barnamehs]}")
                
                for barnameh in all_barnamehs:
                    try:
                        # بررسی اینکه آیا برای این بارنامه اطلاعاتی ارسال شده یا نه
                        barnameh_prefix = f'barnameh_{barnameh.id}_'
                        has_data = any(key.startswith(barnameh_prefix) for key in request.POST.keys())
                        
                        logger.info(f"بررسی بارنامه {barnameh.id}: has_data={has_data}, کلیدهای POST: {[k for k in request.POST.keys() if k.startswith(barnameh_prefix)]}")
                        
                        if has_data:
                            # استخراج اطلاعات مربوط به این بارنامه
                            number = request.POST.get(f'{barnameh_prefix}number', '').strip()
                            driver_name = request.POST.get(f'{barnameh_prefix}driver_name', '').strip()
                            driver_phone = request.POST.get(f'{barnameh_prefix}driver_phone', '').strip()
                            vehicle_plate = request.POST.get(f'{barnameh_prefix}vehicle_plate', '').strip()
                            
                            # اطلاعات وزن
                            empty_weight = request.POST.get(f'{barnameh_prefix}empty_vehicle_weight', '')
                            loaded_weight = request.POST.get(f'{barnameh_prefix}loaded_vehicle_weight', '')
                            delivered_weight = request.POST.get(f'{barnameh_prefix}final_delivered_weight', '')
                            
                            # اطلاعات زمانی
                            vehicle_arrival_time = request.POST.get(f'{barnameh_prefix}vehicle_arrival_time', '')
                            empty_weigh_time = request.POST.get(f'{barnameh_prefix}empty_weigh_time', '')
                            loaded_weigh_time = request.POST.get(f'{barnameh_prefix}loaded_weigh_time', '')
                            departure_time = request.POST.get(f'{barnameh_prefix}departure_time', '')
                            delivery_time = request.POST.get(f'{barnameh_prefix}delivery_time', '')
                            barnameh_date = request.POST.get(f'{barnameh_prefix}barnameh_date', '')
                            
                            # بروزرسانی فیلدها - بررسی مقدار وارد شده بدون در نظر گیری تغییر
                            updated = False
                            
                            if number:
                                if number != (barnameh.number or ''):
                                    barnameh.number = number
                                    updated = True
                                    logger.info(f"بروزرسانی شماره بارنامه {barnameh.id}: '{barnameh.number}' -> '{number}'")
                            
                            if driver_name:
                                if driver_name != (barnameh.driver_name or ''):
                                    barnameh.driver_name = driver_name
                                    updated = True
                                    logger.info(f"بروزرسانی نام راننده بارنامه {barnameh.id}: '{barnameh.driver_name}' -> '{driver_name}'")
                            
                            if driver_phone:
                                if driver_phone != (barnameh.driver_phone or ''):
                                    barnameh.driver_phone = driver_phone
                                    updated = True
                                    logger.info(f"بروزرسانی شماره راننده بارنامه {barnameh.id}: '{barnameh.driver_phone}' -> '{driver_phone}'")
                            
                            if vehicle_plate:
                                if vehicle_plate != (barnameh.vehicle_plate or ''):
                                    barnameh.vehicle_plate = vehicle_plate
                                    updated = True
                                    logger.info(f"بروزرسانی پلاک بارنامه {barnameh.id}: '{barnameh.vehicle_plate}' -> '{vehicle_plate}'")
                            
                            # بروزرسانی وزن‌ها
                            if empty_weight:
                                try:
                                    empty_weight_val = float(empty_weight)
                                    if empty_weight_val != (barnameh.empty_vehicle_weight or 0):
                                        barnameh.empty_vehicle_weight = empty_weight_val
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if loaded_weight:
                                try:
                                    loaded_weight_val = float(loaded_weight)
                                    if loaded_weight_val != (barnameh.loaded_vehicle_weight or 0):
                                        barnameh.loaded_vehicle_weight = loaded_weight_val
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if delivered_weight:
                                try:
                                    delivered_weight_val = float(delivered_weight)
                                    if delivered_weight_val != (barnameh.final_delivered_weight or 0):
                                        barnameh.final_delivered_weight = delivered_weight_val
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            # بروزرسانی زمان‌ها
                            from datetime import datetime
                            
                            if vehicle_arrival_time:
                                try:
                                    arrival_time = datetime.fromisoformat(vehicle_arrival_time)
                                    if arrival_time != barnameh.vehicle_arrival_time:
                                        barnameh.vehicle_arrival_time = arrival_time
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if empty_weigh_time:
                                try:
                                    empty_time = datetime.fromisoformat(empty_weigh_time)
                                    if empty_time != barnameh.empty_weigh_time:
                                        barnameh.empty_weigh_time = empty_time
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if loaded_weigh_time:
                                try:
                                    loaded_time = datetime.fromisoformat(loaded_weigh_time)
                                    if loaded_time != barnameh.loaded_weigh_time:
                                        barnameh.loaded_weigh_time = loaded_time
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if departure_time:
                                try:
                                    depart_time = datetime.fromisoformat(departure_time)
                                    if depart_time != barnameh.departure_time:
                                        barnameh.departure_time = depart_time
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if delivery_time:
                                try:
                                    deliver_time = datetime.fromisoformat(delivery_time)
                                    if deliver_time != barnameh.delivery_time:
                                        barnameh.delivery_time = deliver_time
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if barnameh_date:
                                try:
                                    date_val = datetime.strptime(barnameh_date, '%Y-%m-%d').date()
                                    if date_val != barnameh.barnameh_date:
                                        barnameh.barnameh_date = date_val
                                        updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            # ذخیره تغییرات اگر چیزی تغییر کرده باشد
                            if updated:
                                barnameh.save()
                                updated_count += 1
                    
                    except Exception as e:
                        errors.append(f'خطا در بروزرسانی بارنامه #{barnameh.number or barnameh.id}: {str(e)}')
                        continue
                
                # نمایش نتیجه
                if updated_count > 0:
                    message = f'{updated_count} بارنامه با موفقیت بروزرسانی شد'
                    if errors:
                        message += f' ({len(errors)} خطا)'
                    messages.success(request, message)
                    
                    # نمایش خطاها (حداکثر 3 مورد)
                    for error in errors[:3]:
                        messages.warning(request, error)
                else:
                    if errors:
                        messages.error(request, f'هیچ بارنامه‌ای بروزرسانی نشد - {len(errors)} خطا رخ داد')
                        for error in errors[:3]:
                            messages.error(request, error)
                    else:
                        messages.info(request, 'هیچ تغییری برای بروزرسانی یافت نشد')
                
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                
            except Exception as e:
                logger.error(f"خطا در بروزرسانی همه بارنامه‌ها: {str(e)}")
                messages.error(request, f'خطا در بروزرسانی همه بارنامه‌ها: {str(e)}')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        if is_action_button_pressed:
            post_data['bypass_validation'] = 'true'
            # برای دکمه‌های اکشن، اطمینان از وجود فیلدهای ضروری
            if not post_data.get('customer_price'):
                post_data['customer_price'] = purchase.customer_price
            if not post_data.get('quantity'):
                post_data['quantity'] = purchase.quantity
            if not post_data.get('unit'):
                post_data['unit'] = purchase.unit
            if not post_data.get('bag_weight'):
                post_data['bag_weight'] = purchase.bag_weight
            if not post_data.get('amount_paid'):
                post_data['amount_paid'] = purchase.amount_paid
            
            # تنظیم قیمت‌ها از محصول (فقط customer_price در فرم)
            if purchase.customer_price:
                post_data['customer_price'] = purchase.customer_price
        
        form = RoleBasedNonBazargahPurchaseForm(post_data, request.FILES, instance=purchase, user_role=user_role)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # پردازش اکشن‌های مختلف
                    action_taken = False
                    
                    # اکشن‌های مدیر مالی
                    if user_role in ['financial_manager', 'admin']:
                        if purchase.state in ['initiated', 'payment_verification_pending'] and 'approve_payment' in request.POST:
                            # بررسی وجود مدرک پرداخت
                            if not purchase.payment_document:
                                messages.error(request, 'برای تایید پرداخت ابتدا باید مدرک پرداخت آپلود شود')
                            else:
                                purchase.state = 'payment_verified'
                                purchase.payment_verified_by = request.user
                                purchase.payment_verified_at = timezone.now()
                                action_taken = True
                                messages.success(request, 'پرداخت با موفقیت تایید شد')
                    
                    # اکشن‌های مدیر لجستیک
                    if user_role in ['logistics_manager', 'admin']:
                        if purchase.state == 'payment_verified' and 'approve_allocations' in request.POST:
                            logger.info(f"تلاش برای تایید تخصیص‌ها - خرید {purchase.id}")
                            # بررسی اینکه آیا همه وزن تخصیص شده است
                            if remaining_weight > 0:
                                logger.warning(f"وزن باقی‌مانده: {remaining_weight}")
                                messages.error(request, f'هنوز {remaining_weight} کیلوگرم وزن برای تخصیص باقی مانده است')
                            elif not allocations.exists():
                                logger.warning("هیچ تخصیصی وجود ندارد")
                                messages.error(request, 'ابتدا باید حداقل یک تخصیص اضافه کنید')
                            else:
                                try:
                                    # تغییر مستقیم وضعیت بدون استفاده از متد approve_all_allocations
                                    logger.info(f"تغییر وضعیت خرید {purchase.id} به address_assigned")
                                    purchase.state = 'address_assigned'
                                    purchase.save()
                                    action_taken = True
                                    messages.success(request, 'همه تخصیص‌ها تایید شد و وضعیت خرید تغییر کرد')
                                    logger.info(f"وضعیت خرید {purchase.id} با موفقیت تغییر کرد")
                                except Exception as e:
                                    logger.error(f"خطا در تایید تخصیص‌ها: {str(e)}")
                                    messages.error(request, f'خطا در تایید تخصیص‌ها: {str(e)}')
                        
                        elif purchase.state == 'address_assigned' and 'send_to_warehouse' in request.POST:
                            purchase.state = 'sent_to_warehouse'
                            action_taken = True
                            messages.success(request, 'اطلاعات به انبار ارسال شد')
                        
                        elif purchase.state == 'sent_to_warehouse' and 'notify_carrier' in request.POST:
                            purchase.state = 'carrier_notified'
                            action_taken = True
                            messages.success(request, 'بار به باربری اعلام شد')
                        
                        elif purchase.state == 'carrier_notified' and 'confirm_vehicle_arrival' in request.POST:
                            # بررسی اینکه برای همه تخصیص‌ها حداقل یک بارنامه وجود دارد
                            if not purchase.can_confirm_vehicle_arrival():
                                messages.error(request, 'برای تایید ورود ماشین، ابتدا باید برای همه تخصیص‌ها حداقل یک بارنامه اضافه کنید')
                            else:
                                purchase.state = 'vehicle_arrived'
                                
                                # ثبت زمان ورود ماشین در همه بارنامه‌ها
                                current_time = timezone.now()
                                all_barnamehs = purchase.get_all_barnamehs()
                                for barnameh in all_barnamehs:
                                    if not barnameh.vehicle_arrival_time:
                                        barnameh.vehicle_arrival_time = current_time
                                        barnameh.save(update_fields=['vehicle_arrival_time'])
                                
                                action_taken = True
                                messages.success(request, 'ورود ماشین تایید شد و زمان ورود ثبت گردید')
                        
                        elif purchase.state == 'vehicle_arrived' and 'record_empty_weight' in request.POST:
                            # بررسی اینکه همه بارنامه‌ها اطلاعات ماشین کامل دارند
                            if not purchase.can_record_empty_weight():
                                messages.error(request, 'برای ثبت وزن خالی، ابتدا باید اطلاعات ماشین (نام راننده، شماره تلفن، پلاک) برای همه بارنامه‌ها کامل باشد')
                            # بررسی اینکه همه بارنامه‌ها وزن خالی دارند
                            elif not purchase.can_record_empty_weight_values():
                                messages.error(request, 'برای ثبت وزن خالی، ابتدا باید وزن خالی برای همه بارنامه‌ها ثبت شده باشد (مقدار بیشتر از صفر)')
                            else:
                                purchase.state = 'empty_weighed'
                                
                                # ثبت زمان وزن‌گیری خالی در همه بارنامه‌ها
                                current_time = timezone.now()
                                all_barnamehs = purchase.get_all_barnamehs()
                                for barnameh in all_barnamehs:
                                    if not barnameh.empty_weigh_time and barnameh.empty_vehicle_weight:
                                        barnameh.empty_weigh_time = current_time
                                        barnameh.save(update_fields=['empty_weigh_time'])
                                
                                action_taken = True
                                messages.success(request, 'وزن خالی ثبت شد و زمان وزن‌گیری ثبت گردید')
                        
                        elif purchase.state == 'empty_weighed' and 'record_loaded_weight' in request.POST:
                            # بررسی اینکه همه بارنامه‌ها وزن خالی دارند
                            if not purchase.can_record_loaded_weight():
                                messages.error(request, 'برای ثبت وزن پر، ابتدا باید وزن خالی برای همه بارنامه‌ها ثبت شده باشد')
                            # بررسی اینکه همه بارنامه‌ها وزن پر دارند
                            elif not purchase.can_record_loaded_weight_values():
                                messages.error(request, 'برای ثبت وزن پر، ابتدا باید وزن پر برای همه بارنامه‌ها ثبت شده باشد (مقدار بیشتر از صفر)')
                            else:
                                purchase.state = 'loaded_weighed'
                                
                                # ثبت زمان وزن‌گیری پر در همه بارنامه‌ها
                                current_time = timezone.now()
                                all_barnamehs = purchase.get_all_barnamehs()
                                for barnameh in all_barnamehs:
                                    if not barnameh.loaded_weigh_time and barnameh.loaded_vehicle_weight:
                                        barnameh.loaded_weigh_time = current_time
                                        barnameh.save(update_fields=['loaded_weigh_time'])
                                
                                action_taken = True
                                messages.success(request, 'وزن پر ثبت شد و زمان وزن‌گیری ثبت گردید')
                        
                        elif purchase.state == 'loaded_weighed' and 'issue_barnameh' in request.POST:
                            # بررسی اینکه همه بارنامه‌ها وزن پر دارند
                            if not purchase.can_issue_barnameh():
                                messages.error(request, 'برای صدور بارنامه، ابتدا باید وزن پر برای همه بارنامه‌ها ثبت شده باشد (مقدار بیشتر از صفر)')
                            else:
                                # محاسبه و بروزرسانی وزن‌ها از بارنامه‌ها
                                try:
                                    purchase.update_weights_from_barnamehs(save=False)
                                    
                                    # محاسبه اختلاف وزن و مبلغ آن در همین مرحله
                                    weight_difference = purchase.calculate_net_weight_difference()
                                    weight_difference_amount = purchase.calculate_weight_difference_amount()
                                    
                                    # ذخیره مقادیر محاسبه شده
                                    if weight_difference is not None:
                                        purchase.weight_difference = weight_difference
                                    if weight_difference_amount is not None:
                                        purchase.weight_difference_amount = weight_difference_amount
                                    
                                    logger.info(f"وزن‌های خرید {purchase.id} از بارنامه‌ها بروزرسانی شد - اختلاف وزن: {weight_difference} کیلوگرم، مبلغ اختلاف: {weight_difference_amount} ریال")
                                    
                                    # نمایش اطلاعات محاسبه شده
                                    if weight_difference and weight_difference != 0:
                                        if weight_difference > 0:
                                            messages.success(request, f'بارنامه صادر شد. اختلاف وزن: +{weight_difference:.2f} کیلوگرم (اضافه تحویل) - مبلغ اضافی: {weight_difference_amount:,.0f} ریال')
                                        else:
                                            messages.success(request, f'بارنامه صادر شد. اختلاف وزن: {weight_difference:.2f} کیلوگرم (کمبود تحویل) - مبلغ کسر: {abs(weight_difference_amount):,.0f} ریال')
                                    else:
                                        messages.success(request, 'بارنامه صادر شد. وزن تحویل دقیقاً مطابق سفارش است.')
                                        
                                except Exception as e:
                                    logger.error(f"خطا در بروزرسانی وزن‌ها از بارنامه‌ها: {str(e)}")
                                    messages.warning(request, f'بارنامه صادر شد اما خطا در محاسبه وزن‌ها: {str(e)}')
                                
                                purchase.state = 'barnameh_issued'
                                
                                # ثبت زمان خروج از انبار و تاریخ بارنامه در همه بارنامه‌ها
                                current_time = timezone.now()
                                current_date = current_time.date()
                                all_barnamehs = purchase.get_all_barnamehs()
                                for barnameh in all_barnamehs:
                                    # ثبت زمان خروج از انبار
                                    if not barnameh.departure_time and barnameh.loaded_vehicle_weight:
                                        barnameh.departure_time = current_time
                                    
                                    # ثبت تاریخ بارنامه (مهم برای گزارش‌گیری)
                                    if not barnameh.barnameh_date:
                                        barnameh.barnameh_date = current_date
                                    
                                    barnameh.save(update_fields=['departure_time', 'barnameh_date'])
                                
                                action_taken = True
                        
                        elif purchase.state == 'barnameh_issued' and 'confirm_delivery' in request.POST:
                            purchase.state = 'delivered'
                            
                            # ثبت زمان تحویل در همه بارنامه‌ها
                            current_time = timezone.now()
                            all_barnamehs = purchase.get_all_barnamehs()
                            for barnameh in all_barnamehs:
                                if not barnameh.delivery_time:
                                    barnameh.delivery_time = current_time
                                    barnameh.save(update_fields=['delivery_time'])
                            
                            action_taken = True
                            messages.success(request, 'تحویل به مشتری تایید شد و زمان تحویل ثبت گردید')
                        
                        elif purchase.state == 'delivered' and 'close_purchase' in request.POST:
                            # اضافه کردن مبلغ اختلاف وزن به کیف پول مشتری (اگر قبلاً محاسبه نشده باشد)
                            try:
                                wallet_transaction = None
                                if purchase.weight_difference_amount and purchase.weight_difference_amount != 0:
                                    wallet_transaction = purchase.add_weight_difference_to_customer_wallet()
                                    if wallet_transaction:
                                        logger.info(f"تراکنش کیف پول برای خرید {purchase.id} ایجاد شد: {wallet_transaction.id}")
                                
                                purchase.state = 'purchase_closed'
                                
                                # نمایش اطلاعات نهایی
                                if purchase.weight_difference and purchase.weight_difference != 0:
                                    if purchase.weight_difference > 0:
                                        wallet_msg = " و به کیف پول مشتری اضافه شد" if wallet_transaction else ""
                                        messages.success(request, f'خرید بسته شد. اختلاف وزن: +{purchase.weight_difference:.2f} کیلوگرم (اضافه تحویل) - مبلغ اضافی: {purchase.weight_difference_amount:,.0f} ریال{wallet_msg}')
                                    else:
                                        wallet_msg = " و به کیف پول مشتری اضافه شد" if wallet_transaction else ""
                                        messages.success(request, f'خرید بسته شد. اختلاف وزن: {purchase.weight_difference:.2f} کیلوگرم (کمبود تحویل) - مبلغ کسر: {abs(purchase.weight_difference_amount):,.0f} ریال{wallet_msg}')
                                else:
                                    messages.success(request, 'خرید بسته شد. وزن تحویل دقیقاً مطابق سفارش است.')
                                    
                            except Exception as e:
                                logger.error(f"خطا در بستن خرید {purchase.id}: {str(e)}")
                                purchase.state = 'purchase_closed'
                                messages.warning(request, f'خرید بسته شد اما خطا در اضافه کردن به کیف پول: {str(e)}')
                            
                            action_taken = True
                    
                    # اکشن‌های ادمین
                    if user_role == 'admin':
                        if 'cancel_purchase' in request.POST:
                            purchase.state = 'canceled'
                            action_taken = True
                            messages.success(request, 'خرید لغو شد')
                        
                        elif 'archive_purchase' in request.POST:
                            purchase.state = 'archived'
                            action_taken = True
                            messages.success(request, 'خرید آرشیو شد')
                    
                    # ذخیره تغییرات purchase در انتهای transaction
                    purchase.save()
                    
                    # ذخیره فرم فقط اگر اکشن انجام نشده باشد
                    if not action_taken:
                        # فیلدهای قفل شده که نباید تغییر کنند
                        locked_fields = [
                            'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
                            'bag_weight', 'unit', 'state'
                        ]
                        
                        # ذخیره مقادیر اصلی فیلدهای قفل شده
                        original_values = {}
                        for field_name in locked_fields:
                            if hasattr(purchase, field_name):
                                original_values[field_name] = getattr(purchase, field_name)
                        
                        # ذخیره فرم
                        purchase_instance = form.save(commit=False)
                        
                        # بازگردانی مقادیر اصلی فیلدهای قفل شده
                        for field_name, original_value in original_values.items():
                            setattr(purchase_instance, field_name, original_value)
                        
                        # تنظیم فی خرید از محصول
                        if purchase_instance.product:
                            product_price = purchase_instance.get_product_purchase_price()
                            if product_price:
                                purchase_instance.company_price = product_price
                        
                        purchase_instance.save()
                        messages.success(request, 'تغییرات با موفقیت اعمال شد')
                    else:
                        # اگر اکشن انجام شده، فقط ذخیره فرم بدون تغییر فیلدهای قفل شده
                        # فیلدهای قفل شده که نباید تغییر کنند
                        locked_fields = [
                            'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
                            'bag_weight', 'unit'
                        ]
                        
                        # ذخیره مقادیر اصلی فیلدهای قفل شده
                        original_values = {}
                        for field_name in locked_fields:
                            if hasattr(purchase, field_name):
                                original_values[field_name] = getattr(purchase, field_name)
                        
                        # ذخیره فرم
                        purchase_instance = form.save(commit=False)
                        
                        # بازگردانی مقادیر اصلی فیلدهای قفل شده
                        for field_name, original_value in original_values.items():
                            setattr(purchase_instance, field_name, original_value)
                        
                        # تنظیم فی خرید از محصول
                        if purchase_instance.product:
                            product_price = purchase_instance.get_product_purchase_price()
                            if product_price:
                                purchase_instance.company_price = product_price
                        
                        purchase_instance.save()
                    
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                    
            except ValidationError as e:
                if hasattr(e, 'message'):
                    messages.error(request, e.message)
                else:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, error)
            except Exception as e:
                logger.error(f"خطا در پردازش خرید خارج بازارگاه {purchase_id}: {str(e)}")
                messages.error(request, f'خطا: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = RoleBasedNonBazargahPurchaseForm(instance=purchase, user_role=user_role)
    
    # فرم تخصیص جدید
    allocation_form = NonBazargahAllocationForm(purchase=purchase)
    
    # فرم آپلود اکسل تخصیص‌ها
    excel_upload_form = ExcelAllocationUploadForm()
    
    # فرم آپلود اکسل بارنامه‌ها
    excel_barnameh_upload_form = ExcelBarnamehUploadForm()
    
    # دریافت نوتیفیکیشن‌ها
    notifications = NotificationService.get_unread_notifications(request.user)
    
    # دریافت تمام بارنامه‌های مرتبط
    all_barnamehs = purchase.get_all_barnamehs()
    
    # سازماندهی بارنامه‌ها بر اساس تخصیص
    allocations_with_barnamehs = []
    for allocation in allocations:
        allocation_barnamehs = allocation.barnamehs.all()
        allocations_with_barnamehs.append({
            'allocation': allocation,
            'barnamehs': allocation_barnamehs,
            'barnameh_forms': {barnameh.id: BarnamehForm(instance=barnameh) for barnameh in allocation_barnamehs}
        })
    
    context = {
        'purchase': purchase,
        'form': form,
        'allocation_form': allocation_form,
        'excel_upload_form': excel_upload_form,
        'excel_barnameh_upload_form': excel_barnameh_upload_form,
        'allocations': allocations,
        'allocations_with_barnamehs': allocations_with_barnamehs,
        'total_allocated_weight': total_allocated_weight,
        'remaining_weight': remaining_weight,
        'requested_weight_kg': requested_weight_kg,
        'progress_steps': progress_steps,
        'user_role': user_role,
        'notifications': notifications,
        'barnameh_form': BarnamehForm(),
        'all_barnamehs': all_barnamehs,
    }
    
    return render(request, 'non_bazargah_purchase_CRUD_view.html', context)


@role_required('admin', 'logistics_manager', 'sales_agent')
@login_required
def delete_non_bazargah_purchase_view(request, purchase_id):
    """حذف خرید خارج بازارگاه"""
    logger.warning(f"درخواست حذف خرید خارج بازارگاه {purchase_id} توسط {request.user.username} با IP {get_client_ip(request)}")
    
    purchase = get_object_or_404(NonBazargahPurchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کارشناس فروش
    if user_role == 'sales_agent':
        if not purchase.customer or not hasattr(request.user, 'sales_agent'):
            messages.error(request, 'شما اجازه حذف این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
        
        if not purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
            messages.error(request, 'شما اجازه حذف این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
    
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, 'خرید با موفقیت حذف شد')
        return redirect('non_bazargah_purchase_list')
    
    context = {
        'purchase': purchase,
    }
    return render(request, 'confirm_delete_non_bazargah.html', context)


@role_required('admin', 'logistics_manager')
@login_required
def download_allocation_excel_template(request):
    """دانلود قالب اکسل برای تخصیص‌ها"""
    logger.warning(f"دانلود قالب اکسل تخصیص‌ها توسط {request.user.username}, IP: {get_client_ip(request)}")
    
    # ایجاد فایل اکسل در حافظه
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('تخصیص آدرس‌ها')
    
    # تنظیم استایل‌ها
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#007bff',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    data_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter'
    })
    
    # تنظیم عرض ستون‌ها
    worksheet.set_column('A:A', 40)  # آدرس تحویل
    worksheet.set_column('B:B', 15)  # کد پستی
    worksheet.set_column('C:C', 25)  # نام گیرنده
    worksheet.set_column('D:D', 20)  # شماره هماهنگی
    worksheet.set_column('E:E', 18)  # وزن تخصیص یافته
    worksheet.set_column('F:F', 15)  # شماره تخصیص
    worksheet.set_column('G:G', 30)  # توضیحات
    
    # نوشتن هدرها
    headers = [
        'آدرس تحویل', 'کد پستی', 'نام گیرنده', 
        'شماره هماهنگی', 'وزن تخصیص یافته', 'شماره تخصیص', 'توضیحات'
    ]
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # نوشتن نمونه داده‌ها
    sample_data = [
        [
            'تهران، خیابان ولیعصر، پلاک 123، طبقه 2',
            '1234567890',
            'علی احمدی',
            '09123456789',
            500,
            'A001',
            'تحویل در منزل - تماس قبل از تحویل'
        ],
        [
            'کرج، بلوار فردوس، کوچه 45، پلاک 12',
            '0987654321',
            'فاطمه محمدی',
            '09987654321',
            300,
            'A002',
            'تحویل در محل کار - ساعت کاری'
        ],
        [
            'اصفهان، خیابان چهارباغ، پلاک 67',
            '1111111111',
            'حسن رضایی',
            '09111111111',
            750,
            'A003',
            'تحویل در منزل - عصر'
        ]
    ]
    
    for row, data in enumerate(sample_data, start=1):
        for col, value in enumerate(data):
            worksheet.write(row, col, value, data_format)
    
    # بستن workbook
    workbook.close()
    output.seek(0)
    
    # ایجاد پاسخ HTTP
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="template_allocations.xlsx"'
    
    return response


@role_required('admin', 'logistics_manager')
@login_required
def download_barnameh_excel_template(request):
    """دانلود قالب اکسل برای بارنامه‌ها"""
    logger.warning(f"دانلود قالب اکسل بارنامه‌ها توسط {request.user.username}, IP: {get_client_ip(request)}")
    
    # ایجاد فایل اکسل در حافظه
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('بارنامه‌ها')
    
    # تنظیم استایل‌ها
    header_format = workbook.add_format({
        'bold': True,
        'bg_color': '#28a745',
        'font_color': 'white',
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    data_format = workbook.add_format({
        'border': 1,
        'align': 'right',
        'valign': 'vcenter'
    })
    
    # تنظیم عرض ستون‌ها
    worksheet.set_column('A:A', 15)  # شناسه تخصیص
    worksheet.set_column('B:B', 20)  # شماره بارنامه
    worksheet.set_column('C:C', 25)  # نام راننده
    worksheet.set_column('D:D', 20)  # شماره تلفن راننده
    worksheet.set_column('E:E', 15)  # پلاک خودرو
    worksheet.set_column('F:F', 15)  # وزن خالی
    worksheet.set_column('G:G', 15)  # وزن پر
    worksheet.set_column('H:H', 15)  # وزن تحویلی
    worksheet.set_column('I:I', 20)  # زمان ورود ماشین
    worksheet.set_column('J:J', 20)  # زمان وزن خالی
    worksheet.set_column('K:K', 20)  # زمان وزن پر
    worksheet.set_column('L:L', 20)  # زمان خروج از انبار
    worksheet.set_column('M:M', 20)  # زمان تحویل
    worksheet.set_column('N:N', 30)  # توضیحات
    
    # نوشتن هدرها
    headers = [
        'شناسه تخصیص', 'شماره بارنامه', 'نام راننده', 'شماره تلفن راننده', 
        'پلاک خودرو', 'وزن خالی', 'وزن پر', 'وزن تحویلی', 
        'زمان ورود ماشین', 'زمان وزن خالی', 'زمان وزن پر', 'زمان خروج از انبار', 'زمان تحویل', 'توضیحات'
    ]
    
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
    
    # نوشتن نمونه داده‌ها
    sample_data = [
        [
            'A001',  # شماره تخصیص
            'B-001',  # شماره بارنامه
            'احمد محمدی',
            '09123456789',
            '12ب12345',
            15000,  # وزن خالی
            20000,  # وزن پر
            19000,  # وزن تحویلی
            '1403/06/15 08:30',  # زمان ورود ماشین
            '1403/06/15 09:00',  # زمان وزن خالی
            '1403/06/15 11:30',  # زمان وزن پر
            '1403/06/15 12:00',  # زمان خروج از انبار
            '1403/06/15 16:30',  # زمان تحویل
            'تحویل در صبح - تماس قبل از رسیدن'
        ],
        [
            'A002',  # شماره تخصیص
            'B-002',  # شماره بارنامه
            'علی رضایی',
            '09987654321',
            '34ج67890',
            12000,  # وزن خالی
            17000,  # وزن پر
            16500,  # وزن تحویلی
            '1403/06/16 10:00',  # زمان ورود ماشین
            '1403/06/16 10:30',  # زمان وزن خالی
            '1403/06/16 13:00',  # زمان وزن پر
            '1403/06/16 13:30',  # زمان خروج از انبار
            '1403/06/16 18:00',  # زمان تحویل
            'تحویل در عصر'
        ]
    ]
    
    for row, data in enumerate(sample_data, start=1):
        for col, value in enumerate(data):
            worksheet.write(row, col, value, data_format)
    
    # بستن workbook
    workbook.close()
    output.seek(0)
    
    # ایجاد پاسخ HTTP
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="template_barnamehs.xlsx"'
    
    return response


# View قدیمی آپلود مدرک - حذف شده چون حالا درون فرم اصلی handle می‌شود
# @role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
# @login_required  
# @csrf_exempt
# def upload_non_bazargah_document(request, purchase_id):
#     """آپلود مدارک برای خرید خارج بازارگاه - منسوخ شده"""
#     return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
