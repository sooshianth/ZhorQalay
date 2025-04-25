import os
import pandas as pd
import logging
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.files import File

from ..models import ExcelFile, BGExcelFile, ExcelProcessingLog
from core._models import CargoProduct, Purchase
from core.PurchaseModel import ShenaseTakhsis, PurchaseStateChange
from core.CustomerModel import Customer

from .utils import (
    fix_excel_headers, 
    extract_province_from_address, 
    map_excel_field_to_model,
    get_super_user_agent
)

# ایجاد یک لاگر برای دیباگ
logger = logging.getLogger(__name__)

@login_required
def process_bge_file(request, file_id):
    """
    پردازش فایل اکسل بازارگاه و به‌روزرسانی رکوردهای Purchase
    """
    bge_file = get_object_or_404(BGExcelFile, id=file_id)


    if request.method == 'POST':

            
        if not bge_file.is_approved:
            messages.error(request, 'این فایل تایید نشده است')
            return redirect('excel_manager:bge_files_list')

        if bge_file.is_processed:
            messages.error(request, 'این فایل قبلا پردازش شده است')
            context = {
                'bge_file': bge_file,
                'page_title': 'پردازش فایل اکسل بازارگاه',
            }
            return render(request, 'excel_manager/process_bge_file.html', context)

        try:
            # دریافت فایل بازارگاه
            file_path = bge_file.file.path
            file_extension = os.path.splitext(file_path)[1].lower()
            
            # ایجاد لاگ پردازش
            processing_log = ExcelProcessingLog.objects.create(
                excel_file=bge_file,
                processed_by=request.user,
                success=False,  # پیش‌فرض ناموفق، در صورت موفقیت به‌روزرسانی می‌شود
                records_processed=0,
                records_updated=0,
                records_failed=0,
                log_message=""
            )
            
            try:
                # خواندن محتوای فایل اکسل
                df, error_msg = read_excel_file(file_path, file_extension)
                
                if error_msg:
                    processing_log.log_message = error_msg
                    processing_log.save()
                    messages.error(request, error_msg)
                    return redirect('excel_manager:bge_files_list')
                
                # بررسی وجود ستون‌های ضروری
                validation_result = validate_excel_columns(df)
                if not validation_result['success']:
                    processing_log.log_message = validation_result['message']
                    processing_log.save()
                    messages.error(request, validation_result['message'])
                    return redirect('excel_manager:bge_files_list')
                
                cottage_column = validation_result['cottage_column']
                
                # پردازش رکوردها
                processing_result = process_excel_records(df, bge_file, cottage_column)
                
                # به‌روزرسانی لاگ پردازش
                processing_log.success = processing_result['records_failed'] == 0
                processing_log.records_processed = processing_result['records_processed']
                processing_log.records_updated = processing_result['records_updated']
                processing_log.records_failed = processing_result['records_failed']
                processing_log.log_message = processing_result['log_message']
                processing_log.save()
                
                # به‌روزرسانی وضعیت فایل
                bge_file.is_processed = True
                bge_file.save()
                
                # اگر درخواست AJAX باشد، پاسخ JSON برگردان
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': processing_result['summary_message'],
                        'records_processed': processing_result['records_processed'],
                        'records_updated': processing_result['records_updated'],
                        'records_failed': processing_result['records_failed'],
                        'has_cleaned_file': bge_file.cleaned_file and True or False,
                        'cleaned_file_url': bge_file.cleaned_file.url if bge_file.cleaned_file else None
                    })
                
                messages.success(request, processing_result['summary_message'])
                return redirect('excel_manager:bge_files_list')
                
            except Exception as e:
                logger.error(f"خطا در پردازش فایل: {str(e)}")
                processing_log.log_message = f"خطا در پردازش فایل: {str(e)}"
                processing_log.save()
                
                # اگر درخواست AJAX باشد، پاسخ JSON برگردان
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'خطا در پردازش فایل: {str(e)}'
                    }, status=500)
                
                messages.error(request, f'خطا در پردازش فایل: {str(e)}')
                return redirect('excel_manager:bge_files_list')
                
        except Exception as e:
            logger.error(f"خطای کلی در پردازش فایل: {str(e)}")
            
            # اگر درخواست AJAX باشد، پاسخ JSON برگردان
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f'خطای کلی در پردازش فایل: {str(e)}'
                }, status=500)
            
            messages.error(request, f'خطای کلی در پردازش فایل: {str(e)}')
            return redirect('excel_manager:bge_files_list')
    
    # نمایش جزئیات فایل برای پردازش
    context = {
        'bge_file': bge_file,
        'page_title': 'پردازش فایل اکسل بازارگاه',
    }
    
    # بررسی وجود فایل تمیز شده در مدل برای نمایش لینک دانلود
    if bge_file.is_processed and bge_file.cleaned_file:
        context['has_cleaned_file'] = True
    
    return render(request, 'excel_manager/process_bge_file.html', context)

