import os
import pandas as pd
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.conf import settings
from django.utils import timezone

from ..models import BGExcelFile, CargoProduct
from .utils import fix_excel_headers
from core.decorators.decorators import role_required
# ایجاد یک لاگر برای دیباگ
logger = logging.getLogger(__name__)


@role_required('admin', 'logistics_manager', 'financial_manager')
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


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def approve_bge_file(request, file_id):
    """
    تایید فایل اکسل بازارگاه توسط کارشناسان لجستیک
    """
    # بررسی دسترسی کاربر
    if not hasattr(request.user, 'logistics_manager'):
        messages.error(request, 'شما دسترسی لازم برای تایید فایل اکسل را ندارید.')
        return redirect('excel_manager:bge_files_list')
    
    # بازیابی فایل
    file_obj = get_object_or_404(BGExcelFile, id=file_id)
    
    if request.method == 'POST':
        # تایید فایل
        file_obj.is_approved = True
        file_obj.approved_by = request.user
        file_obj.approved_at = timezone.now()
        file_obj.save()
        
        messages.success(request, 'فایل با موفقیت تایید شد.')
        return redirect('excel_manager:bge_files_list')
    
    # نمایش صفحه تایید
    context = {
        'excel_file': file_obj,
        'page_title': 'تایید فایل اکسل بازارگاه'
    }
    return render(request, 'excel_manager/approve_bge_file.html', context) 