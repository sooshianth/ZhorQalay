import os
import pandas as pd
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages

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
    نمایش محتوای فایل اکسل در مرورگر بدون نیاز به دانلود
    """
    # بازیابی فایل
    excel_file = get_object_or_404(ExcelFile, id=file_id)
    
    try:
        file_path = excel_file.file.path
        file_name = os.path.basename(file_path)
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # خواندن محتوای فایل بر اساس نوع آن
        if file_extension == '.xls':
            try:
                # بررسی اگر فایل xls حاوی HTML است
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if '<html' in content.lower():
                    # اگر فایل حاوی HTML است، آن را به عنوان یک DataFrame بخوان
                    tables = pd.read_html(content)
                    if not tables:
                        messages.error(request, 'جدولی در فایل اکسل یافت نشد.')
                        return redirect('excel_manager:bge_files_list')
                    df = tables[0]
                    
                    # برگرداندن مستقیم محتوای HTML با استایل‌های لازم
                    # حذف اسکریپت‌ها و محتوای غیر امن
                    safe_content = content.replace('<script', '<!-- script').replace('</script>', '</script -->')
                    
                    context = {
                        'excel_file': excel_file,
                        'page_title': f'مشاهده فایل: {excel_file.title}',
                        'html_content': safe_content,
                        'is_html_file': True
                    }
                    return render(request, 'excel_manager/view_excel_file.html', context)
                else:
                    # فایل xls عادی است
                    df = pd.read_excel(file_path)
            except UnicodeDecodeError:
                # فایل باینری است
                df = pd.read_excel(file_path)
        else:  # فایل xlsx
            df = pd.read_excel(file_path)
        
        # بررسی و پیدا کردن ردیف header اگر لازم باشد
        df = fix_excel_headers(df)
        
        # تبدیل DataFrame به HTML
        html_table = df.to_html(index=False, classes='table table-striped table-bordered table-hover', 
                               escape=False, na_rep='-', table_id='excel-table')
        
        context = {
            'excel_file': excel_file,
            'page_title': f'مشاهده فایل: {excel_file.title}',
            'file_name': file_name,
            'html_table': html_table,
            'is_html_file': False
        }
        return render(request, 'excel_manager/view_excel_file.html', context)
        
    except Exception as e:
        logger.error(f"خطا در نمایش فایل اکسل: {str(e)}")
        messages.error(request, f'خطا در نمایش فایل اکسل: {str(e)}')
        return redirect('excel_manager:bge_files_list') 