def process_bge_file_data(bge_file, user):
    """
    پردازش داده‌های فایل اکسل بازارگاه
    این تابع جداگانه ایجاد شده تا قابلیت استفاده برنامه‌ای هم داشته باشد
    """
    try:
        # دریافت فایل بازارگاه
        file_path = bge_file.file.path
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # ایجاد لاگ پردازش
        processing_log = ExcelProcessingLog.objects.create(
            excel_file=bge_file,
            processed_by=user,
            success=False,  # پیش‌فرض ناموفق، در صورت موفقیت به‌روزرسانی می‌شود
            records_processed=0,
            records_updated=0,
            records_failed=0,
            log_message=""
        )
        
        # خواندن محتوای فایل اکسل با فانکشن جداگانه
        df, error_msg = read_excel_file(file_path, file_extension)
        
        if error_msg:
            processing_log.log_message = error_msg
            processing_log.save()
            return {'success': False, 'message': error_msg}
            
        # بررسی وجود ستون‌های ضروری
        validation_result = validate_excel_columns(df)
        if not validation_result['success']:
            processing_log.log_message = validation_result['message']
            processing_log.save()
            return {'success': False, 'message': validation_result['message']}
        
        cottage_column = validation_result['cottage_column']
        
        # پردازش رکوردها
        processing_result = process_excel_records(df, bge_file, cottage_column)
        
        # به‌روزرسانی لاگ پردازش
        processing_log.success = processing_result['records_failed'] == 0
        processing_log.records_processed = processing_result['records_processed']
        processing_log.records_updated = processing_result['records_updated']
        processing_log.records_failed = processing_result['records_failed']
        processing_log.log_message = processing_result['log_message']
        processing_log.save()
        
        # به‌روزرسانی وضعیت فایل
        bge_file.is_processed = True
        bge_file.save()
        
        return {
            'success': True, 
            'message': processing_result['summary_message']
        }
            
    except Exception as e:
        logger.error(f"خطای کلی در پردازش فایل: {str(e)}")
        
        # در صورت وجود، آپدیت لاگ پردازش
        if 'processing_log' in locals():
            processing_log.log_message = f"خطای کلی در پردازش فایل: {str(e)}"
            processing_log.save()
            
        return {
            'success': False, 
            'message': f'خطای کلی در پردازش فایل: {str(e)}'
        } 

def read_excel_file(file_path, file_extension):
    """
    خواندن فایل اکسل با در نظر گرفتن نوع آن
    """
    try:
        # خواندن محتوای فایل اکسل با توجه به نوع آن
        if file_extension == '.xls':
            try:
                # ابتدا تلاش برای خواندن به عنوان HTML
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '<html' in content.lower():
                    # این فایل xls حاوی HTML است
                    tables = pd.read_html(content)
                    if not tables:
                        return None, "جدولی در فایل اکسل یافت نشد."
                    df = tables[0]
                else:
                    # این یک فایل xls معمولی است
                    df = pd.read_excel(file_path)
                    # بررسی و پیدا کردن ردیف header
                    df = fix_excel_headers(df)
            except UnicodeDecodeError:
                # این یک فایل باینری است، نه فایل متنی
                df = pd.read_excel(file_path)
                # بررسی و پیدا کردن ردیف header
                df = fix_excel_headers(df)
        else:  # فایل xlsx
            df = pd.read_excel(file_path)
            # بررسی و پیدا کردن ردیف header
            df = fix_excel_headers(df)
        
        # گزارش دیباگ برای تعداد ردیف‌ها
        logger.debug(f"تعداد ردیف‌های خوانده شده: {len(df)}")
        logger.debug(f"ستون‌های موجود در فایل: {df.columns.tolist()}")
        
        return df, None
        
    except Exception as e:
        error_msg = f"خطا در خواندن فایل اکسل: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def validate_excel_columns(df):
    """
    بررسی وجود ستون‌های ضروری در فایل اکسل
    """
    # بررسی ستون کوتاژ
    has_cottage_column = False
    cottage_column = None
    for column in ['کد کوتاژ', 'کوتاژ']:
        if column in df.columns:
            has_cottage_column = True
            cottage_column = column
            break
    
    if not has_cottage_column:
        error_msg = "ستون کوتاژ در فایل یافت نشد"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    
    # بررسی وجود ستون‌های ضروری
    required_columns = ['کد', 'شناسه تخصیص', 'وزن کل خرید', 'کد ملی تحویل', 'شماره هماهنگی تحویل', 'شماره همراه خریدار', 
                        'نام خریدار', 'آدرس تحویل', 'مبلغ پرداختی', 'شیوه پرداخت']
    
    # بررسی اینکه آیا ستون‌های مورد نیاز در دیتافریم وجود دارند
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        error_msg = f"ستون‌های زیر در فایل اکسل یافت نشد: {', '.join(missing_columns)}"
        logger.error(error_msg)
        return {'success': False, 'message': error_msg}
    
    return {
        'success': True, 
        'cottage_column': cottage_column
    }

