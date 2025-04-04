import os
import pandas as pd
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib import messages
from ..models import ExcelFile, BGExcelFile, ExcelProcessingLog
from core._models import CargoProduct, Purchase
from django.conf import settings
from django.db import transaction

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
            
            logger.debug(f"داده‌های دریافتی: cargo_id={cargo_id}, title={title}, excel_file={excel_file}")
            
            # بررسی داده‌های اجباری
            if not cargo_id or not title or not excel_file:
                logger.warning("داده‌های اجباری دریافت نشد")
                messages.error(request, 'لطفا تمام فیلدهای اجباری را پر کنید')
                return redirect('excel_manager:upload_bge_file')
            
            # بررسی نوع فایل
            file_extension = os.path.splitext(excel_file.name)[1].lower()
            if file_extension != '.xls':
                logger.warning(f"فرمت فایل نامعتبر: {file_extension}")
                messages.error(request, 'لطفا یک فایل اکسل معتبر (.xls) آپلود کنید')
                return redirect('excel_manager:upload_bge_file')
            
            # بررسی محتوای فایل
            try:
                # اول سعی می‌کنیم با pandas read_html بخونیم
                logger.debug("تلاش برای خواندن با pandas read_html")
                content = excel_file.read().decode('utf-8')
                excel_file.seek(0)  # برگرداندن اشاره‌گر فایل به ابتدا
                
                if '<html' in content.lower():
                    logger.debug("فایل HTML شناسایی شد")
                    # خواندن اولین جدول از فایل HTML بدون تعیین header
                    df = pd.read_html(content)[0]
                    
                    # پیدا کردن ردیف header (معمولاً ردیفی که شامل "کد" یا "شناسه تخصیص" است)
                    header_row = None
                    for idx, row in df.iterrows():
                        # بررسی اینکه آیا این سطر شامل "ثبت اطلاعات حمل" است
                        if any('ثبت اطلاعات حمل' in str(val) for val in row.values):
                            continue
                        if any(col in str(row.values) for col in ['کد', 'شناسه تخصیص']):
                            header_row = idx
                            break
                    
                    if header_row is not None:
                        # تنظیم ستون‌های جدید
                        df.columns = df.iloc[header_row]
                        # حذف ردیف‌های اضافی و سطر اول که شامل "ثبت اطلاعات حمل" است
                        df = df.iloc[header_row + 1:].reset_index(drop=True)
                    
                    logger.debug(f"ستون‌های شناسایی شده: {df.columns.tolist()}")
                else:
                    # اگر HTML نبود، با xlrd امتحان می‌کنیم
                    logger.debug("تلاش برای خواندن با xlrd")
                    import xlrd
                    wb = xlrd.open_workbook(file_contents=excel_file.read())
                    excel_file.seek(0)
                
                if len(df.columns) == 0:
                    raise ValueError("فایل خالی است یا ساختار معتبری ندارد")
                    
                logger.debug(f"فایل با موفقیت خوانده شد. تعداد ستون‌ها: {len(df.columns)}")
                logger.debug(f"ستون‌های موجود: {df.columns.tolist()}")
                
                # تمیز کردن نام ستون‌ها
                df.columns = df.columns.str.strip()
                
                # بررسی و تصحیح نام ستون‌ها
                column_corrections = {
                    'کد': 'کد خرید',
                    'شماره خرید': 'کد خرید',
                    'شماره خرید بازارگاه': 'کد خرید',
                    'شناسه': 'شناسه تخصیص'
                }
                
                df = df.rename(columns=column_corrections)
                
            except Exception as e:
                logger.error(f"خطا در خواندن فایل: {str(e)}")
                messages.error(request, f'خطا در خواندن فایل: {str(e)}')
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
                    new_filename = f"BGE_{cargo_product.cottage}_{cargo_product.get_product_type_display()}.xls"
                    rename_result = file_obj.change_file_name(new_filename)
                    if rename_result:
                        logger.debug(f"نام فایل تغییر یافت به: {new_filename}")
                    else:
                        logger.warning(f"تغییر نام فایل انجام نشد، اما فایل در دیتابیس ذخیره شده است")
                except Exception as rename_error:
                    logger.error(f"خطا در تغییر نام فایل: {str(rename_error)}")
                    # حتی اگر تغییر نام با خطا مواجه شود، فایل در دیتابیس ذخیره شده است
                
                # ارسال پیام موفقیت و هدایت به صفحه لیست
                messages.success(request, 'فایل اکسل بازارگاه با موفقیت آپلود شد')
                return redirect('excel_manager:bge_files_list')
                
            except Exception as e:
                logger.error(f"خطا در آپلود فایل: {str(e)}", exc_info=True)
                messages.error(request, f'خطا در آپلود فایل: {str(e)}')
                return redirect('excel_manager:upload_bge_file')
        
        except Exception as e:
            logger.error(f"خطا در دریافت داده‌های فرم: {str(e)}", exc_info=True)
            messages.error(request, f'خطا در دریافت داده‌های فرم: {str(e)}')
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
def process_bge_file(request, file_id):
    """
    پردازش فایل اکسل بازارگاه و به‌روزرسانی رکوردهای Purchase
    """
    bge_file = get_object_or_404(BGExcelFile, id=file_id)
    
    if request.method == 'POST':
        try:
            # بررسی وجود فایل
            file_path = bge_file.file.path
            if not os.path.exists(file_path):
                logger.error(f"فایل در مسیر {file_path} وجود ندارد")
                return JsonResponse({
                    'status': 'error',
                    'message': 'فایل مورد نظر در سرور یافت نشد'
                }, status=404)
            
            # بررسی نوع فایل
            file_extension = os.path.splitext(file_path)[1].lower()
            logger.debug(f"پسوند فایل: {file_extension}")
            logger.debug(f"اندازه فایل: {os.path.getsize(file_path)} بایت")
            
            try:
                # اول سعی می‌کنیم با pandas read_html بخونیم
                logger.debug("تلاش برای خواندن با pandas read_html")
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '<html' in content.lower():
                    logger.debug("فایل HTML شناسایی شد")
                    # خواندن اولین جدول از فایل HTML بدون تعیین header
                    df = pd.read_html(content)[0]
                    
                    # پیدا کردن ردیف header (معمولاً ردیفی که شامل "کد" یا "شناسه تخصیص" است)
                    header_row = None
                    for idx, row in df.iterrows():
                        # بررسی اینکه آیا این سطر شامل "ثبت اطلاعات حمل" است
                        if any('ثبت اطلاعات حمل' in str(val) for val in row.values):
                            continue
                        if any(col in str(row.values) for col in ['کد', 'شناسه تخصیص']):
                            header_row = idx
                            break
                    
                    if header_row is not None:
                        # تنظیم ستون‌های جدید
                        df.columns = df.iloc[header_row]
                        # حذف ردیف‌های اضافی و سطر اول که شامل "ثبت اطلاعات حمل" است
                        df = df.iloc[header_row + 1:].reset_index(drop=True)
                    
                    logger.debug(f"ستون‌های شناسایی شده: {df.columns.tolist()}")
                else:
                    # اگر HTML نبود، با xlrd امتحان می‌کنیم
                    logger.debug("تلاش برای خواندن با xlrd")
                    import xlrd
                    wb = xlrd.open_workbook(file_path)
                    df = pd.read_excel(file_path, engine='xlrd', header=1)
                
                # بررسی ساختار فایل
                if len(df.columns) == 0:
                    raise ValueError("فایل خالی است یا ساختار معتبری ندارد")
                    
                logger.debug(f"فایل با موفقیت خوانده شد. تعداد ستون‌ها: {len(df.columns)}")
                logger.debug(f"ستون‌های موجود: {df.columns.tolist()}")
                
                # تمیز کردن نام ستون‌ها
                df.columns = df.columns.str.strip()
                
                # بررسی و تصحیح نام ستون‌ها
                column_corrections = {
                    'کد': 'کد خرید',
                    'شماره خرید': 'کد خرید',
                    'شماره خرید بازارگاه': 'کد خرید',
                    'شناسه': 'شناسه تخصیص'
                }
                
                df = df.rename(columns=column_corrections)
                
            except Exception as e:
                logger.error(f"خطا در خواندن فایل: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در خواندن فایل: {str(e)}'
                }, status=500)
            
            # بررسی موفقیت خواندن فایل
            if df is None or len(df) == 0:
                logger.error("فایل اکسل خالی است یا به درستی خوانده نشده است")
                return JsonResponse({
                    'status': 'error',
                    'message': 'فایل اکسل خالی است یا ساختار معتبری ندارد'
                }, status=400)
            
            logger.debug(f"فایل با موفقیت خوانده شد. تعداد سطرها: {len(df)}")
            logger.debug(f"ستون‌های موجود: {df.columns.tolist()}")
            
            # اگر ستون 'کد' وجود دارد ولی 'کد خرید' وجود ندارد، آن را تغییر نام دهیم
            if 'کد' in df.columns and 'کد خرید' not in df.columns:
                logger.debug("تغییر نام ستون 'کد' به 'کد خرید'")
                df = df.rename(columns={'کد': 'کد خرید'})
                logger.debug(f"ستون‌ها پس از تغییر نام: {df.columns.tolist()}")
            
            # بررسی وجود ستون‌های مورد نیاز
            required_columns = ['شناسه تخصیص', 'کد خرید']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                missing_cols_str = ', '.join(missing_columns)
                error_message = f"ستون‌های ضروری در فایل وجود ندارند: {missing_cols_str}"
                logger.error(error_message)
                return JsonResponse({
                    'status': 'error',
                    'message': error_message
                }, status=400)
            
            # متغیرهای ثبت گزارش
            records_processed = len(df)
            records_updated = 0
            records_failed = 0
            success = True
            log_messages = []
            
            # ۱. حذف رکوردهای تکراری شناسه تخصیص
            if 'شناسه تخصیص' in df.columns:
                initial_records = len(df)
                df.drop_duplicates(subset=['شناسه تخصیص'], keep='first', inplace=True)
                duplicate_removed = initial_records - len(df)
                if duplicate_removed > 0:
                    log_messages.append(f"{duplicate_removed} رکورد تکراری حذف شد")
            
            # ۲. پردازش و به‌روزرسانی Purchase
            try:
                # نگاشت نام ستون‌های فایل اکسل به فیلدهای مدل
                column_mapping = {
                    'شناسه تخصیص': 'shenase_takhsis',
                    'کد خرید': 'purchase_number',
                    'کد': 'purchase_number',  # اضافه کردن 'کد' به عنوان معادل 'کد خرید'
                    'کد ملی تحویل': 'code_melli_tahvil',
                    'شماره همراه خریدار': 'bazaargah_phone_number',
                    'شماره هماهنگی تحویل': 'tahvil_phone_number',
                    'آدرس تحویل': 'address'
                }
                
                # تبدیل ستون‌ها به نام‌های فیلدهای مدل
                df_renamed = df.rename(columns=column_mapping, errors='ignore')
                
                # فیلدهای موجود در دیتافریم که با مدل مطابقت دارند
                model_fields = set(column_mapping.values())
                available_fields = set(df_renamed.columns).intersection(model_fields)
                
                # عملیات بروزرسانی
                with transaction.atomic():
                    # اول، پاکسازی رکوردهای قدیمی که شناسه تخصیص دارند
                    existing_shenase_takhsis = [str(row['shenase_takhsis']).strip() 
                                             for _, row in df_renamed.iterrows() 
                                             if 'shenase_takhsis' in row and not pd.isna(row['shenase_takhsis'])]
                    Purchase.objects.filter(shenase_takhsis__in=existing_shenase_takhsis).delete()
                    
                    for _, row in df_renamed.iterrows():
                        try:
                            # بررسی وجود کد خرید
                            if 'purchase_number' not in available_fields or pd.isna(row.get('purchase_number')):
                                records_failed += 1
                                continue
                                
                            purchase_number = str(row['purchase_number']).strip()
                            shenase_takhsis = str(row['shenase_takhsis']).strip() if 'shenase_takhsis' in available_fields and not pd.isna(row.get('shenase_takhsis')) else None
                            
                            # جستجوی رکورد خرید بر اساس شماره خرید
                            purchase = None
                            if purchase_number:
                                try:
                                    purchase = Purchase.objects.get(purchase_number=purchase_number)
                                except Purchase.DoesNotExist:
                                    # اگر رکورد وجود نداشت، یک رکورد جدید ایجاد می‌کنیم
                                    purchase_data = {}
                                    for field in available_fields:
                                        if not pd.isna(row.get(field)):
                                            purchase_data[field] = str(row[field]).strip()
                                    
                                    purchase = Purchase.objects.create(**purchase_data)
                                    records_updated += 1
                                    continue
                            
                            if purchase:
                                updated = False
                                # بروزرسانی فیلدهای موجود
                                for field in available_fields:
                                    if not pd.isna(row.get(field)):
                                        field_value = str(row[field]).strip()
                                        if getattr(purchase, field) != field_value:
                                            setattr(purchase, field, field_value)
                                            updated = True
                                
                                # اگر به روزرسانی شده، تغییرات را ذخیره می‌کنیم
                                if updated:
                                    purchase.save()
                                    records_updated += 1
                            else:
                                records_failed += 1
                                
                        except Exception as e:
                            logger.error(f"خطا در پردازش رکورد: {str(e)}", exc_info=True)
                            records_failed += 1
            
            except Exception as e:
                logger.error(f"خطا در به‌روزرسانی دیتابیس: {str(e)}", exc_info=True)
                log_messages.append(f"خطا در به‌روزرسانی دیتابیس: {str(e)}")
                success = False
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در به‌روزرسانی دیتابیس: {str(e)}'
                }, status=500)
            
            # ۳. ایجاد و ذخیره فایل پردازش شده
            try:
                # خواندن محتوای HTML اصلی
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_html = f.read()
                
                # استخراج بخش‌های HTML
                html_parts = original_html.split('<table')
                header = html_parts[0]  # بخش قبل از جدول
                table_content = '<table' + html_parts[1]  # بخش جدول
                
                # تبدیل DataFrame به HTML
                df_html = df.to_html(index=False, classes='trFormat', border=1, justify='center')
                
                # جایگزینی محتوای جدول
                processed_html = header + df_html
                
                # ذخیره فایل HTML
                output_file_path = os.path.splitext(file_path)[0] + "_processed.xls"
                with open(output_file_path, 'w', encoding='utf-8') as f:
                    f.write(processed_html)
                
                # ذخیره فایل پردازش شده
                with open(output_file_path, 'rb') as f:
                    file_content = f.read()
                    file_name = os.path.basename(bge_file.file.name).replace(".xls", "_processed.xls")
                    bge_file.file.save(file_name, ContentFile(file_content), save=False)
                
                # بروزرسانی وضعیت فایل
                bge_file.is_processed = True
                bge_file.save()
                
                # ثبت گزارش پردازش
                log_message = "\n".join(log_messages)
                ExcelProcessingLog.objects.create(
                    excel_file=bge_file,
                    processed_by=request.user,
                    success=success,
                    records_processed=records_processed,
                    records_updated=records_updated,
                    records_failed=records_failed,
                    log_message=log_message
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'فایل اکسل بازارگاه با موفقیت پردازش شد',
                    'records_processed': records_processed,
                    'records_updated': records_updated,
                    'records_failed': records_failed
                })
                
            except Exception as e:
                logger.error(f"خطا در ایجاد فایل پردازش شده: {str(e)}", exc_info=True)
                
                # ثبت خطا در گزارش
                ExcelProcessingLog.objects.create(
                    excel_file=bge_file,
                    processed_by=request.user,
                    success=False,
                    records_processed=records_processed,
                    records_updated=records_updated,
                    records_failed=records_failed,
                    log_message=f"خطا در ایجاد فایل پردازش شده: {str(e)}\n" + "\n".join(log_messages)
                )
                
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در ایجاد فایل پردازش شده: {str(e)}'
                }, status=500)
            
        except Exception as e:
            # ثبت خطا در گزارش
            logger.error(f"خطا در پردازش فایل: {str(e)}", exc_info=True)
            
            ExcelProcessingLog.objects.create(
                excel_file=bge_file,
                processed_by=request.user,
                success=False,
                records_processed=0,
                records_updated=0,
                records_failed=0,
                log_message=f"خطا در پردازش فایل: {str(e)}"
            )
            
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در پردازش فایل: {str(e)}'
            }, status=500)
    
    # پاسخ به درخواست GET
    # دریافت داده‌های مورد نیاز برای صفحه
    cargo_product = bge_file.cargo
    
    context = {
        'bge_file': bge_file,
        'cargo_product': cargo_product,
        'page_title': f'پردازش فایل {bge_file.title}',
    }
    return render(request, 'excel_manager/process_bge_file.html', context)


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