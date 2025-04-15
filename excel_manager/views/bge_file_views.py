import os
import pandas as pd
import logging
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib import messages
from ..models import ExcelFile, BGExcelFile, ExcelProcessingLog
from core._models import CargoProduct, Purchase
from core.PurchaseModel import ShenaseTakhsis
from core.CustomerModel import Customer, FIELD_OF_ACTIVITY
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

# ایجاد یک لاگر برای دیباگ
logger = logging.getLogger(__name__)

@login_required
def bge_files_list(request):
    """
    نمایش لیست فایل‌های اکسل بازارگاه
    """
    bge_files = BGExcelFile.objects.all().order_by('-created_at')
    
    context = {
        'bge_files': bge_files,
        'page_title': 'لیست فایل‌های اکسل بازارگاه',
    }
    return render(request, 'excel_manager/bge_files_list.html', context)


@login_required
def upload_bge_file(request):
    """آپلود فایل اکسل بازارگاه"""
    if request.method == 'POST':
        logger.debug(f"درخواست POST دریافت شد: {request.POST}")
        logger.debug(f"فایل‌های دریافتی: {request.FILES}")
        
        try:
            # دریافت داده‌های فرم
            cargo_id = request.POST.get('cargo_id')
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            excel_file = request.FILES.get('excel_file')
            force_upload = request.POST.get('force_upload') == 'true'  # بررسی آپلود اجباری
            
            logger.debug(f"داده‌های دریافتی: cargo_id={cargo_id}, title={title}, excel_file={excel_file}, force_upload={force_upload}")
            
            # بررسی داده‌های اجباری
            if not cargo_id or not title or not excel_file:
                logger.warning("داده‌های اجباری دریافت نشد")
                messages.error(request, 'لطفا تمام فیلدهای اجباری را پر کنید')
                return redirect('excel_manager:upload_bge_file')
            
            # بررسی نوع فایل
            file_extension = os.path.splitext(excel_file.name)[1].lower()
            if file_extension not in ['.xls', '.xlsx']:
                logger.warning(f"فرمت فایل نامعتبر: {file_extension}")
                messages.error(request, 'لطفا یک فایل اکسل معتبر (.xls یا .xlsx) آپلود کنید')
                return redirect('excel_manager:upload_bge_file')
            
            try:
                # بررسی و دریافت محصول
                try:
                    cargo_product = CargoProduct.objects.get(id=cargo_id)
                    logger.debug(f"محصول یافت شد: {cargo_product}")
                except CargoProduct.DoesNotExist:
                    logger.warning(f"محصولی با شناسه {cargo_id} یافت نشد")
                    messages.error(request, f'محصولی با شناسه {cargo_id} یافت نشد')
                    return redirect('excel_manager:upload_bge_file')
                
                # بررسی تطابق کوتاژ محصول با کوتاژ داخل فایل اکسل
                # ذخیره موقت فایل
                temp_file_path = os.path.join(settings.MEDIA_ROOT, f'temp_excel{file_extension}')
                with open(temp_file_path, 'wb+') as destination:
                    for chunk in excel_file.chunks():
                        destination.write(chunk)
                
                # خواندن محتوای فایل اکسل
                try:
                    # خواندن محتوای فایل اکسل با توجه به نوع آن
                    if file_extension == '.xls':
                        try:
                            # ابتدا تلاش برای خواندن به عنوان HTML
                            with open(temp_file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            if '<html' in content.lower():
                                # این فایل xls حاوی HTML است
                                tables = pd.read_html(content)
                                if not tables:
                                    logger.warning(f"جدولی در فایل اکسل یافت نشد")
                                    messages.error(request, 'جدولی در فایل اکسل یافت نشد')
                                    os.remove(temp_file_path)  # حذف فایل موقت
                                    return redirect('excel_manager:upload_bge_file')
                                df = tables[0]
                            else:
                                # این یک فایل xls معمولی است
                                df = pd.read_excel(temp_file_path)
                                # بررسی و پیدا کردن ردیف header
                                df = fix_excel_headers(df)
                        except UnicodeDecodeError:
                            # این یک فایل باینری است، نه فایل متنی
                            df = pd.read_excel(temp_file_path)
                            # بررسی و پیدا کردن ردیف header
                            df = fix_excel_headers(df)
                    else:  # فایل xlsx
                        df = pd.read_excel(temp_file_path)
                        # بررسی و پیدا کردن ردیف header
                        df = fix_excel_headers(df)
                
                except Exception as e:
                    logger.error(f"خطا در خواندن فایل اکسل: {str(e)}")
                    messages.error(request, f'خطا در خواندن فایل اکسل: {str(e)}')
                    os.remove(temp_file_path)  # حذف فایل موقت
                    return redirect('excel_manager:upload_bge_file')
                
                # بررسی وجود ستون کد کوتاژ
                cottage_column = None
                for column_name in ['کد کوتاژ', 'کوتاژ']:
                    if column_name in df.columns:
                        cottage_column = column_name
                        break
                
                if not cottage_column:
                    logger.warning(f"ستون کد کوتاژ در فایل یافت نشد")
                    messages.error(request, 'ستون کد کوتاژ در فایل یافت نشد')
                    os.remove(temp_file_path)  # حذف فایل موقت
                    return redirect('excel_manager:upload_bge_file')
                
                # بررسی مقادیر کوتاژ در هر ردیف
                cottage_mismatch = False
                mismatched_cottages = []
                
                for idx, row in df.iterrows():
                    if pd.notna(row[cottage_column]):
                        file_cottage = str(row[cottage_column]).strip()
                        # اگر کوتاژ فایل با کوتاژ محصول متفاوت باشد
                        if file_cottage != cargo_product.cottage:
                            cottage_mismatch = True
                            mismatched_cottages.append(file_cottage)
                
                # اگر کوتاژها مطابقت نداشته باشند و آپلود اجباری نباشد، هشدار نمایش بده
                if cottage_mismatch and not force_upload:
                    unique_cottages = list(set(mismatched_cottages))
                    logger.warning(f"کوتاژ محصول ({cargo_product.cottage}) با کوتاژ رکوردهای فایل مطابقت ندارد: {unique_cottages}")
                    
                    # فایل موقت را حذف کن
                    os.remove(temp_file_path)
                    
                    # پیام هشدار و درخواست تایید برای آپلود
                    context = {
                        'cargo_product': cargo_product,
                        'title': title,
                        'description': description,
                        'mismatched_cottages': unique_cottages[:10],  # نمایش حداکثر 10 کوتاژ متفاوت
                        'total_mismatched': len(unique_cottages),
                        'page_title': 'تایید آپلود فایل با کوتاژهای مختلف',
                    }
                    return render(request, 'excel_manager/confirm_upload_bge_file.html', context)
                
                # حذف فایل موقت
                os.remove(temp_file_path)
                
                # بررسی وجود پوشه‌های لازم
                media_dir = os.path.join(settings.BASE_DIR, 'media')
                excel_files_dir = os.path.join(media_dir, 'excel_files')
                for dir_path in [media_dir, excel_files_dir]:
                    if not os.path.exists(dir_path):
                        try:
                            os.makedirs(dir_path, exist_ok=True)
                            logger.debug(f"پوشه ایجاد شد: {dir_path}")
                        except Exception as e:
                            logger.error(f"خطا در ایجاد پوشه {dir_path}: {str(e)}")
                            messages.error(request, f'خطا در ایجاد پوشه: {str(e)}')
                            return redirect('excel_manager:upload_bge_file')
                
                # بررسی وجود فایل قبلی برای این محصول
                existing_file = BGExcelFile.objects.filter(cargo=cargo_product).first()
                
                file_obj = None
                if existing_file:
                    logger.debug(f"فایل قبلی یافت شد: {existing_file.id}")
                    # در صورت وجود فایل قبلی، آن را حذف می‌کنیم
                    old_file_path = existing_file.file.path if existing_file.file else None
                    if old_file_path and os.path.exists(old_file_path):
                        try:
                            os.remove(old_file_path)
                            logger.debug(f"فایل قبلی حذف شد: {old_file_path}")
                        except Exception as e:
                            logger.warning(f"خطا در حذف فایل قبلی: {str(e)}")
                    
                    # به‌روزرسانی رکورد موجود
                    existing_file.title = title
                    existing_file.description = description
                    existing_file.file = excel_file
                    existing_file.user = request.user
                    existing_file.is_processed = False
                    existing_file.is_approved = False
                    existing_file.save()
                    file_obj = existing_file
                    logger.debug(f"فایل قبلی به‌روزرسانی شد: {file_obj.id}")
                else:
                    logger.debug("ایجاد رکورد جدید")
                    # ایجاد رکورد جدید
                    file_obj = BGExcelFile.objects.create(
                        user=request.user,
                        cargo=cargo_product,
                        title=title,
                        file=excel_file,
                        description=description
                    )
                    logger.debug(f"رکورد جدید ایجاد شد: {file_obj.id}")
                
                if not file_obj:
                    logger.error("خطا: شیء فایل ایجاد نشد")
                    messages.error(request, 'خطا در ذخیره فایل')
                    return redirect('excel_manager:upload_bge_file')
                
                # اطمینان از ذخیره فایل
                if not file_obj.file or not hasattr(file_obj.file, 'path'):
                    logger.error("خطا: فایل به درستی ذخیره نشده است")
                    messages.error(request, 'خطا در ذخیره فایل')
                    return redirect('excel_manager:upload_bge_file')
                
                # تغییر نام فایل به فرمت مناسب
                try:
                    new_filename = f"BGE_{cargo_product.cottage}_{cargo_product.get_product_type_display()}{file_extension}"
                    rename_result = file_obj.change_file_name(new_filename)
                    if rename_result:
                        logger.debug(f"نام فایل تغییر یافت به: {new_filename}")
                    else:
                        logger.warning(f"تغییر نام فایل انجام نشد، اما فایل در دیتابیس ذخیره شده است")
                except Exception as rename_error:
                    logger.error(f"خطا در تغییر نام فایل: {str(rename_error)}")
                    # حتی اگر تغییر نام با خطا مواجه شود، فایل در دیتابیس ذخیره شده است
                
                # پیام موفقیت
                messages.success(request, 'فایل با موفقیت آپلود شد. اکنون می‌توانید آن را پردازش کنید.')
                return redirect('excel_manager:bge_files_list')
                
            except Exception as e:
                logger.error(f"خطا در آپلود فایل: {str(e)}")
                messages.error(request, f'خطا در آپلود فایل: {str(e)}')
                return redirect('excel_manager:upload_bge_file')
                
        except Exception as e:
            logger.error(f"خطای کلی در آپلود فایل: {str(e)}")
            messages.error(request, f'خطای کلی در آپلود فایل: {str(e)}')
            return redirect('excel_manager:upload_bge_file')
    
    # دریافت لیست محصولات برای انتخاب
    cargo_products = CargoProduct.objects.all().order_by('-cottage')
    logger.debug(f"تعداد محصولات برای نمایش: {len(cargo_products)}")
    
    context = {
        'cargo_products': cargo_products,
        'page_title': 'آپلود فایل اکسل بازارگاه',
    }
    return render(request, 'excel_manager/upload_bge_file.html', context)


@login_required
def search_cargo_products(request):
    """
    جستجوی محصولات برای API
    """
    query = request.GET.get('q', '')
    if not query:
        return JsonResponse({'results': []})
    
    # جستجو در کوتاژ و نوع محصول
    cargo_products = CargoProduct.objects.filter(
        cottage__icontains=query
    )[:10]  # محدود کردن نتایج به 10 مورد
    
    results = []
    for product in cargo_products:
        results.append({
            'id': product.id,  # استفاده از شناسه محصول
            'text': f"کوتاژ {product.cottage} - {product.get_product_type_display()}"
        })
    
    return JsonResponse({'results': results})


@login_required
def process_bge_file(request, file_id):
    """
    پردازش فایل اکسل بازارگاه و به‌روزرسانی رکوردهای Purchase
    """
    bge_file = get_object_or_404(BGExcelFile, id=file_id)
    
    if request.method == 'POST':
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
                                messages.error(request, 'جدولی در فایل اکسل یافت نشد.')
                                processing_log.log_message = "جدولی در فایل اکسل یافت نشد."
                                processing_log.save()
                                return redirect('excel_manager:bge_files_list')
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
                
                # بررسی وجود ستون‌های ضروری
                required_columns = ['کد', 'شناسه تخصیص', 'وزن کل خرید', 'کد ملی تحویل', 'شماره هماهنگی تحویل', 'شماره همراه خریدار', 
                                    'نام خریدار', 'آدرس تحویل', 'مبلغ پرداختی', 'شیوه پرداخت']
                
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
                    messages.error(request, error_msg)
                    processing_log.log_message = error_msg
                    processing_log.save()
                    return redirect('excel_manager:bge_files_list')
                
                # بررسی اینکه آیا ستون‌های مورد نیاز در دیتافریم وجود دارند
                missing_columns = [col for col in required_columns if col not in df.columns]
                if missing_columns:
                    error_msg = f"ستون‌های زیر در فایل اکسل یافت نشد: {', '.join(missing_columns)}"
                    logger.error(error_msg)
                    messages.error(request, error_msg)
                    processing_log.log_message = error_msg
                    processing_log.save()
                    return redirect('excel_manager:bge_files_list')
                
                # لیست رکوردهایی که باید از اکسل حذف شوند
                rows_to_remove = []
                
                # تعریف کاربر superuser برای تخصیص به مشتریان جدید
                super_user = User.objects.filter(is_superuser=True).first()
                super_agent = None
                if super_user and hasattr(super_user, 'sales_agent'):
                    super_agent = super_user.sales_agent
                
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
                        weight = int(float(row['وزن کل خرید'])) if pd.notna(row['وزن کل خرید']) else 0
                        amount_paid = int(float(row['مبلغ پرداختی'])) if pd.notna(row['مبلغ پرداختی']) else None
                        payment_method = 'نقدی' if pd.notna(row['شیوه پرداخت']) and row['شیوه پرداخت'] == 'نقدی' else 'توافقی'
                        
                        # استخراج کوتاژ از فایل
                        current_cottage = str(row[cottage_column]).strip() if pd.notna(row[cottage_column]) else None
                        
                        # نرمالایز کردن شماره تلفن
                        if bazaargah_phone_number:
                            bazaargah_phone_number = re.sub(r'\D', '', bazaargah_phone_number)
                            if bazaargah_phone_number.startswith('0'):
                                bazaargah_phone_number = bazaargah_phone_number[1:]
                            elif bazaargah_phone_number.startswith('98'):
                                bazaargah_phone_number = bazaargah_phone_number[2:]
                        
                        if tahvil_phone_number:
                            tahvil_phone_number = re.sub(r'\D', '', tahvil_phone_number)
                            if tahvil_phone_number.startswith('0'):
                                tahvil_phone_number = tahvil_phone_number[1:]
                            elif tahvil_phone_number.startswith('98'):
                                tahvil_phone_number = tahvil_phone_number[2:]
                        
                        # بررسی وجود خرید با شماره خرید مشابه
                        purchase = Purchase.objects.filter(purchase_number=purchase_number).first()
                        
                        # بررسی قبلاً ثبت شدن شناسه تخصیص
                        existing_shenase = ShenaseTakhsis.objects.filter(code=shenase_takhsis).exists() if shenase_takhsis else False
                        if existing_shenase:
                            rows_to_remove.append(idx)
                            continue
                        
                        # تعیین محصول (CargoProduct) براساس کوتاژ
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
                                            product_type = None
                                            
                                            # بررسی وجود ستون "عنوان کالا" یا مشابه آن
                                            product_name_column = None
                                            for column in ['عنوان کالا', 'نام کالا', 'محصول', 'کالا']:
                                                if column in df.columns:
                                                    product_name_column = column
                                                    break
                                            
                                            if product_name_column and pd.notna(row[product_name_column]):
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
                                            
                                            # اگر نوع محصول از فایل تشخیص داده نشد، از محصول موجود استفاده کن
                                            if not product_type:
                                                product_type = bge_file.cargo.product_type
                                                logger.info(f"نوع محصول از فایل تشخیص داده نشد، استفاده از نوع محصول {bge_file.cargo.get_product_type_display()}")
                                            
                                            # تعیین قیمت خرید و فروش
                                            company_price = 0
                                            customer_price = 0
                                            
                                            # تلاش برای استخراج قیمت از فایل
                                            if 'قیمت هر واحد' in df.columns and pd.notna(row['قیمت هر واحد']):
                                                try:
                                                    price_per_unit = int(float(row['قیمت هر واحد']))
                                                    company_price = price_per_unit
                                                    customer_price = price_per_unit
                                                except (ValueError, TypeError):
                                                    # اگر تبدیل به عدد با خطا مواجه شد، از مقادیر محصول اصلی استفاده کن
                                                    logger.warning(f"قیمت در فایل با فرمت نامعتبر: {row['قیمت هر واحد']}")
                                            
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
                                                weight=bge_file.cargo.weight,  # وزن مشابه
                                                status=True  # فعال
                                            )
                                            cargo_products_created += 1
                                            created_cargo_products[current_cottage] = new_cargo_product
                                            cargo_product = new_cargo_product
                                            logger.info(f"محصول جدید با کوتاژ {current_cottage} و نوع {cargo_product.get_product_type_display()} ایجاد شد")
                                    except Exception as ce:
                                        logger.error(f"خطا در ایجاد محصول جدید با کوتاژ {current_cottage}: {str(ce)}")
                                        error_messages.append(f"خطا در ایجاد محصول با کوتاژ {current_cottage}: {str(ce)}")
                                        records_failed += 1
                                        continue
                        
                        # اگر هنوز محصول تعیین نشده، از محصول فعلی استفاده می‌کنیم
                        if not cargo_product:
                            cargo_product = bge_file.cargo
                        
                        # هر پردازش در یک بلاک atomic جداگانه انجام می‌شود
                        with transaction.atomic():
                            if purchase:
                                try:
                                    # به‌روزرسانی خرید موجود - استفاده از update به جای save برای دور زدن validation
                                    Purchase.objects.filter(id=purchase.id).update(
                                        code_melli_tahvil=code_melli_tahvil,
                                        tahvil_phone_number=tahvil_phone_number,
                                        bazaargah_phone_number=bazaargah_phone_number,
                                        address=address,
                                        weight=weight,
                                        cargo=cargo_product,
                                        amount_paid=amount_paid,
                                        payment_method=payment_method,
                                        is_takhsised=True if shenase_takhsis else purchase.is_takhsised
                                    )
                                    
                                    # افزودن شناسه تخصیص جدید به خرید
                                    if shenase_takhsis and not ShenaseTakhsis.objects.filter(purchase=purchase, code=shenase_takhsis).exists():
                                        ShenaseTakhsis.objects.create(
                                            purchase=purchase,
                                            code=shenase_takhsis
                                        )
                                        
                                    records_updated += 1
                                except Exception as e:
                                    records_failed += 1
                                    error_messages.append(f"خطا در به‌روزرسانی خرید {purchase_number}: {str(e)}")
                                    logger.error(f"خطا در به‌روزرسانی خرید {purchase_number}: {str(e)}")
                                    raise
                            else:
                                # ایجاد مشتری جدید اگر وجود ندارد
                                customer = None
                                try:
                                    if bazaargah_phone_number:
                                        customer = Customer.objects.filter(phone_number=bazaargah_phone_number).first()
                                        if not customer:
                                            try:
                                                # استخراج زمینه فعالیت بر اساس اکسل:
                                                field_of_activity_raw = None
                                                for fieldname in ['نوع کاربری خریدار', 'زمینه فعالیت', 'حیطه فعالیت']:
                                                    if fieldname in row and pd.notna(row[fieldname]):
                                                        field_of_activity_raw = str(row[fieldname]).strip()
                                                        break

                                                field_of_activity = map_excel_field_to_model(field_of_activity_raw)

                                                customer = Customer.objects.create(
                                                    phone_number=bazaargah_phone_number,
                                                    name=customer_name if customer_name else "مشتری جدید",
                                                    field_of_activity=field_of_activity if field_of_activity else 'chicken',
                                                    sms_preference=True,
                                                    is_bazaargah_enjoyer=True
                                                )

                                                logger.debug(f"مشتری جدید ایجاد شد با شناسه: {customer.id}")
                                                # اضافه کردن کارشناس فروش
                                                if super_agent:
                                                    customer.sales_agent.add(super_agent)
                                            except Exception as ce:
                                                logger.error(f"خطا در ایجاد مشتری با ORM: {str(ce)}", exc_info=True)
                                                raise 

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
                                                code_melli_tahvil=code_melli_tahvil,
                                                tahvil_phone_number=tahvil_phone_number,
                                                bazaargah_phone_number=bazaargah_phone_number,
                                                address=address,
                                                weight=weight,
                                                cargo=cargo_product,
                                                amount_paid=amount_paid,
                                                payment_method=payment_method,
                                                type='bazaargah',
                                                is_bazaargahed=True,
                                                is_takhsised=True if shenase_takhsis else False,
                                                company_price=cargo_product.company_price,
                                                customer_price=cargo_product.customer_price,
                                                # Boolean fields
                                                is_sms_sent=True,
                                                is_paid=True,
                                                is_weight_costed=True,
                                                is_ap_af=False,
                                                is_archived=False,
                                                is_canceled=False,
                                                is_urgent=False,
                                                is_delivered=True,
                                                is_sent=True,
                                                is_sent_to_barbari=True,
                                                is_barnamed=True,
                                                is_takhsised_approved=True,
                                                is_tasvied_with_varedkonandeh=True,
                                                is_address_sent_to_varedkonandeh=True,
                                                is_ekhtelaf_approved=True,
                                                is_kasri_varized=True,
                                                is_sarak_varized=True,
                                                is_kasri_reciept_submited=True,
                                                is_factorated=True,
                                                does_salesman_approve=True,
                                                does_logistics_approve=True,
                                                does_financial_approve=True,
                                                description=""
                                            )
                                            
                                            # Bypass validation when saving
                                            new_purchase.save(force_insert=True)
                                            logger.debug(f"خرید جدید با موفقیت ایجاد شد: {purchase_id}")
                                            
                                            # افزودن شناسه تخصیص به خرید جدید
                                            if shenase_takhsis:
                                                ShenaseTakhsis.objects.create(
                                                    purchase=new_purchase,
                                                    code=shenase_takhsis
                                                )
                                                
                                            records_created += 1
                                        except Exception as e:
                                            logger.error(f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}")
                                            raise
                                    else:
                                        logger.error(f"ایجاد مشتری با شماره {bazaargah_phone_number} ناموفق بود")
                                        records_failed += 1
                                        error_messages.append(f"خطا در ایجاد مشتری برای خرید {purchase_number}: مشتری ایجاد نشد")
                                except Exception as e:
                                    records_failed += 1
                                    error_messages.append(f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}")
                                    logger.error(f"خطا در ایجاد خرید جدید {purchase_number}: {str(e)}", exc_info=True)
                    except Exception as e:
                        records_failed += 1
                        error_messages.append(f"خطا در پردازش رکورد {idx+1}: {str(e)}")
                        logger.error(f"خطا در پردازش رکورد {idx+1}: {str(e)}")
                
                # حذف رکوردهای با شناسه تخصیص تکراری
                if rows_to_remove:
                    df = df.drop(rows_to_remove).reset_index(drop=True)
                
                # ذخیره فایل اکسل تمیز شده
                cleaned_filename = f"cleaned_{os.path.basename(file_path)}"
                cleaned_file_path = os.path.join(os.path.dirname(file_path), cleaned_filename)
                
                # ذخیره فایل بر اساس نوع آن
                if file_extension == '.xls' and '<html' in content.lower():
                    # بازسازی فایل HTML
                    html_content = """<html><head><meta http-equiv=Content-Type content='text/html; charset=utf-8'><style> .text { mso-number-format:\\@; } .trFormat{color:Black;background-color:#DEDFDE;}</style></head>"""
                    html_content += """<div style="direction:rtl;padding:5px 0"><span style="font:bold 12px tahoma; color:#008B00;line-height:180%"> ثبت اطلاعات حمل</span></div>"""
                    
                    # تبدیل پاندس به HTML و ذخیره
                    table_html = df.to_html(index=False, border=1, classes='table')
                    table_html = table_html.replace('<table', '<table dir="rtl" cellspacing="0" cellpadding="7" style="font-family:Tahoma;font-size:11px;width:70%;"')
                    
                    # جایگزین کردن عناوین ردیف اول با استایل مناسب
                    thead_html = """<thead><tr style='color:#E7E7FF;background-color:#4A3C8C;font-weight:bold;'>"""
                    for col in df.columns:
                        thead_html += f"<th>{col}</th>"
                    thead_html += "</tr></thead>"
                    
                    table_html = re.sub(r'<thead>.*?</thead>', thead_html, table_html, flags=re.DOTALL)
                    
                    # ایجاد استایل برای ردیف‌های داده
                    table_html = table_html.replace('<tr>', '<tr class="trFormat">')
                    table_html = table_html.replace('<td>', '<td align="center">')
                    
                    html_content += table_html + "</html>"
                    
                    with open(cleaned_file_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                else:
                    # ذخیره به عنوان فایل اکسل
                    df.to_excel(cleaned_file_path, index=False)
                
                # به‌روزرسانی لاگ پردازش
                processing_log.success = records_failed == 0
                processing_log.records_processed = records_processed
                processing_log.records_updated = records_updated
                processing_log.records_failed = records_failed
                log_message = f"تعداد کل رکوردها: {records_processed}\n"
                log_message += f"تعداد رکوردهای به‌روزرسانی شده: {records_updated}\n"
                log_message += f"تعداد رکوردهای ایجاد شده: {records_created}\n"
                log_message += f"تعداد محصولات ایجاد شده: {cargo_products_created}\n"
                log_message += f"تعداد رکوردهای ناموفق: {records_failed}\n"
                
                if error_messages:
                    log_message += "خطاها:\n" + "\n".join(error_messages)
                
                processing_log.log_message = log_message
                processing_log.save()
                
                # به‌روزرسانی وضعیت فایل
                bge_file.is_processed = True
                bge_file.save()
                
                success_message = f"فایل با موفقیت پردازش شد. {records_updated} رکورد به‌روزرسانی شد و {records_created} رکورد جدید ایجاد شد."
                if cargo_products_created > 0:
                    success_message += f" همچنین {cargo_products_created} محصول جدید براساس کوتاژهای موجود در فایل ایجاد شد."
                
                messages.success(request, success_message)
                return redirect('excel_manager:bge_files_list')
                
            except Exception as e:
                logger.error(f"خطا در پردازش فایل: {str(e)}")
                processing_log.log_message = f"خطا در پردازش فایل: {str(e)}"
                processing_log.save()
                messages.error(request, f'خطا در پردازش فایل: {str(e)}')
                return redirect('excel_manager:bge_files_list')
                
        except Exception as e:
            logger.error(f"خطای کلی در پردازش فایل: {str(e)}")
            messages.error(request, f'خطای کلی در پردازش فایل: {str(e)}')
            return redirect('excel_manager:bge_files_list')
    
    # نمایش جزئیات فایل برای پردازش
    context = {
        'bge_file': bge_file,
        'page_title': 'پردازش فایل اکسل بازارگاه',
    }
    return render(request, 'excel_manager/process_bge_file.html', context)


def get_excel_columns(file_path):
    """نمایش ستون‌های موجود در فایل اکسل"""
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
    تابعی برای تشخیص و اصلاح سربرگ‌های فایل اکسل.
    در برخی فایل‌ها، سربرگ‌ها در ردیف اول یا دوم قرار دارند.
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
    نگاشت نوع کاربری اکسل به فیلد مدل
    این نگاشت را بسته به دیتا اکسل خود کامل و اصلاح کن
    """
    # اگر مقدار None یا تهی بود
    if not field_value or not isinstance(field_value, str):
        return 'chicken'  # مقدار پیش‌فرض

    field_value = field_value.strip()
    FIELD_MAP = {
        'مرغداری': 'chicken',
        'دامداری': 'livestock',
        'گاوداری': 'livestock',
        'تولیدی مرغ': 'chicken',
        'تعاونی': 'corporation', # یا بر اساس دیتا واقعی؛ ممکن است نیازمند تفکیک دقیق‌تر باشد!
        'دلال': 'trader',
        'بازرگان': 'trader',
        'کارخانه': 'factory',
        'کارخانه خوراک': 'factory',
        'آبزی': 'fish',
        'پرورش آبزیان': 'fish',
        'ماهی': 'fish',
    }
    for k, v in FIELD_MAP.items():
        if k in field_value:
            return v
    # اگر پیدا نشد
    return 'chicken'