def process_excel_records(df, bge_file, cottage_column):
    """
    پردازش رکوردهای فایل اکسل و به‌روزرسانی دیتابیس
    """
    # لیست رکوردهایی که باید از اکسل حذف شوند
    rows_to_remove = []
    
    # تعریف کاربر superuser برای تخصیص به مشتریان جدید
    super_agent = get_super_user_agent()
    
    # ذخیره CargoProduct های جدید ایجاد شده
    created_cargo_products = {}
    
    # پردازش رکوردها
    records_processed = 0
    records_updated = 0
    records_created = 0
    records_failed = 0
    cargo_products_created = 0
    error_messages = []
    
    # پردازش هر رکورد جداگانه
    for idx, row in df.iterrows():
        logger.debug(f"شروع پردازش رکورد {idx+1}")
        
        try:
            records_processed += 1
            
            # استخراج اطلاعات ضروری
            purchase_number = str(row['کد']).strip() if pd.notna(row['کد']) else None
            shenase_takhsis = str(row['شناسه تخصیص']).strip() if pd.notna(row['شناسه تخصیص']) else None
            code_melli_tahvil = str(row['کد ملی تحویل']).strip() if pd.notna(row['کد ملی تحویل']) else None
            tahvil_phone_number = str(row['شماره هماهنگی تحویل']).strip() if pd.notna(row['شماره هماهنگی تحویل']) else None
            bazaargah_phone_number = str(row['شماره همراه خریدار']).strip() if pd.notna(row['شماره همراه خریدار']) else None
            customer_name = str(row['نام خریدار']).strip() if pd.notna(row['نام خریدار']) else None
            address = str(row['آدرس تحویل']).strip() if pd.notna(row['آدرس تحویل']) else None
            order_weight = int(float(row['وزن سفارش'])) if 'وزن سفارش' in df.columns and pd.notna(row['وزن سفارش']) else 0
            delivered_weight = int(float(row['وزن کل خرید'])) if pd.notna(row['وزن کل خرید']) else 0
            amount_paid = int(float(row['مبلغ پرداختی'])) if pd.notna(row['مبلغ پرداختی']) else None
            payment_method = 'نقدی' if pd.notna(row['شیوه پرداخت']) and row['شیوه پرداخت'] == 'نقدی' else 'توافقی'
            tracking_number = str(row['شماره پیگیری']).strip() if 'شماره پیگیری' in df.columns and pd.notna(row['شماره پیگیری']) else None
            
            # استخراج اطلاعات وزن بارنامه
            barnameh_weight = int(float(row['وزن بارنامه شده'])) if 'وزن بارنامه شده' in df.columns and pd.notna(row['وزن بارنامه شده']) else 0
            not_barnameh_weight = int(float(row['وزن بارنامه نشده'])) if 'وزن بارنامه نشده' in df.columns and pd.notna(row['وزن بارنامه نشده']) else 0
            
            # تشخیص اختلاف وزن (کسری یا سرک)
            extelaf_type, extelaf_weight, extelaf_amount = calculate_extelaf(
                order_weight, barnameh_weight, not_barnameh_weight, row
            )
            
            # استخراج کوتاژ از فایل
            current_cottage = str(row[cottage_column]).strip() if pd.notna(row[cottage_column]) else None
            
            # نرمالایز کردن شماره تلفن
            bazaargah_phone_number = normalize_phone_number(bazaargah_phone_number)
            tahvil_phone_number = normalize_phone_number(tahvil_phone_number)
            
            # بررسی وجود خرید با شماره خرید مشابه
            purchase = Purchase.objects.filter(purchase_number=purchase_number).first()
            
            # بررسی قبلاً ثبت شدن شناسه تخصیص
            existing_shenase = ShenaseTakhsis.objects.filter(code=shenase_takhsis).exists() if shenase_takhsis else False
            if existing_shenase:
                rows_to_remove.append(idx)
                continue
            
            # تعیین محصول (CargoProduct) براساس کوتاژ
            cargo_product = get_or_create_cargo_product(
                current_cottage, bge_file, created_cargo_products, row
            )
            
            if not cargo_product:
                cargo_product = bge_file.cargo
            
            # هر پردازش در یک بلاک atomic جداگانه انجام می‌شود
            with transaction.atomic():
                if purchase:
                    # به‌روزرسانی خرید موجود
                    update_result = update_existing_purchase(
                        purchase, code_melli_tahvil, tahvil_phone_number, 
                        bazaargah_phone_number, address, order_weight, 
                        delivered_weight, cargo_product, amount_paid, 
                        payment_method, tracking_number, extelaf_type, 
                        extelaf_weight, extelaf_amount, shenase_takhsis
                    )
                    
                    if update_result['success']:
                        records_updated += 1
                    else:
                        records_failed += 1
                        error_messages.append(update_result['error'])
                else:
                    # ایجاد خرید جدید
                    create_result = create_new_purchase(
                        customer_name, bazaargah_phone_number, purchase_number, 
                        tracking_number, code_melli_tahvil, tahvil_phone_number, 
                        address, order_weight, delivered_weight, cargo_product, 
                        amount_paid, payment_method, shenase_takhsis,
                        extelaf_type, extelaf_weight, extelaf_amount, 
                        super_agent, row
                    )
                    
                    if create_result['success']:
                        records_created += 1
                    else:
                        records_failed += 1
                        error_messages.append(create_result['error'])
                        
        except Exception as e:
            records_failed += 1
            error_messages.append(f"خطا در پردازش رکورد {idx+1}: {str(e)}")
            logger.error(f"خطا در پردازش رکورد {idx+1}: {str(e)}")
    
    # حذف رکوردهای با شناسه تخصیص تکراری
    if rows_to_remove:
        df = df.drop(rows_to_remove).reset_index(drop=True)
    
    # ذخیره فایل اکسل تمیز شده
    save_cleaned_excel(df, bge_file.file.path, bge_file)
    
    # ایجاد پیام‌های خلاصه و لاگ
    log_message = f"تعداد کل رکوردها: {records_processed}\n"
    log_message += f"تعداد رکوردهای به‌روزرسانی شده: {records_updated}\n"
    log_message += f"تعداد رکوردهای ایجاد شده: {records_created}\n"
    log_message += f"تعداد محصولات ایجاد شده: {cargo_products_created}\n"
    log_message += f"تعداد رکوردهای ناموفق: {records_failed}\n"
    
    if error_messages:
        log_message += "خطاها:\n" + "\n".join(error_messages)
    
    success_message = f"فایل با موفقیت پردازش شد. {records_updated} رکورد به‌روزرسانی شد و {records_created} رکورد جدید ایجاد شد."
    if cargo_products_created > 0:
        success_message += f" همچنین {cargo_products_created} محصول جدید براساس کوتاژهای موجود در فایل ایجاد شد."
    
    return {
        'records_processed': records_processed,
        'records_updated': records_updated,
        'records_created': records_created,
        'records_failed': records_failed,
        'cargo_products_created': cargo_products_created,
        'log_message': log_message,
        'summary_message': success_message
    }

