from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
from core.decorators.decorators import role_required
from .upload_excel import handle_uploaded_file, process_excel_file
from .export_excel import export_to_excel
import logging

logger = logging.getLogger("bki_barnameh_excel_management")

def get_client_ip(request):
    """
    دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
    """
    if not request:
        return "Unknown"
        
    # IP مستقیم (از سرور دیده می‌شود)
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
    # IP از طریق proxy headers
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')

    # انتخاب IP اصلی
    client_ip = direct_ip
    if forwarded_for:
        # اولین IP در لیست X-Forwarded-For
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
        
    # اگر proxy وجود دارد، هر دو IP را نمایش بده
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
        
    return f"{client_ip}-{proxy_info}"

@role_required('logistics_manager', 'admin')
def upload_excel_view(request):
    """
    آپلود فایل اکسل بارنامه
    """
    if request.method == 'POST' and request.FILES.get('excel_file'):
        logger.warning(f"آپلود فایل اکسل بارنامه: {get_client_ip(request)}, user: {request.user}")
        excel_file = request.FILES['excel_file']
        
        # Check if file is Excel
        if not excel_file.name.endswith(('.xls', '.xlsx')):
            messages.error(request, 'فایل باید با فرمت اکسل (.xls یا .xlsx) باشد.')
            return redirect('upload_excel')
        
        # Handle file upload
        excel_file_obj = handle_uploaded_file(excel_file, excel_file.name)
        
        # Process Excel file
        result = process_excel_file(excel_file_obj.id)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        return redirect('barnameh_list')
    
    return render(request, 'bki_barnameh/upload_excel.html')

@role_required('logistics_manager', 'admin', 'financial_manager')
def download_excel_template(request):
    """
    دانلود قالب اکسل بارنامه
    """
    import pandas as pd
    import os
    from django.conf import settings

    # Create template DataFrame
    template_data = {
        'شماره بارنامه': [''],
        'سریال بارنامه': [''],
        'وزن': [''],
        'شماره تلفن راننده': [''],
        'نام راننده': [''],
        'پلاک خودرو': [''],
        'نام گیرنده': [''],
        'مقصد': [''],
        'تاریخ بارنامه': ['1402/01/01'],
        'شناسه خرید': [''],
        'شناسه تخصیص': [''],
    }
    
    df = pd.DataFrame(template_data)
    
    # Create HTTP response with Excel file
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=barnameh_template.xlsx'
    
    # Write DataFrame to Excel
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='قالب بارنامه')
        
        # Auto-adjust columns' width
        worksheet = writer.sheets['قالب بارنامه']
        for i, col in enumerate(df.columns):
            worksheet.column_dimensions[chr(65 + i)].width = len(col) + 5
    
    return response

@role_required('logistics_manager', 'admin', 'financial_manager')
def export_excel_view(request):
    """
    خروجی اکسل از بارنامه‌ها
    """
    logger.warning(f"خروجی اکسل از بارنامه‌ها: {get_client_ip(request)}, user: {request.user}")
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        return export_to_excel(barnameh_ids)
    
    # If GET request or no barnameh_ids, export all
    return export_to_excel() 