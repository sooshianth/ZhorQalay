import os
import pandas as pd
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
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
                return JsonResponse({
                    'status': 'error',
                    'message': 'لطفا تمام فیلدهای اجباری را پر کنید'
                }, status=400)
            
            # بررسی نوع فایل
            file_extension = os.path.splitext(excel_file.name)[1].lower()
            if file_extension not in ['.xlsx', '.xls']:
                logger.warning(f"فرمت فایل نامعتبر: {file_extension}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'لطفا یک فایل اکسل معتبر (.xlsx یا .xls) آپلود کنید'
                }, status=400)
            
            try:
                # بررسی و دریافت محصول
                try:
                    cargo_product = CargoProduct.objects.get(id=cargo_id)
                    logger.debug(f"محصول یافت شد: {cargo_product}")
                except CargoProduct.DoesNotExist:
                    logger.warning(f"محصولی با شناسه {cargo_id} یافت نشد")
                    return JsonResponse({
                        'status': 'error',
                        'message': f'محصولی با شناسه {cargo_id} یافت نشد'
                    }, status=404)
                
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
                            return JsonResponse({
                                'status': 'error',
                                'message': f'خطا در ایجاد پوشه: {str(e)}'
                            }, status=500)
                
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
                    return JsonResponse({
                        'status': 'error',
                        'message': 'خطا در ذخیره فایل'
                    }, status=500)
                
                # اطمینان از ذخیره فایل
                if not file_obj.file or not hasattr(file_obj.file, 'path'):
                    logger.error("خطا: فایل به درستی ذخیره نشده است")
                    return JsonResponse({
                        'status': 'error',
                        'message': 'خطا در ذخیره فایل'
                    }, status=500)
                
                # تغییر نام فایل به فرمت مناسب
                try:
                    new_filename = f"BGE_{cargo_product.cottage}_{cargo_product.get_product_type_display()}.xlsx"
                    rename_result = file_obj.change_file_name(new_filename)
                    if rename_result:
                        logger.debug(f"نام فایل تغییر یافت به: {new_filename}")
                    else:
                        logger.warning(f"تغییر نام فایل انجام نشد، اما فایل در دیتابیس ذخیره شده است")
                except Exception as rename_error:
                    logger.error(f"خطا در تغییر نام فایل: {str(rename_error)}")
                    # حتی اگر تغییر نام با خطا مواجه شود، فایل در دیتابیس ذخیره شده است
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'فایل اکسل بازارگاه با موفقیت آپلود شد',
                    'file_id': file_obj.id
                })
                
            except Exception as e:
                logger.error(f"خطا در آپلود فایل: {str(e)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در آپلود فایل: {str(e)}'
                }, status=500)
        
        except Exception as e:
            logger.error(f"خطا در دریافت داده‌های فرم: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در دریافت داده‌های فرم: {str(e)}'
            }, status=500)
    
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
            # خواندن فایل اکسل
            file_path = bge_file.file.path
            
            # تعیین موتور پردازش براساس پسوند فایل
            file_extension = os.path.splitext(file_path)[1].lower()
            engine = 'openpyxl' if file_extension == '.xlsx' else 'xlrd'
                
            logger.debug(f"خواندن فایل اکسل با موتور {engine}: {file_path}")
            
            try:
                df = pd.read_excel(file_path, engine=engine)
                logger.debug(f"فایل با موفقیت خوانده شد. تعداد سطرها: {len(df)}")
                
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
            except Exception as excel_error:
                logger.error(f"خطا در خواندن فایل: {str(excel_error)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در خواندن فایل: {str(excel_error)}'
                }, status=500)
            
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
                    'کد ملی تحویل گیرنده': 'code_melli_tahvil',
                    'شماره همراه': 'bazaargah_phone_number',
                    'شماره تماس': 'tahvil_phone_number',
                    'آدرس': 'address'
                }
                
                # تبدیل ستون‌ها به نام‌های فیلدهای مدل
                df_renamed = df.rename(columns=column_mapping, errors='ignore')
                
                # فیلدهای موجود در دیتافریم که با مدل مطابقت دارند
                model_fields = set(column_mapping.values())
                available_fields = set(df_renamed.columns).intersection(model_fields)
                
                # عملیات بروزرسانی
                with transaction.atomic():
                    for _, row in df_renamed.iterrows():
                        try:
                            # بررسی وجود شناسه تخصیص
                            if 'shenase_takhsis' not in available_fields or pd.isna(row.get('shenase_takhsis')):
                                records_failed += 1
                                continue
                                
                            shenase_takhsis = str(row['shenase_takhsis']).strip()
                            
                            # جستجوی رکورد خرید بر اساس شناسه تخصیص
                            purchase = None
                            if shenase_takhsis:
                                try:
                                    purchase = Purchase.objects.get(shenase_takhsis=shenase_takhsis)
                                except Purchase.DoesNotExist:
                                    # اگر بر اساس شناسه تخصیص پیدا نشد، سعی می‌کنیم با شماره خرید پیدا کنیم
                                    if 'purchase_number' in available_fields and not pd.isna(row.get('purchase_number')):
                                        purchase_number = str(row['purchase_number']).strip()
                                        try:
                                            purchase = Purchase.objects.get(purchase_number=purchase_number)
                                        except Purchase.DoesNotExist:
                                            # خرید پیدا نشد
                                            records_failed += 1
                                            continue
                            
                            if purchase:
                                updated = False
                                # بروزرسانی فیلدهای موجود
                                for field in available_fields:
                                    if field == 'shenase_takhsis' and purchase.shenase_takhsis is not None:
                                        # اگر شناسه تخصیص قبلاً تنظیم شده، آن را تغییر نمی‌دهیم
                                        continue
                                        
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
                output_file_path = os.path.splitext(file_path)[0] + "_processed.xlsx"
                df.to_excel(output_file_path, index=False)
                
                # ذخیره فایل پردازش شده
                with open(output_file_path, 'rb') as f:
                    file_content = f.read()
                    file_name = os.path.basename(bge_file.file.name).replace(".xlsx", "_processed.xlsx").replace(".xls", "_processed.xlsx")
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