def calculate_extelaf(order_weight, barnameh_weight, not_barnameh_weight, row):
    """
    محاسبه اختلاف وزن (کسری یا سرک) و مبلغ آن
    """
    extelaf_type = None
    extelaf_weight = 0
    extelaf_amount = 0
    
    if barnameh_weight > order_weight:  # سرک
        extelaf_type = 'سرک'
        extelaf_weight = barnameh_weight - order_weight
        # محاسبه مبلغ اختلاف بر اساس فی خرید
        if 'قیمت هر واحد' in row.index and pd.notna(row['قیمت هر واحد']):
            price_per_unit = int(float(row['قیمت هر واحد']))
            extelaf_amount = extelaf_weight * price_per_unit
    elif barnameh_weight < order_weight:  # کسری
        extelaf_type = 'کسری'
        extelaf_weight = order_weight - barnameh_weight
        # کسری برابر با وزن بارنامه نشده
        if not_barnameh_weight > 0:
            extelaf_weight = not_barnameh_weight
        # محاسبه مبلغ اختلاف بر اساس فی خرید
        if 'قیمت هر واحد' in row.index and pd.notna(row['قیمت هر واحد']):
            price_per_unit = int(float(row['قیمت هر واحد']))
            extelaf_amount = extelaf_weight * price_per_unit
    
    return extelaf_type, extelaf_weight, extelaf_amount

