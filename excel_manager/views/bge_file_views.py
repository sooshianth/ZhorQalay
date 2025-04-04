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
from core.CustomerModel import Customer, FIELD_OF_ACTIVITY
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
                
                # نگاشت ستون‌ها
                column_mapping = {
                    'کد': 'purchase_number',
                    'کد خرید': 'purchase_number',
                    'شماره خرید': 'purchase_number',
                    'شماره خرید بازارگاه': 'purchase_number',
                    'وزن کل خرید': 'weight',
                    'قیمت هر واحد': 'company_price',
                    'شماره پیگیری': 'tracking_number',
                    'مبلغ پرداختی': 'amount_paid',
                    'توضیحات': 'description',
                    'شیوه پرداخت': 'payment_method',
                    'شناسه تخصیص': 'shenase_takhsis',
                    'شناسه': 'shenase_takhsis',
                    'نام خریدار': 'customer_name',
                    'شماره همراه خریدار': 'customer_phone',
                    'نوع کاربری خریدار': 'customer_type',
                    'شهرستان': 'city',
                    'کد ملی تحویل': 'code_melli_tahvil',
                    'شماره هماهنگی تحویل': 'tahvil_phone_number',
                    'آدرس تحویل': 'address',
                    'آدرس خریدار': 'address'
                }

                # تمیز کردن نام ستون‌ها
                df.columns = df.columns.str.strip()
                
                # نگاشت ستون‌ها
                df = df.rename(columns=column_mapping)
                
                logger.debug(f"ستون‌های شناسایی شده بعد از نگاشت: {df.columns.tolist()}")
                
                # متغیرهای ثبت گزارش
                records_processed = len(df)
                records_updated = 0
                records_failed = 0
                success = True
                log_messages = []
                
                # پردازش و به‌روزرسانی Purchase
                try:
                    with transaction.atomic():
                        for _, row in df.iterrows():
                            try:
                                # بررسی وجود کد خرید یا شناسه تخصیص
                                purchase_number = None
                                logger.debug(f"بررسی ستون‌های موجود در ردیف: {row.index}")
                                logger.debug(f"مقادیر ردیف: {row.to_dict()}")
                                
                                # بررسی ستون‌های نگاشت شده
                                if not pd.isna(row.get('purchase_number')):
                                    purchase_number = str(row['purchase_number']).strip()
                                    logger.debug(f"شماره خرید از ستون 'purchase_number': {purchase_number}")
                                elif not pd.isna(row.get('shenase_takhsis')):
                                    purchase_number = str(row['shenase_takhsis']).strip()
                                    logger.debug(f"شماره خرید از ستون 'shenase_takhsis': {purchase_number}")
                                
                                if not purchase_number:
                                    logger.error("شماره خرید یا شناسه تخصیص یافت نشد")
                                    records_failed += 1
                                    continue

                                # بررسی وجود شماره تلفن
                                phone_number = None
                                if not pd.isna(row.get('customer_phone')):
                                    phone_number = str(row['customer_phone']).strip()
                                    phone_number = re.sub(r'^0', '', phone_number)
                                    logger.debug(f"شماره تلفن: {phone_number}")
                                
                                if not phone_number:
                                    logger.error(f"شماره همراه خریدار برای رکورد {purchase_number} یافت نشد")
                                    records_failed += 1
                                    continue
                                
                                # ایجاد/آپدیت مشتری
                                customer_data = {}
                                
                                if not pd.isna(row.get('customer_name')):
                                    customer_data['name'] = str(row['customer_name']).strip()
                                
                                if not pd.isna(row.get('city')):
                                    customer_data['city'] = str(row['city']).strip()
                                
                                if not pd.isna(row.get('customer_type')):
                                    activity_type = map_activity_type(str(row['customer_type']).strip())
                                    if activity_type:
                                        customer_data['field_of_activity'] = activity_type
                                        logger.debug(f"نوع فعالیت: {activity_type}")
                                
                                logger.debug(f"داده‌های مشتری: {customer_data}")
                                customer, customer_created = Customer.objects.update_or_create(
                                    phone_number=phone_number,
                                    defaults=customer_data
                                )
                                logger.debug(f"مشتری {'ایجاد' if customer_created else 'به‌روزرسانی'} شد")

                                # ایجاد/آپدیت خرید
                                purchase_data = {
                                    'customer': customer,
                                    'bazaargah_phone_number': phone_number
                                }

                                # اضافه کردن فیلدهای اختیاری
                                if not pd.isna(row.get('weight')):
                                    try:
                                        weight = str(row['weight']).strip().replace(',', '')
                                        purchase_data['weight'] = int(float(weight))
                                        logger.debug(f"وزن: {purchase_data['weight']}")
                                    except Exception as e:
                                        logger.warning(f"خطا در تبدیل وزن: {str(e)}")
                                
                                if not pd.isna(row.get('company_price')):
                                    try:
                                        price = str(row['company_price']).strip().replace(',', '')
                                        purchase_data['company_price'] = int(float(price))
                                        logger.debug(f"قیمت شرکت: {purchase_data['company_price']}")
                                    except Exception as e:
                                        logger.warning(f"خطا در تبدیل قیمت شرکت: {str(e)}")
                                
                                if not pd.isna(row.get('tracking_number')):
                                    purchase_data['tracking_number'] = str(row['tracking_number']).strip()
                                
                                if not pd.isna(row.get('amount_paid')):
                                    try:
                                        amount = str(row['amount_paid']).strip().replace(',', '')
                                        purchase_data['amount_paid'] = int(float(amount))
                                        logger.debug(f"مبلغ پرداختی: {purchase_data['amount_paid']}")
                                    except Exception as e:
                                        logger.warning(f"خطا در تبدیل مبلغ پرداختی: {str(e)}")
                                
                                if not pd.isna(row.get('description')):
                                    purchase_data['description'] = str(row['description']).strip()
                                
                                if not pd.isna(row.get('payment_method')):
                                    payment_method = str(row['payment_method']).strip()
                                    purchase_data['payment_method'] = 'نقدی' if payment_method == 'نقدی' else 'توافقی'
                                
                                if not pd.isna(row.get('shenase_takhsis')):
                                    purchase_data['shenase_takhsis'] = str(row['shenase_takhsis']).strip()
                                
                                if not pd.isna(row.get('code_melli_tahvil')):
                                    purchase_data['code_melli_tahvil'] = str(row['code_melli_tahvil']).strip()
                                
                                if not pd.isna(row.get('tahvil_phone_number')):
                                    purchase_data['tahvil_phone_number'] = str(row['tahvil_phone_number']).strip()
                                
                                if not pd.isna(row.get('address')):
                                    purchase_data['address'] = str(row['address']).strip()

                                logger.debug(f"داده‌های خرید: {purchase_data}")
                                purchase, purchase_created = Purchase.objects.update_or_create(
                                    purchase_number=purchase_number,
                                    defaults=purchase_data
                                )
                                logger.debug(f"خرید {'ایجاد' if purchase_created else 'به‌روزرسانی'} شد")

                                if purchase_created or customer_created:
                                    records_updated += 1
                                    logger.debug(f"رکورد {purchase_number} با موفقیت پردازش شد")
                                else:
                                    logger.warning(f"رکورد {purchase_number} تغییری نکرد")

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
            
            # ثبت گزارش پردازش
            log_message = "\n".join(log_messages)
            ExcelProcessingLog.objects.create(
                excel_file=file_obj,
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
            # ثبت خطا در گزارش
            logger.error(f"خطا در پردازش فایل: {str(e)}", exc_info=True)
            
            ExcelProcessingLog.objects.create(
                excel_file=file_obj,
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
                # تست خواندن ستون‌ها
                columns = test_read_excel_columns(file_path)
                logger.debug(f"ستون‌های موجود در فایل: {columns}")

                # نگاشت دقیق ستون‌ها با تمام حالت‌های ممکن
                column_mapping = {
                    'کد': 'purchase_number',  # شماره خرید بازارگاه
                    'کد خرید': 'purchase_number',
                    'شماره خرید': 'purchase_number',
                    'شماره خرید بازارگاه': 'purchase_number',
                    'وزن کل خرید': 'weight',
                    'قیمت هر واحد': 'company_price',
                    'شماره پیگیری': 'tracking_number',
                    'مبلغ پرداختی': 'amount_paid',
                    'توضیحات': 'description',
                    'شیوه پرداخت': 'payment_method',
                    'شناسه تخصیص': 'shenase_takhsis',
                    'شناسه': 'shenase_takhsis',
                    'نام خریدار': 'customer_name',
                    'شماره همراه خریدار': 'customer_phone',
                    'نوع کاربری خریدار': 'customer_type',
                    'شهرستان': 'city',
                    'کد ملی تحویل': 'code_melli_tahvil',
                    'شماره هماهنگی تحویل': 'tahvil_phone_number',
                    'آدرس تحویل': 'address',
                    'آدرس خریدار': 'address'  # اگر آدرس تحویل نبود از این استفاده میشه
                }
                
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
                        if any(col in str(row.values) for col in ['کد', 'شناسه تخصیص', 'شناسه']):
                            header_row = idx
                            break
                    
                    if header_row is not None:
                        # تنظیم ستون‌های جدید
                        df.columns = df.iloc[header_row]
                        # حذف ردیف‌های اضافی و سطر اول که شامل "ثبت اطلاعات حمل" است
                        df = df.iloc[header_row + 1:].reset_index(drop=True)
                    
                    logger.debug(f"ستون‌های شناسایی شده قبل از نگاشت: {df.columns.tolist()}")
                    
                    # بررسی وجود ستون‌های مورد نیاز
                    required_columns = ['کد']  # فقط کد (شماره خرید) اجباری است
                    
                    # تمیز کردن نام ستون‌ها
                    df.columns = df.columns.str.strip()
                    
                    # نگاشت ستون‌ها
                    df = df.rename(columns=column_mapping, errors='ignore')
                    
                    logger.debug(f"ستون‌های شناسایی شده بعد از نگاشت: {df.columns.tolist()}")
                    
                    # بررسی وجود ستون‌های مورد نیاز با نام‌های مختلف
                    has_purchase_number = any(col in df.columns for col in ['کد', 'کد خرید', 'شماره خرید', 'شماره خرید بازارگاه', 'purchase_number'])
                    has_shenase = any(col in df.columns for col in ['شناسه تخصیص', 'شناسه', 'shenase_takhsis'])
                    
                    logger.debug(f"وجود کد خرید: {has_purchase_number}")
                    logger.debug(f"وجود شناسه تخصیص: {has_shenase}")
                    
                    if not (has_purchase_number or has_shenase):
                        error_message = "حداقل یکی از ستون‌های 'کد خرید' یا 'شناسه تخصیص' باید در فایل وجود داشته باشد"
                        logger.error(error_message)
                        logger.error(f"ستون‌های موجود: {df.columns.tolist()}")
                        return JsonResponse({
                            'status': 'error',
                            'message': error_message
                        }, status=400)
                    
                    # بررسی ساختار فایل
                    if len(df.columns) == 0:
                        raise ValueError("فایل خالی است یا ساختار معتبری ندارد")
                    
                    # اگر ستون 'کد' وجود دارد ولی 'کد خرید' وجود ندارد، آن را تغییر نام دهیم
                    if 'کد' in df.columns and 'کد خرید' not in df.columns:
                        logger.debug("تغییر نام ستون 'کد' به 'کد خرید'")
                        df = df.rename(columns={'کد': 'کد خرید'})
                    
                    # اگر ستون 'شناسه' وجود دارد ولی 'شناسه تخصیص' وجود ندارد، آن را تغییر نام دهیم
                    if 'شناسه' in df.columns and 'شناسه تخصیص' not in df.columns:
                        logger.debug("تغییر نام ستون 'شناسه' به 'شناسه تخصیص'")
                        df = df.rename(columns={'شناسه': 'شناسه تخصیص'})
                    
                    logger.debug(f"ستون‌ها پس از تغییر نام: {df.columns.tolist()}")
                    
                    # حذف بررسی اضافی ستون‌های اجباری
                    # متغیرهای ثبت گزارش
                    records_processed = len(df)
                    records_updated = 0
                    records_failed = 0
                    success = True
                    log_messages = []
                    
                    # ۱. حذف رکوردهای تکراری شناسه تخصیص
                    if 'shenase_takhsis' in df.columns:
                        initial_records = len(df)
                        df.drop_duplicates(subset=['shenase_takhsis'], keep='first', inplace=True)
                        duplicate_removed = initial_records - len(df)
                        if duplicate_removed > 0:
                            log_messages.append(f"{duplicate_removed} رکورد تکراری حذف شد")
                    
                    # ۲. پردازش و به‌روزرسانی Purchase
                    try:
                        # عملیات بروزرسانی
                        with transaction.atomic():
                            for _, row in df.iterrows():
                                try:
                                    # بررسی وجود کد خرید یا شناسه تخصیص
                                    purchase_number = None
                                    logger.debug(f"بررسی ستون‌های موجود در ردیف: {row.index}")
                                    logger.debug(f"مقادیر ردیف: {row.to_dict()}")
                                    
                                    # بررسی ستون‌های نگاشت شده
                                    if not pd.isna(row.get('purchase_number')):
                                        purchase_number = str(row['purchase_number']).strip()
                                        logger.debug(f"شماره خرید از ستون 'purchase_number': {purchase_number}")
                                    elif not pd.isna(row.get('shenase_takhsis')):
                                        purchase_number = str(row['shenase_takhsis']).strip()
                                        logger.debug(f"شماره خرید از ستون 'shenase_takhsis': {purchase_number}")
                                    
                                    if not purchase_number:
                                        logger.error("شماره خرید یا شناسه تخصیص یافت نشد")
                                        records_failed += 1
                                        continue

                                    # بررسی وجود شماره تلفن
                                    phone_number = None
                                    if not pd.isna(row.get('customer_phone')):
                                        phone_number = str(row['customer_phone']).strip()
                                        phone_number = re.sub(r'^0', '', phone_number)
                                        logger.debug(f"شماره تلفن: {phone_number}")
                                    
                                    if not phone_number:
                                        logger.error(f"شماره همراه خریدار برای رکورد {purchase_number} یافت نشد")
                                        records_failed += 1
                                        continue
                                    
                                    # ایجاد/آپدیت مشتری
                                    customer_data = {}
                                    
                                    if not pd.isna(row.get('customer_name')):
                                        customer_data['name'] = str(row['customer_name']).strip()
                                    
                                    if not pd.isna(row.get('city')):
                                        customer_data['city'] = str(row['city']).strip()
                                    
                                    if not pd.isna(row.get('customer_type')):
                                        activity_type = map_activity_type(str(row['customer_type']).strip())
                                        if activity_type:
                                            customer_data['field_of_activity'] = activity_type
                                            logger.debug(f"نوع فعالیت: {activity_type}")
                                    
                                    logger.debug(f"داده‌های مشتری: {customer_data}")
                                    customer, customer_created = Customer.objects.update_or_create(
                                        phone_number=phone_number,
                                        defaults=customer_data
                                    )
                                    logger.debug(f"مشتری با شماره {phone_number} {'ایجاد' if customer_created else 'به‌روزرسانی'} شد")

                                    # ایجاد/آپدیت خرید
                                    purchase_data = {
                                        'customer': customer,
                                        'bazaargah_phone_number': phone_number
                                    }

                                    # اضافه کردن فیلدهای اختیاری
                                    if not pd.isna(row.get('weight')):
                                        try:
                                            weight = str(row['weight']).strip().replace(',', '')
                                            purchase_data['weight'] = int(float(weight))
                                            logger.debug(f"وزن: {purchase_data['weight']}")
                                        except Exception as e:
                                            logger.warning(f"خطا در تبدیل وزن: {str(e)}")
                                    
                                    if not pd.isna(row.get('company_price')):
                                        try:
                                            price = str(row['company_price']).strip().replace(',', '')
                                            purchase_data['company_price'] = int(float(price))
                                            logger.debug(f"قیمت شرکت: {purchase_data['company_price']}")
                                        except Exception as e:
                                            logger.warning(f"خطا در تبدیل قیمت شرکت: {str(e)}")
                                    
                                    if not pd.isna(row.get('tracking_number')):
                                        purchase_data['tracking_number'] = str(row['tracking_number']).strip()
                                    
                                    if not pd.isna(row.get('amount_paid')):
                                        try:
                                            amount = str(row['amount_paid']).strip().replace(',', '')
                                            purchase_data['amount_paid'] = int(float(amount))
                                            logger.debug(f"مبلغ پرداختی: {purchase_data['amount_paid']}")
                                        except Exception as e:
                                            logger.warning(f"خطا در تبدیل مبلغ پرداختی: {str(e)}")
                                    
                                    if not pd.isna(row.get('description')):
                                        purchase_data['description'] = str(row['description']).strip()
                                    
                                    if not pd.isna(row.get('payment_method')):
                                        payment_method = str(row['payment_method']).strip()
                                        purchase_data['payment_method'] = 'نقدی' if payment_method == 'نقدی' else 'توافقی'
                                    
                                    if not pd.isna(row.get('shenase_takhsis')):
                                        purchase_data['shenase_takhsis'] = str(row['shenase_takhsis']).strip()
                                    
                                    if not pd.isna(row.get('code_melli_tahvil')):
                                        purchase_data['code_melli_tahvil'] = str(row['code_melli_tahvil']).strip()
                                    
                                    if not pd.isna(row.get('tahvil_phone_number')):
                                        purchase_data['tahvil_phone_number'] = str(row['tahvil_phone_number']).strip()
                                    
                                    if not pd.isna(row.get('address')):
                                        purchase_data['address'] = str(row['address']).strip()

                                    logger.debug(f"داده‌های خرید: {purchase_data}")
                                    purchase, purchase_created = Purchase.objects.update_or_create(
                                        purchase_number=purchase_number,
                                        defaults=purchase_data
                                    )
                                    logger.debug(f"خرید با شماره {purchase_number} {'ایجاد' if purchase_created else 'به‌روزرسانی'} شد")

                                    if purchase_created or customer_created:
                                        records_updated += 1
                                        logger.debug(f"رکورد {purchase_number} با موفقیت پردازش شد")
                                    else:
                                        logger.warning(f"رکورد {purchase_number} تغییری نکرد")

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

def map_activity_type(activity_type):
    """نگاشت نوع فعالیت به مقادیر مجاز"""
    if not activity_type:
        logger.debug("نوع فعالیت خالی است - مقدار پیش‌فرض 'chicken' برگردانده می‌شود")
        return 'chicken'
        
    activity_type = str(activity_type).strip()
    logger.debug(f"نوع فعالیت دریافتی (قبل از پردازش): '{activity_type}'")
    
    # تبدیل اعداد به رشته
    if isinstance(activity_type, (int, float)):
        activity_type = str(activity_type)
    
    # حذف فاصله‌های اضافی و یکسان‌سازی
    activity_type = ' '.join(activity_type.split())
    activity_type = activity_type.replace('ي', 'ی').replace('ك', 'ک')
    
    logger.debug(f"نوع فعالیت پس از پاکسازی: '{activity_type}'")
    
    # نگاشت دقیق
    activity_mapping = {
        'مرغداری': 'chicken',
        'مرغدار': 'chicken',
        'مرغداران': 'chicken',
        'تعاونی مرغداران': 'chicken',
        'مرغ': 'chicken',
        'پرورش مرغ': 'chicken',
        'پرورش طیور': 'chicken',
        'طیور': 'chicken',
        'دامداری': 'livestock',
        'دامدار': 'livestock',
        'دامداران': 'livestock',
        'تعاونی دامداران': 'livestock',
        'دام': 'livestock',
        'پرورش دام': 'livestock',
        'گاوداری': 'livestock',
        'گوسفندداری': 'livestock',
        'کارخانه خوراک': 'factory',
        'کارخانه': 'factory',
        'تولیدی': 'factory',
        'تولید': 'factory',
        'صنعتی': 'factory',
        'شرکت تولیدی': 'factory',
        'شرکت': 'factory',
        'تعاونی': 'factory',
        'تعاونی تولید': 'factory',
        'دلال': 'trader',
        'دلالان': 'trader',
        'واسطه': 'trader',
        'خرید و فروش': 'trader',
        'بازرگانی': 'trader',
        'تجاری': 'trader',
        'پرورش آبزیان': 'fish',
        'آبزیان': 'fish',
        'پرورش ماهی': 'fish',
        'ماهی': 'fish',
        'شیلات': 'fish'
    }
    
    # اول سعی می‌کنیم نگاشت دقیق پیدا کنیم
    mapped_value = activity_mapping.get(activity_type)
    if mapped_value:
        logger.debug(f"نگاشت مستقیم: '{activity_type}' -> '{mapped_value}'")
        return mapped_value
    
    # اگر نگاشت مستقیم پیدا نشد، بررسی کلمات کلیدی
    activity_type_lower = activity_type.lower()
    logger.debug(f"بررسی کلمات کلیدی برای: '{activity_type_lower}'")
    
    if any(keyword in activity_type_lower for keyword in ['مرغ', 'طیور', 'پرنده']):
        logger.debug(f"تشخیص نوع فعالیت 'chicken' از طریق کلمات کلیدی برای: '{activity_type}'")
        return 'chicken'
    elif any(keyword in activity_type_lower for keyword in ['دام', 'گاو', 'گوسفند']):
        logger.debug(f"تشخیص نوع فعالیت 'livestock' از طریق کلمات کلیدی برای: '{activity_type}'")
        return 'livestock'
    elif any(keyword in activity_type_lower for keyword in ['کارخانه', 'تولید', 'صنعت', 'تعاونی']):
        logger.debug(f"تشخیص نوع فعالیت 'factory' از طریق کلمات کلیدی برای: '{activity_type}'")
        return 'factory'
    elif any(keyword in activity_type_lower for keyword in ['دلال', 'واسطه', 'بازرگان', 'تجار']):
        logger.debug(f"تشخیص نوع فعالیت 'trader' از طریق کلمات کلیدی برای: '{activity_type}'")
        return 'trader'
    elif any(keyword in activity_type_lower for keyword in ['آبزی', 'ماهی', 'شیلات']):
        logger.debug(f"تشخیص نوع فعالیت 'fish' از طریق کلمات کلیدی برای: '{activity_type}'")
        return 'fish'
    
    # اگر هیچ تطابقی پیدا نشد، پیش‌فرض مرغدار
    logger.debug(f"هیچ تطابقی برای '{activity_type}' پیدا نشد - استفاده از مقدار پیش‌فرض 'chicken'")
    return 'chicken'

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

def test_read_excel_columns(file_path):
    """تست خواندن ستون‌های فایل اکسل"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '<html' in content.lower():
            logger.debug("محتوای HTML شناسایی شد")
            df = pd.read_html(content)[0]
            
            # پیدا کردن ردیف header
            header_row = None
            for idx, row in df.iterrows():
                row_values = [str(val).strip() for val in row.values]
                logger.debug(f"بررسی ردیف {idx}: {row_values}")
                
                # بررسی اینکه آیا این سطر شامل "ثبت اطلاعات حمل" است
                if any('ثبت اطلاعات حمل' in str(val) for val in row_values):
                    logger.debug(f"ردیف {idx} شامل 'ثبت اطلاعات حمل' است - نادیده گرفته شد")
                    continue
                
                # بررسی وجود هر یک از ستون‌های کلیدی
                key_columns = ['کد', 'کد خرید', 'شماره خرید', 'شماره خرید بازارگاه', 'شناسه تخصیص', 'شناسه']
                found_columns = [col for col in key_columns if any(col in str(val) for val in row_values)]
                
                if found_columns:
                    logger.debug(f"ردیف {idx} به عنوان header انتخاب شد. ستون‌های کلیدی یافت شده: {found_columns}")
                    header_row = idx
                    break
            
            if header_row is not None:
                df.columns = df.iloc[header_row]
                df = df.iloc[header_row + 1:].reset_index(drop=True)
                
                # تمیز کردن نام ستون‌ها
                df.columns = df.columns.str.strip()
                logger.debug(f"ستون‌های نهایی پس از تمیز کردن: {df.columns.tolist()}")
                
                # بررسی وجود ستون‌های کلیدی
                has_purchase_number = any(col in df.columns for col in ['کد', 'کد خرید', 'شماره خرید', 'شماره خرید بازارگاه', 'purchase_number'])
                has_shenase = any(col in df.columns for col in ['شناسه تخصیص', 'شناسه', 'shenase_takhsis'])
                
                logger.debug(f"وجود کد خرید: {has_purchase_number}")
                logger.debug(f"وجود شناسه تخصیص: {has_shenase}")
                
                # بررسی ساختار فایل
                if len(df.columns) == 0:
                    raise ValueError("فایل خالی است یا ساختار معتبری ندارد")
                
                logger.debug(f"ستون‌ها پس از تغییر نام: {df.columns.tolist()}")
                
                return df.columns.tolist()
            else:
                logger.warning("هیچ ردیف header مناسبی پیدا نشد")
                return []
        else:
            logger.warning("فایل در قالب HTML نیست")
            return []
    except Exception as e:
        logger.error(f"خطا در خواندن ستون‌های فایل: {str(e)}")
        return [] 