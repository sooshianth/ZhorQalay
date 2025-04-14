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
                temp_file_path = os.path.join(settings.MEDIA_ROOT, 'temp_excel.xls')
                with open(temp_file_path, 'wb+') as destination:
                    for chunk in excel_file.chunks():
                        destination.write(chunk)
                
                # خواندن محتوای فایل اکسل
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # بررسی وجود HTML در فایل
                if '<html' not in content.lower():
                    logger.warning(f"محتوای فایل نامعتبر است: HTML یافت نشد")
                    messages.error(request, 'فایل اکسل باید مبتنی بر HTML باشد')
                    os.remove(temp_file_path)  # حذف فایل موقت
                    return redirect('excel_manager:upload_bge_file')
                
                # استفاده از pandas برای خواندن جدول HTML
                tables = pd.read_html(content)
                if not tables:
                    logger.warning(f"جدولی در فایل اکسل یافت نشد")
                    messages.error(request, 'جدولی در فایل اکسل یافت نشد')
                    os.remove(temp_file_path)  # حذف فایل موقت
                    return redirect('excel_manager:upload_bge_file')
                
                # بررسی ستون‌های جدول
                df = tables[0]
                
                # بررسی وجود ستون کد کوتاژ
                if 'کد کوتاژ' not in df.columns and 'کوتاژ' not in df.columns:
                    logger.warning(f"ستون کد کوتاژ در فایل یافت نشد")
                    messages.error(request, 'ستون کد کوتاژ در فایل یافت نشد')
                    os.remove(temp_file_path)  # حذف فایل موقت
                    return redirect('excel_manager:upload_bge_file')
                
                # ستون کوتاژ را پیدا کن
                cottage_column = 'کد کوتاژ' if 'کد کوتاژ' in df.columns else 'کوتاژ'
                
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
                
                # اگر کوتاژها مطابقت نداشته باشند، خطا نمایش بده
                if cottage_mismatch:
                    unique_cottages = list(set(mismatched_cottages))
                    logger.warning(f"کوتاژ محصول ({cargo_product.cottage}) با کوتاژ رکوردهای فایل مطابقت ندارد: {unique_cottages}")
                    messages.error(request, f'کوتاژ محصول ({cargo_product.cottage}) با کوتاژ برخی رکوردهای فایل مطابقت ندارد. کوتاژهای مشاهده شده در فایل: {", ".join(unique_cottages[:5])}{" و ..." if len(unique_cottages) > 5 else ""} - لطفاً فایل صحیح را آپلود کنید یا محصول با کوتاژ مناسب را انتخاب نمایید.')
                    os.remove(temp_file_path)  # حذف فایل موقت
                    return redirect('excel_manager:upload_bge_file')
                
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
                    new_filename = f"BGE_{cargo_product.cottage}_{cargo_product.get_product_type_display()}.xls"
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
                # خواندن محتوای فایل اکسل مبتنی بر HTML
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '<html' not in content.lower():
                    messages.error(request, 'فایل اکسل باید مبتنی بر HTML باشد.')
                    processing_log.log_message = "فایل اکسل باید مبتنی بر HTML باشد."
                    processing_log.save()
                    return redirect('excel_manager:bge_files_list')
                
                # استفاده از pandas برای خواندن جدول HTML
                tables = pd.read_html(content)
                if not tables:
                    messages.error(request, 'جدولی در فایل اکسل یافت نشد.')
                    processing_log.log_message = "جدولی در فایل اکسل یافت نشد."
                    processing_log.save()
                    return redirect('excel_manager:bge_files_list')
                
                # گزارش دیباگ برای تعداد ردیف‌ها
                df = tables[0]
                logger.debug(f"تعداد ردیف‌های خوانده شده: {len(df)}")
                logger.debug(f"ستون‌های موجود در فایل: {df.columns.tolist()}")
                
                # بررسی وجود ستون‌های ضروری
                required_columns = ['کد', 'شناسه تخصیص', 'وزن کل خرید', 'کد ملی تحویل', 'شماره هماهنگی تحویل', 'شماره همراه خریدار', 
                                    'نام خریدار', 'آدرس تحویل', 'مبلغ پرداختی', 'شیوه پرداخت']
                
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
                
                # پردازش رکوردها
                records_processed = 0
                records_updated = 0
                records_created = 0
                records_failed = 0
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
                        if shenase_takhsis and Purchase.objects.filter(shenase_takhsis=shenase_takhsis).exists():
                            rows_to_remove.append(idx)
                            continue
                        
                        # هر پردازش در یک بلاک atomic جداگانه انجام می‌شود
                        with transaction.atomic():
                            if purchase:
                                try:
                                    # به‌روزرسانی خرید موجود - استفاده از update به جای save برای دور زدن validation
                                    Purchase.objects.filter(id=purchase.id).update(
                                        shenase_takhsis=shenase_takhsis,
                                        code_melli_tahvil=code_melli_tahvil,
                                        tahvil_phone_number=tahvil_phone_number,
                                        bazaargah_phone_number=bazaargah_phone_number,
                                        address=address,
                                        weight=weight,
                                        cargo=bge_file.cargo,
                                        amount_paid=amount_paid,
                                        payment_method=payment_method,
                                        is_takhsised=True if shenase_takhsis else purchase.is_takhsised
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
                                                # ایجاد مشتری جدید با ORM جنگو به جای SQL مستقیم
                                                customer = Customer.objects.create(
                                                    phone_number=bazaargah_phone_number,
                                                    name=customer_name if customer_name else "مشتری جدید",
                                                    field_of_activity='chicken',
                                                    sms_preference=True,
                                                    is_bazaargah_enjoyer=True
                                                )
                                                
                                                logger.debug(f"مشتری جدید ایجاد شد با شناسه: {customer.id}")
                                                
                                                # اضافه کردن کارشناس فروش به مشتری
                                                if super_agent:
                                                    logger.debug(f"افزودن کارشناس فروش {super_agent.id} به مشتری {customer.id}")
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
                                                shenase_takhsis=shenase_takhsis,
                                                code_melli_tahvil=code_melli_tahvil,
                                                tahvil_phone_number=tahvil_phone_number,
                                                bazaargah_phone_number=bazaargah_phone_number,
                                                address=address,
                                                weight=weight,
                                                cargo=bge_file.cargo,
                                                amount_paid=amount_paid,
                                                payment_method=payment_method,
                                                type='bazaargah',
                                                is_bazaargahed=True,
                                                is_takhsised=True if shenase_takhsis else False,
                                                company_price=bge_file.cargo.company_price,
                                                customer_price=bge_file.cargo.customer_price,
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
                
                # به‌روزرسانی لاگ پردازش
                processing_log.success = records_failed == 0
                processing_log.records_processed = records_processed
                processing_log.records_updated = records_updated
                processing_log.records_failed = records_failed
                log_message = f"تعداد کل رکوردها: {records_processed}\n"
                log_message += f"تعداد رکوردهای به‌روزرسانی شده: {records_updated}\n"
                log_message += f"تعداد رکوردهای ایجاد شده: {records_created}\n"
                log_message += f"تعداد رکوردهای ناموفق: {records_failed}\n"
                
                if error_messages:
                    log_message += "خطاها:\n" + "\n".join(error_messages)
                
                processing_log.log_message = log_message
                processing_log.save()
                
                # به‌روزرسانی وضعیت فایل
                bge_file.is_processed = True
                bge_file.save()
                
                messages.success(request, f"فایل با موفقیت پردازش شد. {records_updated} رکورد به‌روزرسانی شد و {records_created} رکورد جدید ایجاد شد.")
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