def normalize_phone_number(phone_number):
    """
    نرمال‌سازی شماره تلفن به فرمت استاندارد
    """
    if not phone_number:
        return None
        
    phone_number = re.sub(r'\D', '', phone_number)
    if phone_number.startswith('0'):
        phone_number = phone_number[1:]
    elif phone_number.startswith('98'):
        phone_number = phone_number[2:]
    
    return phone_number

def get_or_create_cargo_product(current_cottage, bge_file, created_cargo_products, row):
    """
    یافتن یا ایجاد محصول (CargoProduct) بر اساس کوتاژ
    """
    cargo_product = None
    
    # ابتدا بررسی می‌کنیم آیا کوتاژ در محصول آپلود شده وجود دارد
    if current_cottage == bge_file.cargo.cottage:
        cargo_product = bge_file.cargo
    # سپس بررسی می‌کنیم آیا کوتاژ در محصولات موجود وجود دارد
    elif current_cottage:
        # بررسی در محصولات قبلاً ایجاد شده در این پردازش
        if current_cottage in created_cargo_products:
            cargo_product = created_cargo_products[current_cottage]
        else:
            # بررسی در دیتابیس
            try:
                cargo_product = CargoProduct.objects.get(cottage=current_cottage)
            except CargoProduct.DoesNotExist:
                # ایجاد محصول جدید براساس کوتاژ
                try:
                    with transaction.atomic():
                        # تعیین نوع محصول از فایل اکسل
                        product_type = determine_product_type(row)
                        
                        # اگر نوع محصول از فایل تشخیص داده نشد، از محصول موجود استفاده کن
                        if not product_type:
                            product_type = bge_file.cargo.product_type
                            logger.info(f"نوع محصول از فایل تشخیص داده نشد، استفاده از نوع محصول {bge_file.cargo.get_product_type_display()}")
                        
                        # تعیین قیمت خرید و فروش
                        company_price, customer_price = determine_product_prices(row, bge_file.cargo)
                        
                        # استفاده از مقادیر محصول فعلی برای ایجاد محصول جدید
                        new_cargo_product = CargoProduct.objects.create(
                            type='bazaargah',  # نوع خرید بازارگاه
                            cottage=current_cottage,  # کوتاژ جدید
                            company_price=company_price,  # قیمت خرید
                            customer_price=customer_price,  # قیمت فروش
                            product_type=product_type,  # نوع محصول
                            country=bge_file.cargo.country,  # کشور مشابه
                            importer_name=bge_file.cargo.importer_name,  # نام واردکننده مشابه
                            port=bge_file.cargo.port,  # محل بارگیری مشابه
                            loading_time=bge_file.cargo.loading_time,  # زمان بارگیری مشابه
                            description=f"ایجاد شده به صورت خودکار در پردازش فایل {bge_file.title}",
                            order_weight=bge_file.cargo.order_weight,  # وزن مشابه
                            delivered_weight=bge_file.cargo.delivered_weight,  # وزن مشابه
                            status=True  # فعال
                        )
                        created_cargo_products[current_cottage] = new_cargo_product
                        cargo_product = new_cargo_product
                        logger.info(f"محصول جدید با کوتاژ {current_cottage} و نوع {cargo_product.get_product_type_display()} ایجاد شد")
                except Exception as ce:
                    logger.error(f"خطا در ایجاد محصول جدید با کوتاژ {current_cottage}: {str(ce)}")
    
    return cargo_product

def determine_product_type(row):
    """
    تعیین نوع محصول بر اساس اطلاعات موجود در ردیف اکسل
    """
    product_type = None
    
    # بررسی وجود ستون "عنوان کالا" یا مشابه آن
    product_name_column = None
    for column in ['عنوان کالا', 'نام کالا', 'محصول', 'کالا']:
        if column in row.index and pd.notna(row[column]):
            product_name_column = column
            break
    
    if product_name_column:
        product_name = str(row[product_name_column]).strip().lower()
        
        # تشخیص نوع محصول بر اساس نام کالا
        if 'ذرت' in product_name:
            product_type = 'corn'
        elif 'جو' in product_name:
            product_type = 'barley'
        elif 'کنجاله سویا' in product_name:
            product_type = 'soy_meal'
        elif 'کنجاله آفتابگردان' in product_name:
            product_type = 'sunflower_meal'
        elif 'کنجاله کلزا' in product_name:
            product_type = 'rapeseed_meal'
        elif 'سویا استحصالی داخلی' in product_name:
            product_type = 'local_extracted_soy'
        elif 'سویا استحصالی خارجی' in product_name:
            product_type = 'foreign_extracted_soy'
        elif 'دان سویا' in product_name or 'سویا' in product_name:
            product_type = 'soy_grain'
        elif 'دان پنبه' in product_name or 'پنبه دانه' in product_name:
            product_type = 'cotton_seed'
        elif 'یونجه' in product_name:
            product_type = 'alfalfa'
    
    return product_type

