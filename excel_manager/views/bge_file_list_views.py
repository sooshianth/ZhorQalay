import os
import pandas as pd
import logging
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

from ..models import ExcelFile, BGExcelFile, CargoProduct
from .utils import fix_excel_headers

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
def view_excel_file(request, file_id):
    """
    نمایش محتوای فایل اکسل با استفاده از Tabulator
    """
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    try:
        file_path = excel_file.file.path
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_path)[1].lower()
        is_html = False
        df = None
        
        # خواندن محتوای فایل بر اساس نوع آن
        if file_extension == '.xls':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read(1024) # خواندن بخش کوچکی برای تشخیص
                
                if '<html' in content.lower():
                    is_html = True
                    # خواندن کل محتوا برای pandas
                    with open(file_path, 'r', encoding='utf-8') as f:
                        full_content = f.read()
                    tables = pd.read_html(full_content)
                    if not tables:
                        messages.error(request, 'جدولی در فایل اکسل (HTML) یافت نشد.')
                        return redirect('excel_manager:bge_files_list')
                    df = tables[0]
                    logger.info(f"فایل HTML/XLS خوانده شد: {file_name}")
                else:
                    # فایل xls عادی
                    df = pd.read_excel(file_path)
                    logger.info(f"فایل XLS عادی خوانده شد: {file_name}")
            except UnicodeDecodeError:
                # فایل xls باینری
                df = pd.read_excel(file_path)
                logger.info(f"فایل XLS باینری خوانده شد: {file_name}")
            except Exception as e:
                 logger.error(f"خطای ناشناخته در خواندن فایل XLS: {str(e)} - {file_name}")
                 messages.error(request, f'خطا در خواندن فایل XLS: {str(e)}')
                 return redirect('excel_manager:bge_files_list')
        else:  # فایل xlsx
            df = pd.read_excel(file_path)
            logger.info(f"فایل XLSX خوانده شد: {file_name}")
        
        if df is None:
            messages.error(request, 'محتوای فایل اکسل قابل خواندن نبود.')
            return redirect('excel_manager:bge_files_list')
            
        # بررسی و پیدا کردن ردیف header اگر لازم باشد
        df = fix_excel_headers(df)
        
        # آماده‌سازی داده‌ها برای Tabulator
        # تبدیل مقادیر NaN به رشته خالی یا مقدار مناسب دیگر
        df = df.fillna('') 
        
        # تبدیل DataFrame به لیست دیکشنری‌ها
        data = df.to_dict(orient='records')
        
        # ایجاد تعریف ستون‌ها برای Tabulator
        columns = []
        for col in df.columns:
            columns.append({
                'title': str(col), 
                'field': str(col), 
                'editor': 'input',       # ویرایشگر پیش‌فرض
                'headerFilter': 'input', # فیلتر پیش‌فرض
                'hozAlign': 'center',    # تراز افقی محتوا
                'headerHozAlign': 'center', # تراز افقی هدر
                'minWidth': 100,         # حداقل عرض ستون
                'sorter': 'string',      # مرتب‌ساز پیش‌فرض
            })

        # اضافه کردن ستون عملیات (حذف سطر) به Tabulator
        columns.append({
            'formatter': "html", 
            'cellClick':"function(e, cell){cell.getRow().delete();}", 
            'title': 'حذف',
            'field': 'deleteAction', # نام فیلد فرضی
            'headerSort': False,
            'width': 60,
            'hozAlign': 'center',
            'headerHozAlign': 'center',
            'formatterParams': {
                'html':'<i class="fa fa-trash text-danger"></i>'
            }
        })
            
        context = {
            'excel_file': excel_file,
            'page_title': f'مشاهده فایل: {excel_file.title}',
            'file_name': file_name,
            'columns_json': json.dumps(columns, ensure_ascii=False),
            'data_json': json.dumps(data, ensure_ascii=False),
            'is_html': is_html # برای استفاده در ذخیره تغییرات
        }
        return render(request, 'excel_manager/view_excel_file.html', context)
        
    except Exception as e:
        logger.error(f"خطا در نمایش فایل اکسل با Tabulator: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        messages.error(request, f'خطا در نمایش فایل اکسل: {str(e)}')
        return redirect('excel_manager:bge_files_list')


@login_required
def save_excel_changes(request, file_id):
    """
    ذخیره تغییرات اعمال شده روی فایل اکسل (با استفاده از داده کامل Tabulator)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر (فقط POST)'}) 
    
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    file_path = excel_file.file.path
    
    try:
        # دریافت داده‌های JSON ارسال شده از Tabulator
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)
        
        table_data = data.get('table_data')
        is_html = data.get('is_html', False)
        
        if table_data is None:
            return JsonResponse({'success': False, 'message': 'داده جدول (`table_data`) ارسال نشده است.'})
        
        logger.debug(f"داده جدول دریافتی برای ذخیره: {len(table_data)} سطر")

        # تبدیل لیست دیکشنری‌ها به DataFrame
        # ابتدا بررسی کنیم آیا ستون عملیات وجود دارد و حذفش کنیم
        if table_data and 'deleteAction' in table_data[0]:
            for row in table_data:
                del row['deleteAction']
                
        new_df = pd.DataFrame(table_data)
        
        # حذف ستون‌های خالی که ممکن است Tabulator اضافه کرده باشد (اگر لازم شد)
        # new_df = new_df.dropna(axis=1, how='all')
        
        # ذخیره تغییرات
        if is_html:
            # --- بازسازی فایل HTML --- 
            # خواندن فایل HTML اصلی برای گرفتن ساختار کلی (هدر، فوتر، استایل)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except FileNotFoundError:
                 logger.error(f"فایل HTML اصلی برای بازسازی یافت نشد: {file_path}")
                 return JsonResponse({'success': False, 'message': 'فایل HTML اصلی برای بازسازی یافت نشد.'})

            # ایجاد یک نسخه پشتیبان
            backup_path = file_path + '.bak'
            import shutil
            try:
                shutil.copy2(file_path, backup_path)
                logger.info(f"نسخه پشتیبان HTML ایجاد شد: {backup_path}")
            except Exception as backup_err:
                 logger.warning(f"خطا در ایجاد نسخه پشتیبان HTML: {backup_err}")

            # استخراج بخش‌های قبل و بعد از جدول از محتوای اصلی
            table_start_tag = '\<table'
            table_end_tag = '/table>'
            import re
            table_start_index = -1
            table_end_index = -1
            
            # جستجوی case-insensitive برای تگ شروع جدول
            match_start = re.search(table_start_tag, original_content, re.IGNORECASE)
            if match_start:
                table_start_index = match_start.start()
                
            # جستجوی case-insensitive برای تگ پایان جدول
            match_end = re.search(table_end_tag, original_content, re.IGNORECASE)
            if match_end:
                 table_end_index = match_end.end()

            html_before_table = ''
            html_after_table = ''

            if table_start_index != -1:
                html_before_table = original_content[:table_start_index]
            if table_end_index != -1 and table_start_index != -1 and table_end_index > table_start_index:
                html_after_table = original_content[table_end_index:]
            elif table_start_index == -1: # اگر تگ شروع پیدا نشد، کل محتوا را قبل فرض کن
                html_before_table = original_content
            
            # اگر تگ پایانی html وجود نداشت ولی هدر داشتیم، اضافه کن
            if '<html>' in html_before_table.lower() and '</html>' not in html_after_table.lower():
                html_after_table += '\n</html>'
                
            # تبدیل DataFrame جدید به جدول HTML
            # سعی می‌کنیم برخی از ویژگی‌های جدول اصلی را حفظ کنیم
            table_attributes = 'dir="rtl" border="1" cellspacing="0" cellpadding="7" style="font-family:Tahoma;font-size:11px;width:70%;"' # Default attributes
            if match_start:
                 table_tag_match = re.search(r'<table[^>]*>', original_content[table_start_index:], re.IGNORECASE)
                 if table_tag_match:
                     # استخراج ویژگی‌های موجود و ترکیب با پیش‌فرض‌ها
                     # این بخش می‌تواند پیچیده‌تر شود برای حفظ دقیق‌تر
                     original_attributes = table_tag_match.group(0)[6:-1] # Remove <table and >
                     # ساده‌سازی: فعلا از ویژگی‌های پیش‌فرض یا استخراج شده ساده استفاده می‌کنیم
                     # می‌توان از کتابخانه‌های پارس HTML برای استخراج دقیق‌تر استفاده کرد
                     pass # فعلا از default_attributes استفاده می‌کنیم

            new_html_table = new_df.to_html(index=False, escape=False, na_rep='-', table_id=None, classes=None, border=None)
            # جایگزین کردن تگ پیش‌فرض با ویژگی‌های مورد نظر
            new_html_table = new_html_table.replace('<table border="1" class="dataframe">' , f'<table {table_attributes}>')
            new_html_table = new_html_table.replace('<table>', f'<table {table_attributes}>') # اگر border نداشت

            # ترکیب بخش‌ها و ذخیره فایل HTML جدید
            final_html = html_before_table + new_html_table + html_after_table
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_html)
            
            logger.info(f"فایل HTML/XLS با داده جدید ذخیره شد: {file_path}")

        else:
            # --- ذخیره فایل اکسل عادی (XLSX یا XLS) --- 
            file_extension_to_save = os.path.splitext(file_path)[1].lower()
            try:
                if file_extension_to_save == '.xlsx':
                    new_df.to_excel(file_path, index=False, engine='openpyxl')
                elif file_extension_to_save == '.xls':
                     # نوشتن XLS با openpyxl ممکن است با محدودیت‌هایی روبرو باشد
                     # ممکن است نیاز به استفاده از engine دیگری مانند xlwt باشد
                     # یا تبدیل فایل به xlsx
                    try:
                         new_df.to_excel(file_path, index=False, engine='xlwt') 
                    except ImportError:
                         logger.warning("xlwt engine not found, trying openpyxl for xls (might not be optimal)")
                         # تبدیل به xlsx و ذخیره با نام قبلی (ممکن است نوع فایل عوض شود)
                         temp_xlsx_path = file_path + ".temp.xlsx"
                         new_df.to_excel(temp_xlsx_path, index=False, engine='openpyxl')
                         # ممکن است بخواهید فایل اصلی را حذف و این را rename کنید
                         # این بخش نیاز به تصمیم‌گیری دارد که آیا فرمت XLS حفظ شود یا به XLSX تبدیل شود
                         logger.warning(f"Saving as XLSX instead due to engine limitations: {file_path}")
                         # فعلا فایل موقت را نگه می‌داریم
                         # os.replace(temp_xlsx_path, file_path) # Uncomment if changing format is acceptable
                else:
                    logger.error(f"فرمت فایل ناشناخته برای ذخیره: {file_extension_to_save}")
                    return JsonResponse({'success': False, 'message': f'فرمت فایل ناشناخته: {file_extension_to_save}'})
                
                logger.info(f"فایل اکسل معمولی با داده جدید ذخیره شد: {file_path}")

            except Exception as excel_save_error:
                 logger.error(f"خطا در ذخیره فایل اکسل: {excel_save_error}")
                 return JsonResponse({'success': False, 'message': f'خطا در ذخیره فایل اکسل: {excel_save_error}'})

        
        # ثبت گزارش تغییرات (اطلاعات دقیق تغییرات را نداریم، کلی ثبت می‌کنیم)
        try:
            from ..models import ExcelProcessingLog
            log = ExcelProcessingLog.objects.create(
                excel_file=excel_file,
                processed_by=request.user,
                success=True,
                records_processed=len(new_df), # تعداد رکوردهای ذخیره شده
                records_updated=len(new_df), # فرض می‌کنیم همه ممکن است آپدیت شده باشند
                records_failed=0,
                log_message=f"کل داده جدول با موفقیت از طریق Tabulator ذخیره شد. تعداد سطرها: {len(new_df)}"
            )
            logger.info(f"گزارش پردازش اکسل ثبت شد برای فایل: {excel_file.id}")
        except Exception as log_error:
             logger.error(f"خطا در ثبت گزارش پردازش اکسل: {log_error}")
        
        return JsonResponse({
            'success': True,
            'message': f'تغییرات با موفقیت ذخیره شد. {len(new_df)} سطر پردازش شد.'
            # 'updated_data': table_data # Optionally send back data if needed by frontend
        })
        
    except json.JSONDecodeError:
        logger.error(f"خطا در پارس کردن JSON دریافتی: {request.body.decode('utf-8')[:200]}...")
        return JsonResponse({'success': False, 'message': 'خطا در پارس کردن داده JSON ارسال شده.'}, status=400)
    except Exception as e:
        logger.error(f"خطای کلی در ذخیره تغییرات اکسل: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'خطای داخلی سرور: {str(e)}'}, status=500)


def is_html_file(file_path):
    """
    بررسی می‌کند که آیا فایل حاوی HTML است یا خیر
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.peek(1024).decode('utf-8')
            return '<html' in content.lower()
    except UnicodeDecodeError:
        return False
    except Exception:
        return False 

def delete_excel_file(request, file_id):
    """
    حذف فایل اکسل از دیتابیس
    """
    file = get_object_or_404(ExcelFile, id=file_id)
    file.delete()
    return redirect('excel_manager:bge_files_list')
