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
                                if 'customer_phone' in row and not pd.isna(row['customer_phone']):
                                    phone_number = str(row['customer_phone']).strip()
                                    # حذف صفر ابتدایی و پاکسازی
                                    phone_number = re.sub(r'\D', '', phone_number)  # حذف همه کاراکترهای غیرعددی
                                    phone_number = re.sub(r'^0', '', phone_number)  # حذف صفر ابتدایی
                                    # اطمینان از اینکه 10 رقم است
                                    if len(phone_number) > 10:
                                        phone_number = phone_number[-10:]
                                    logger.debug(f"شماره تلفن: {phone_number}")
                                
                                if not phone_number or len(phone_number) != 10:
                                    logger.error(f"شماره همراه خریدار برای رکورد {purchase_number} معتبر نیست: {phone_number}")
                                    records_failed += 1
                                    continue
                                
                                # ایجاد/آپدیت مشتری
                                customer_data = {
                                    'field_of_activity': 'chicken'  # تنظیم پیش‌فرض به مرغدار
                                }
                                
                                if 'customer_name' in row and not pd.isna(row['customer_name']):
                                    customer_data['name'] = str(row['customer_name']).strip()
                                else:
                                    # نام پیش‌فرض اگر نام خریدار خالی باشد
                                    customer_data['name'] = "خریدار " + phone_number[-4:]
                                
                                if 'city' in row and not pd.isna(row['city']):
                                    customer_data['city'] = str(row['city']).strip()
                                
                                if 'customer_type' in row and not pd.isna(row['customer_type']):
                                    activity_type = map_activity_type(str(row['customer_type']).strip())
                                    if activity_type:
                                        customer_data['field_of_activity'] = activity_type
                                        logger.debug(f"نوع فعالیت: {activity_type}")
                                
                                logger.debug(f"داده‌های مشتری: {customer_data}")
                                try:
                                    # ایجاد یا به‌روزرسانی مشتری
                                    customer, customer_created = Customer.objects.update_or_create(
                                        phone_number=phone_number,
                                        defaults=customer_data
                                    )
                                    
                                    logger.debug(f"وضعیت نماینده فروش قبل از اختصاص: {customer.sales_agent.exists()}")
                                    
                                    # اختصاص نماینده فروش پیش‌فرض به مشتری در صورت نیاز
                                    if not customer.sales_agent.exists():
                                        logger.error(f"تمام تلاش‌ها برای اختصاص نماینده فروش به مشتری با شماره {phone_number} ناموفق بود")
                                        records_failed += 1
                                        continue
                                
                                except Exception as e:
                                    logger.error(f"خطا در ایجاد/به‌روزرسانی مشتری: {str(e)}", exc_info=True)
                                    records_failed += 1
                                    continue

                                # ایجاد/آپدیت داده‌های خرید - بخش اصلی که باید اصلاح شود
                                purchase_data = {
                                    'customer': customer,
                                    'bazaargah_phone_number': phone_number,
                                    'type': 'bazaargah'  # تنظیم نوع خرید به بازارگاه
                                }
                                
                                # تنظیم کوتاژ
                                if bge_file.cargo:
                                    purchase_data['cargo'] = bge_file.cargo

                                # اضافه کردن وزن با مقدار پیش‌فرض مناسب
                                if 'weight' in row and not pd.isna(row['weight']):
                                    try:
                                        weight = str(row['weight']).strip().replace(',', '')
                                        purchase_data['weight'] = int(float(weight))
                                        # اطمینان از اینکه وزن بیشتر از 10 تن است
                                        if purchase_data['weight'] <= 10000:
                                            purchase_data['weight'] = 15000
                                    except Exception as e:
                                        logger.warning(f"خطا در تبدیل وزن: {str(e)}")
                                        purchase_data['weight'] = 15000  # مقدار پیش‌فرض برای وزن (بالای 10000)
                                else:
                                    purchase_data['weight'] = 15000  # مقدار پیش‌فرض برای وزن

                                # تنظیم قیمت شرکت
                                if 'company_price' in row and not pd.isna(row['company_price']):
                                    try:
                                        price = str(row['company_price']).strip().replace(',', '')
                                        purchase_data['company_price'] = int(float(price))
                                        # اطمینان از اینکه قیمت در محدوده مجاز است
                                        if purchase_data['company_price'] < 50000 or purchase_data['company_price'] > 300000:
                                            purchase_data['company_price'] = 95000
                                    except Exception as e:
                                        logger.warning(f"خطا در تبدیل قیمت شرکت: {str(e)}")
                                        purchase_data['company_price'] = 95000  # مقدار پیش‌فرض برای قیمت
                                else:
                                    purchase_data['company_price'] = 95000  # مقدار پیش‌فرض برای قیمت

                                # تنظیم فی فروش
                                purchase_data['customer_price'] = purchase_data['company_price']
                                
                                # اضافه کردن شماره پیگیری
                                if 'tracking_number' in row and not pd.isna(row['tracking_number']):
                                    tracking_number = str(row['tracking_number']).strip()
                                    # شماره پیگیری باید 6 رقم باشد
                                    tracking_number = re.sub(r'\D', '', tracking_number)  # حذف کاراکترهای غیرعددی
                                    if len(tracking_number) > 6:
                                        tracking_number = tracking_number[:6]
                                    if len(tracking_number) < 6:
                                        tracking_number = tracking_number.zfill(6)
                                    purchase_data['tracking_number'] = tracking_number
                                
                                # اضافه کردن مبلغ پرداختی
                                if 'amount_paid' in row and not pd.isna(row['amount_paid']):
                                    try:
                                        amount = str(row['amount_paid']).strip().replace(',', '')
                                        purchase_data['amount_paid'] = int(float(amount))
                                    except Exception as e:
                                        logger.warning(f"خطا در تبدیل مبلغ پرداختی: {str(e)}")
                                
                                # اضافه کردن توضیحات
                                if 'description' in row and not pd.isna(row['description']):
                                    purchase_data['description'] = str(row['description']).strip()
                                
                                # اضافه کردن روش پرداخت
                                if 'payment_method' in row and not pd.isna(row['payment_method']):
                                    payment_method = str(row['payment_method']).strip()
                                    purchase_data['payment_method'] = 'نقدی' if payment_method == 'نقدی' else 'توافقی'
                                else:
                                    purchase_data['payment_method'] = 'نقدی'  # مقدار پیش‌فرض
                                
                                # اضافه کردن شناسه تخصیص
                                if 'shenase_takhsis' in row and not pd.isna(row['shenase_takhsis']):
                                    purchase_data['shenase_takhsis'] = str(row['shenase_takhsis']).strip()
                                
                                # اضافه کردن کد ملی تحویل
                                if 'code_melli_tahvil' in row and not pd.isna(row['code_melli_tahvil']):
                                    purchase_data['code_melli_tahvil'] = str(row['code_melli_tahvil']).strip()
                                
                                # اضافه کردن شماره تماس تحویل
                                if 'tahvil_phone_number' in row and not pd.isna(row['tahvil_phone_number']):
                                    purchase_data['tahvil_phone_number'] = str(row['tahvil_phone_number']).strip()
                                
                                # اضافه کردن آدرس
                                if 'address' in row and not pd.isna(row['address']):
                                    purchase_data['address'] = str(row['address']).strip()
                                
                                logger.debug(f"داده‌های خرید آماده شده: {purchase_data}")
                                
                                try:
                                    # بررسی وجود نماینده فروش برای مشتری
                                    sales_agent = customer.sales_agent.first()
                                    if not sales_agent:
                                        logger.error(f"مشتری با شماره {phone_number} هیچ نماینده فروشی ندارد")
                                        records_failed += 1
                                        continue
                                    
                                    # ابتدا بررسی می‌کنیم آیا خریدی با این شماره وجود دارد
                                    existing_purchase = Purchase.objects.filter(purchase_number=purchase_number).first()
                                    
                                    if existing_purchase:
                                        # اگر موجود است، فیلدها را به‌روز می‌کنیم
                                        for key, value in purchase_data.items():
                                            setattr(existing_purchase, key, value)
                                        existing_purchase.save()
                                        logger.debug(f"خرید با شماره {purchase_number} به‌روزرسانی شد با آیدی {existing_purchase.id}")
                                        # افزایش شمارنده رکوردهای به‌روزرسانی شده
                                        records_updated += 1
                                    else:
                                        # ایجاد آیدی برای خرید جدید
                                        purchase_id = None
                                        if sales_agent and sales_agent.factor_code:
                                            # ایجاد آیدی با استفاده از factor_code نماینده فروش
                                            factor_code = sales_agent.factor_code
                                            # بررسی آخرین خرید با این کد فاکتور
                                            last_purchase = Purchase.objects.filter(id__startswith=factor_code).order_by('-id').first()
                                            if last_purchase:
                                                last_serial = str(last_purchase.id)[len(factor_code):]
                                                # تمیز کردن و استخراج عدد آخرین سریال
                                                digits_only = ''.join(filter(str.isdigit, last_serial))
                                                if digits_only:
                                                    last_serial_number = int(digits_only)
                                                    new_serial = last_serial_number + 1
                                                else:
                                                    new_serial = 1
                                            else:
                                                new_serial = 1
                                            
                                            purchase_id = f"{factor_code}{str(new_serial).zfill(4)}"
                                            logger.debug(f"آیدی خرید جدید ایجاد شد: {purchase_id}")
                                        
                                        try:
                                            if purchase_id:
                                                # ایجاد خرید جدید با آیدی مشخص
                                                new_purchase = Purchase(
                                                    id=purchase_id,
                                                    purchase_number=purchase_number,
                                                    **purchase_data
                                                )
                                                new_purchase.save()
                                                logger.debug(f"خرید جدید با شماره {purchase_number} و آیدی {purchase_id} ایجاد شد")
                                            else:
                                                # در صورت مشکل در ایجاد آیدی، استفاده از روش معمولی
                                                new_purchase = Purchase.objects.create(
                                                    purchase_number=purchase_number,
                                                    **purchase_data
                                                )
                                                logger.debug(f"خرید جدید با شماره {purchase_number} ایجاد شد با آیدی سیستمی {new_purchase.id}")
                                            
                                            # افزایش شمارنده رکوردهای به‌روزرسانی شده
                                            records_updated += 1
                                        except Exception as e:
                                            logger.error(f"خطا در ایجاد خرید جدید: {str(e)}")
                                            records_failed += 1
                                            continue
                                except Exception as e:
                                    logger.error(f"خطا در ایجاد/به‌روزرسانی خرید: {str(e)}", exc_info=True)
                                    records_failed += 1
                                    continue

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
                    'آدرس خریدار': 'address',
                    'آدرس  خریدار': 'address'
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
                        # یافتن یک sales_agent برای اختصاص به مشتری‌ها
                        from core.SalesAgentModel import SalesAgent
                        default_sales_agent = None
                        try:
                            default_sales_agent = SalesAgent.objects.first()
                            if default_sales_agent:
                                logger.debug(f"نماینده فروش پیش‌فرض یافت شد: {default_sales_agent.id}")
                            else:
                                logger.warning("هیچ نماینده فروشی در سیستم یافت نشد")
                                # ایجاد یک نماینده فروش به صورت خودکار
                                try:
                                    from django.contrib.auth.models import User
                                    admin_user = User.objects.filter(is_superuser=True).first()
                                    if admin_user:
                                        # استفاده از get_or_create برای جلوگیری از ایجاد نماینده‌های تکراری
                                        default_sales_agent, created = SalesAgent.objects.get_or_create(
                                            user=admin_user,
                                            defaults={
                                                'name': "نماینده فروش پیش‌فرض",
                                                'factor_code': "AA"  # کد فاکتور اتوماتیک
                                            }
                                        )
                                        logger.debug(f"نماینده فروش پیش‌فرض {'ایجاد' if created else 'بازیابی'} شد: {default_sales_agent.id}")
                                    else:
                                        logger.error("هیچ کاربر ادمینی برای ایجاد نماینده فروش یافت نشد")
                                except Exception as e:
                                    logger.error(f"خطا در ایجاد نماینده فروش پیش‌فرض: {str(e)}")
                        except Exception as e:
                            logger.warning(f"خطا در یافتن نماینده فروش پیش‌فرض: {str(e)}")
                            
                            # اگر هنوز نماینده فروش نداریم، یک نماینده اضطراری ایجاد می‌کنیم
                            try:
                                from django.contrib.auth.models import User
                                admin_user = User.objects.filter(is_superuser=True).first()
                                if admin_user:
                                    default_sales_agent, created = SalesAgent.objects.get_or_create(
                                        user=admin_user,
                                        name="نماینده فروش اضطراری",
                                        defaults={'factor_code': "ZQ"}
                                    )
                                    logger.debug(f"نماینده فروش اضطراری {'ایجاد' if created else 'بازیابی'} شد: {default_sales_agent.id}")
                            except Exception as e:
                                logger.error(f"خطا در ایجاد نماینده فروش اضطراری: {str(e)}")
                                records_failed += 1
                                pass
                        
                        # عملیات بروزرسانی
                        with transaction.atomic():
                            for idx, row in df.iterrows():
                                try:
                                    # محدود کردن تعداد رکوردها برای تست
                                    if idx > 100:  # فقط 100 رکورد اول پردازش می‌شوند
                                        break
                                        
                                    # بررسی وجود کد خرید یا شناسه تخصیص
                                    purchase_number = None
                                    logger.debug(f"بررسی مقادیر ردیف {idx}: {row.to_dict()}")
                                    
                                    # بررسی ستون‌های نگاشت شده
                                    if 'purchase_number' in row and not pd.isna(row['purchase_number']):
                                        purchase_number = str(row['purchase_number']).strip()
                                        logger.debug(f"شماره خرید از ستون 'purchase_number': {purchase_number}")
                                    elif 'shenase_takhsis' in row and not pd.isna(row['shenase_takhsis']):
                                        purchase_number = str(row['shenase_takhsis']).strip()
                                        logger.debug(f"شماره خرید از ستون 'shenase_takhsis': {purchase_number}")
                                    
                                    if not purchase_number:
                                        logger.error("شماره خرید یا شناسه تخصیص یافت نشد")
                                        records_failed += 1
                                        continue
                                    
                                    # اطمینان از اینکه شماره خرید 7 رقم است
                                    if len(purchase_number) != 7 or not purchase_number.isdigit():
                                        logger.warning(f"شماره خرید {purchase_number} معتبر نیست (باید 7 رقم عددی باشد) - تلاش برای اصلاح")
                                        # تبدیل به عدد و افزودن صفر به ابتدا در صورت نیاز
                                        purchase_number = re.sub(r'\D', '', purchase_number)
                                        if len(purchase_number) > 7:
                                            purchase_number = purchase_number[:7]
                                        if len(purchase_number) < 7:
                                            purchase_number = purchase_number.zfill(7)
                                        logger.debug(f"شماره خرید اصلاح شده: {purchase_number}")

                                    # بررسی وجود شماره تلفن
                                    phone_number = None
                                    if 'customer_phone' in row and not pd.isna(row['customer_phone']):
                                        phone_number = str(row['customer_phone']).strip()
                                        # حذف صفر ابتدایی و پاکسازی
                                        phone_number = re.sub(r'\D', '', phone_number)  # حذف همه کاراکترهای غیرعددی
                                        phone_number = re.sub(r'^0', '', phone_number)  # حذف صفر ابتدایی
                                        # اطمینان از اینکه 10 رقم است
                                        if len(phone_number) > 10:
                                            phone_number = phone_number[-10:]
                                        logger.debug(f"شماره تلفن: {phone_number}")
                                    
                                    if not phone_number or len(phone_number) != 10:
                                        logger.error(f"شماره همراه خریدار برای رکورد {purchase_number} معتبر نیست: {phone_number}")
                                        records_failed += 1
                                        continue
                                    
                                    # ایجاد/آپدیت مشتری
                                    customer_data = {
                                        'field_of_activity': 'chicken'  # تنظیم پیش‌فرض به مرغدار
                                    }
                                    
                                    if 'customer_name' in row and not pd.isna(row['customer_name']):
                                        customer_data['name'] = str(row['customer_name']).strip()
                                    else:
                                        # نام پیش‌فرض اگر نام خریدار خالی باشد
                                        customer_data['name'] = "خریدار " + phone_number[-4:]
                                    
                                    if 'city' in row and not pd.isna(row['city']):
                                        customer_data['city'] = str(row['city']).strip()
                                    
                                    if 'customer_type' in row and not pd.isna(row['customer_type']):
                                        activity_type = map_activity_type(str(row['customer_type']).strip())
                                        if activity_type:
                                            customer_data['field_of_activity'] = activity_type
                                            logger.debug(f"نوع فعالیت: {activity_type}")
                                    
                                    logger.debug(f"داده‌های مشتری: {customer_data}")
                                    try:
                                        # ایجاد یا به‌روزرسانی مشتری
                                        customer, customer_created = Customer.objects.update_or_create(
                                            phone_number=phone_number,
                                            defaults=customer_data
                                        )
                                        
                                        logger.debug(f"وضعیت نماینده فروش قبل از اختصاص: {customer.sales_agent.exists()}")
                                        
                                        # اختصاص نماینده فروش پیش‌فرض به مشتری در صورت نیاز
                                        if not customer.sales_agent.exists():
                                            logger.error(f"تمام تلاش‌ها برای اختصاص نماینده فروش به مشتری با شماره {phone_number} ناموفق بود")
                                            records_failed += 1
                                            continue
                                    
                                    except Exception as e:
                                        logger.error(f"خطا در ایجاد/به‌روزرسانی مشتری: {str(e)}", exc_info=True)
                                        records_failed += 1
                                        pass
                                except Exception as e:
                                    logger.error(f"خطا در پردازش رکورد: {str(e)}", exc_info=True)
                                    records_failed += 1
                    except Exception as e:
                        logger.error(f"خطا در پردازش رکورد: {str(e)}", exc_info=True)
                        records_failed += 1
                        pass
            except Exception as e:
                logger.error(f"خطا در خواندن فایل: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'خطا در خواندن فایل: {str(e)}'
                }, status=500)
            
            # بررسی موفقیت خواندن فایل
            if 'df' not in locals() or df is None or len(df) == 0:
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
            
            # به‌روزرسانی وضعیت پردازش فایل
            bge_file.is_processed = True
            bge_file.save()
            
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
    # برگرداندن مقدار پیش‌فرض 'chicken' (مرغدار) برای همه حالت‌ها
    logger.debug(f"نوع فعالیت دریافتی: '{activity_type}' - استفاده از مقدار پیش‌فرض 'chicken'")
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