def determine_product_prices(row, cargo_product):
    """
    تعیین قیمت خرید و فروش محصول
    """
    company_price = 0
    customer_price = 0
    
    # تلاش برای استخراج قیمت از فایل
    if 'قیمت هر واحد' in row.index and pd.notna(row['قیمت هر واحد']):
        try:
            price_per_unit = int(float(row['قیمت هر واحد']))
            company_price = price_per_unit
            customer_price = price_per_unit
        except (ValueError, TypeError):
            # اگر تبدیل به عدد با خطا مواجه شد، از مقادیر محصول اصلی استفاده کن
            logger.warning(f"قیمت در فایل با فرمت نامعتبر: {row['قیمت هر واحد']}")
            company_price = cargo_product.company_price
            customer_price = cargo_product.customer_price
    else:
        # اگر قیمت در فایل نبود، از مقادیر محصول اصلی استفاده کن
        company_price = cargo_product.company_price
        customer_price = cargo_product.customer_price
    
    return company_price, customer_price

def update_existing_purchase(purchase, code_melli_tahvil, tahvil_phone_number, 
                         bazaargah_phone_number, address, order_weight, 
                         delivered_weight, cargo_product, amount_paid, 
                         payment_method, tracking_number, extelaf_type, 
                         extelaf_weight, extelaf_amount, shenase_takhsis):
    """
    به‌روزرسانی خرید موجود با اطلاعات جدید
    """
    try:
        # به‌روزرسانی خرید موجود - استفاده از update به جای save برای دور زدن validation
        Purchase.objects.filter(id=purchase.id).update(
            code_melli_tahvil=code_melli_tahvil,
            tahvil_phone_number=tahvil_phone_number,
            bazaargah_phone_number=bazaargah_phone_number,
            address=address,
            order_weight=order_weight,
            delivered_weight=delivered_weight,
            cargo=cargo_product,
            amount_paid=amount_paid,
            payment_method=payment_method,
            tracking_number=tracking_number,
            extelaf_type=extelaf_type,
            extelaf_weight=extelaf_weight if extelaf_weight > 0 else None,
            extelaf_amount=extelaf_amount if extelaf_amount > 0 else None,
            company_price=cargo_product.company_price,
            customer_price=cargo_product.customer_price,
            shenase_takhsis=shenase_takhsis
        )
        
        # اگر مشتری آدرس دارد، استان را استخراج کرده و در فیلد city ذخیره می‌کنیم
        if address and purchase.customer:
            province = extract_province_from_address(address)
            logger.debug(f"آدرس مشتری موجود: {address}")
            logger.debug(f"استان استخراج شده برای مشتری موجود: {province}")
            # اگر استان استخراج شده و متفاوت با مقدار قبلی باشد، آن را به‌روزرسانی می‌کنیم
            if province and (not purchase.customer.city or province != purchase.customer.city):
                old_city = purchase.customer.city or "خالی"
                Customer.objects.filter(id=purchase.customer.id).update(city=province)
                logger.debug(f"استان مشتری موجود از '{old_city}' به '{province}' به‌روزرسانی شد")
        
        # افزودن شناسه تخصیص جدید به خرید
        if shenase_takhsis and not ShenaseTakhsis.objects.filter(purchase=purchase, code=shenase_takhsis).exists():
            ShenaseTakhsis.objects.create(
                purchase=purchase,
                code=shenase_takhsis
            )
            # آپدیت وضعیت خرید به ALLOCATION_REGISTERED اگر از حالت INITIATED یا SMS_SENT باشد
            if purchase.state in ['INITIATED', 'SMS_SENT']:
                purchase.change_state('ALLOCATION_REGISTERED', None, 'تخصیص در بازارگاه ثبت شده است')
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی خرید {purchase.purchase_number}: {str(e)}")
        return {'success': False, 'error': f"خطا در به‌روزرسانی خرید {purchase.purchase_number}: {str(e)}"}

def create_new_purchase(customer_name, bazaargah_phone_number, purchase_number, 
                        tracking_number, code_melli_tahvil, tahvil_phone_number, 
                        address, order_weight, delivered_weight, cargo_product, 
                        amount_paid, payment_method, shenase_takhsis,
                        extelaf_type, extelaf_weight, extelaf_amount, 
                        super_agent, row):
    """
    ایجاد خرید جدید با اطلاعات داده شده
    """
    try:
        # ایجاد مشتری جدید اگر وجود ندارد
        customer = None
        
        if bazaargah_phone_number or customer_name:
            customer = Customer.objects.filter(name=customer_name).first() # or Customer.objects.filter(phone_number=bazaargah_phone_number).first()
            if not customer:
                try:
                    # استخراج زمینه فعالیت بر اساس اکسل:
                    field_of_activity_raw = None
                    for fieldname in ['نوع کاربری خریدار', 'زمینه فعالیت', 'حیطه فعالیت']:
                        if fieldname in row.index and pd.notna(row[fieldname]):
                            field_of_activity_raw = str(row[fieldname]).strip()
                            break

                    field_of_activity = map_excel_field_to_model(field_of_activity_raw)

                    # استخراج استان از آدرس
                    province = None
                    if address:
                        province = extract_province_from_address(address)
                        logger.debug(f"آدرس: {address}")
                        logger.debug(f"استان استخراج شده: {province}")

                    customer = Customer.objects.create(
                        phone_number=bazaargah_phone_number,
                        name=customer_name if customer_name else "مشتری جدید",
                        field_of_activity=field_of_activity if field_of_activity else 'chicken',
                        sms_preference=True,
                        is_bazaargah_enjoyer=True,
                        city=province  # ذخیره استان در فیلد city
                    )

                    logger.debug(f"مشتری جدید ایجاد شد با شناسه: {customer.id}")
                    # اضافه کردن کارشناس فروش
                    if super_agent:
                        customer.sales_agent.add(super_agent)
                except Exception as ce:
                    logger.error(f"خطا در ایجاد مشتری: {str(ce)}")
                    return {'success': False, 'error': f"خطا در ایجاد مشتری برای خرید {purchase_number}: {str(ce)}"}

        if customer:
            # ایجاد شناسه منحصر به فرد برای خرید
            factor_code = "88"  # استفاده از کد ثابت برای جلوگیری از مشکلات
            
            # یافتن آخرین خرید
            try:
                last_purchase = Purchase.objects.filter(id__startswith=factor_code).order_by('-id').first()
                if last_purchase:
                    last_serial = str(last_purchase.id)[2:]
                    new_serial = int(last_serial) + 1
                else:
                    new_serial = 1
                
                purchase_id = f"{factor_code}{str(new_serial).zfill(4)}"
                logger.debug(f"شناسه خرید جدید: {purchase_id}")
                
                # ایجاد خرید جدید با ORM جنگو به جای SQL مستقیم
                new_purchase = Purchase(
                    id=purchase_id,
                    customer=customer,
                    purchase_number=purchase_number,
                    tracking_number=tracking_number,
                    code_melli_tahvil=code_melli_tahvil,
                    tahvil_phone_number=tahvil_phone_number,
                    bazaargah_phone_number=bazaargah_phone_number,
                    address=address,
                    order_weight=order_weight,
                    delivered_weight=delivered_weight,
                    cargo=cargo_product,
                    amount_paid=amount_paid,
                    payment_method=payment_method,
                    type='bazaargah',
                    company_price=cargo_product.company_price,
                    customer_price=cargo_product.customer_price,
                    shenase_takhsis=shenase_takhsis,
                    extelaf_type=extelaf_type,
                    extelaf_weight=extelaf_weight if extelaf_weight > 0 else None,
                    extelaf_amount=extelaf_amount if extelaf_amount > 0 else None,
                    # وضعیت اولیه
                    state='DIFFERENCE_APPROVED',
                    # Boolean fields - فقط مواردی که هنوز به Stage Machine منتقل نشده‌اند
                    is_weight_costed=True,
                    is_ap_af=False,
                    is_archived=False,
                    is_canceled=False,
                    is_urgent=False
                )
                
                # Bypass validation when saving
                new_purchase.save(force_insert=True)
                
                # ثبت تغییر وضعیت در تاریخچه
                PurchaseStateChange.objects.create(
                    purchase=new_purchase,
                    previous_state='INITIATED',
                    new_state='BAZAARGAH_CONFIRMED',
                    notes='ثبت خودکار از فایل اکسل بازارگاه'
                )
                
                logger.debug(f"خرید جدید با موفقیت ایجاد شد: {purchase_id}")
                
                # افزودن شناسه تخصیص به خرید جدید
                if shenase_takhsis:
                    ShenaseTakhsis.objects.create(
                        purchase=new_purchase,
                        code=shenase_takhsis
                    )
                    
                return {'success': True}
                
            except Exception as e:
                logger.error(f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}")
                return {'success': False, 'error': f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}"}
        else:
            logger.error(f"ایجاد مشتری با شماره {bazaargah_phone_number} ناموفق بود")
            return {'success': False, 'error': f"خطا در ایجاد مشتری برای خرید {purchase_number}: مشتری ایجاد نشد"}
    
    except Exception as e:
        logger.error(f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}")
        return {'success': False, 'error': f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}"}

def save_cleaned_excel(df, original_file_path, excel_file_obj):
    """
    ذخیره فایل اکسل تمیز شده و ثبت آن در مدل مربوطه
    """
    try:
        # ذخیره فایل اکسل تمیز شده
        cleaned_filename = f"cleaned_{os.path.basename(original_file_path)}"
        cleaned_dir = os.path.join(settings.MEDIA_ROOT, 'cleaned_excel_files')
        
        # اطمینان از وجود دایرکتوری
        if not os.path.exists(cleaned_dir):
            os.makedirs(cleaned_dir)
            
        cleaned_file_path = os.path.join(cleaned_dir, cleaned_filename)
        
        # ذخیره فایل بر اساس نوع آن
        file_extension = os.path.splitext(original_file_path)[1].lower()
        
        if file_extension == '.xls':
            try:
                # بررسی اگر فایل اصلی حاوی HTML است
                with open(original_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '<html' in content.lower():
                    # بازسازی فایل HTML
                    html_content = """<html><head><meta http-equiv=Content-Type content='text/html; charset=utf-8'><style> .text { mso-number-format:\\@; } .trFormat{color:Black;background-color:#DEDFDE;}</style></head>"""
                    html_content += """<div style="direction:rtl;padding:5px 0"><span style="font:bold 12px tahoma; color:#008B00;line-height:180%"> ثبت اطلاعات حمل</span></div>"""
                    
                    # جایگزین کردن مستقیم عناوین و داده‌ها در HTML
                    tbody_html = """<table dir="rtl" cellspacing="0" cellpadding="7" style="font-family:Tahoma;font-size:11px;width:70%;"><tbody>"""
                    
                    # ایجاد تگ سطر عناوین فقط یکبار
                    thead_html = """<tr style='color:#E7E7FF;background-color:#4A3C8C;font-weight:bold;'>"""
                    for col in df.columns:
                        thead_html += f"<th>{col}</th>"
                    thead_html += "</tr>"
                    
                    tbody_html += thead_html
                    
                    # افزودن سطرهای داده
                    for _, row in df.iterrows():
                        tr_html = """<tr class="trFormat">"""
                        for col in df.columns:
                            tr_html += f'<td align="center">{row[col]}</td>'
                        tr_html += """</tr>"""
                        tbody_html += tr_html
                    
                    tbody_html += """</tbody></table></html>"""
                    
                    html_content += tbody_html
                    
                    with open(cleaned_file_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                else:
                    # ذخیره به عنوان فایل اکسل
                    df.to_excel(cleaned_file_path, index=False)
            except UnicodeDecodeError:
                # فایل باینری است، ذخیره به عنوان اکسل
                df.to_excel(cleaned_file_path, index=False)
        else:
            # ذخیره به عنوان فایل اکسل
            df.to_excel(cleaned_file_path, index=False)
        
        # ذخیره فایل تمیز شده در مدل
        try:
            # استفاده مستقیم از آبجکت ارسال شده
            from django.core.files import File
            
            logger.info(f"تلاش برای ذخیره فایل تمیز شده {cleaned_filename} در مدل با ID {excel_file_obj.id}")
            
            # ذخیره فایل تمیز شده در مدل
            with open(cleaned_file_path, 'rb') as f:
                # حذف فایل قبلی اگر وجود داشته باشد
                if excel_file_obj.cleaned_file:
                    if os.path.exists(excel_file_obj.cleaned_file.path):
                        excel_file_obj.cleaned_file.delete(save=False)
                
                # ذخیره فایل جدید
                excel_file_obj.cleaned_file.save(cleaned_filename, File(f), save=True)
            
            logger.info(f"فایل تمیز شده در مدل با مسیر {excel_file_obj.cleaned_file.path} ثبت شد")
            return excel_file_obj.cleaned_file.path
        except Exception as model_e:
            logger.error(f"خطا در ذخیره فایل تمیز شده در مدل: {str(model_e)}")
            return cleaned_file_path
            
    except Exception as e:
        logger.error(f"خطا در ذخیره فایل اکسل تمیز شده: {str(e)}")
        return None 