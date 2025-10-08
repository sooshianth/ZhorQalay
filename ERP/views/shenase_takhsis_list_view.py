from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from core.decorators.decorators import role_required
from core.PurchaseModel import ShenaseTakhsis
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import json


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def shenase_takhsis_list(request):
    """
    نمایش لیست شناسه‌های تخصیص
    هر شناسه تخصیص در یک سطر جداگانه نمایش داده می‌شود
    """
    # دریافت تمام شناسه‌های تخصیص و مرتب‌سازی بر اساس تاریخ ایجاد
    shenase_list = ShenaseTakhsis.objects.select_related(
        'purchase',
        'purchase__customer',
        'purchase__cargo',
        'purchase__unique_sales_agent'
    ).all().order_by('-created_at')
    
    # جستجو
    search_query = request.GET.get('search', '').strip()
    if search_query:
        shenase_list = shenase_list.filter(
            Q(code__icontains=search_query) |
            Q(purchase_number__icontains=search_query) |
            Q(purchase__invoice_id__icontains=search_query) |
            Q(purchase__customer__name__icontains=search_query) |
            Q(code_melli_tahvil__icontains=search_query) |
            Q(tahvil_phone_number__icontains=search_query) |
            Q(delivery_receiver_name__icontains=search_query)
        )
    
    # فیلتر بر اساس خرید خاص (اگر در URL مشخص شده باشد)
    purchase_id = request.GET.get('purchase_id')
    if purchase_id:
        shenase_list = shenase_list.filter(purchase_id=purchase_id)
    
    # صفحه‌بندی
    page_number = request.GET.get('page', 1)
    paginator = Paginator(shenase_list, 50)  # 50 آیتم در هر صفحه
    page_obj = paginator.get_page(page_number)
    
    context = {
        'shenase_list': page_obj,
        'total_count': shenase_list.count(),
        'search_query': search_query,
        'page_obj': page_obj,
    }
    
    return render(request, 'shenase_takhsis_list.html', context)


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
def export_shenase_takhsis_excel(request):
    """
    خروجی اکسل شناسه‌های تخصیص انتخاب شده
    """
    try:
        data = json.loads(request.body)
        selected_ids = data.get('selected_ids', [])
        
        if not selected_ids:
            return JsonResponse({'status': 'error', 'message': 'هیچ شناسه تخصیصی انتخاب نشده است'})
        
        # دریافت شناسه‌های تخصیص انتخاب شده
        shenase_list = ShenaseTakhsis.objects.filter(id__in=selected_ids).select_related(
            'purchase',
            'purchase__customer',
            'purchase__cargo',
            'purchase__unique_sales_agent'
        ).order_by('-created_at')
        
        # ایجاد فایل اکسل
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "شناسه‌های تخصیص"
        
        # تنظیم راست به چپ برای worksheet
        ws.sheet_view.rightToLeft = True
        
        # تنظیمات استایل
        header_fill = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")
        header_font = Font(name='B Nazanin', size=12, bold=True, color="FFFFFF")
        cell_font = Font(name='B Nazanin', size=11)
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # هدرهای جدول
        headers = [
            'ردیف',
            'شناسه تخصیص',
            'شماره خرید',
            'کد درون سازمانی',
            'نام مشتری',
            'وزن (کیلوگرم)',
            'کد ملی تحویل',
            'شماره تلفن تحویل',
            'نام تحویل گیرنده',
            'آدرس تحویل',
            'کد پستی',
            'تاریخ ثبت'
        ]
        
        # نوشتن هدرها
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = border
        
        # نوشتن داده‌ها
        for row_num, shenase in enumerate(shenase_list, 2):
            data_row = [
                row_num - 1,
                shenase.code or '—',
                shenase.purchase.purchase_number if shenase.purchase else (shenase.purchase_number or '—'),
                shenase.purchase.invoice_id if shenase.purchase else '—',
                shenase.purchase.customer.name if (shenase.purchase and shenase.purchase.customer) else '—',
                shenase.weight or 0,
                shenase.code_melli_tahvil or '—',
                shenase.tahvil_phone_number or '—',
                shenase.delivery_receiver_name or '—',
                shenase.delivery_address or '—',
                shenase.delivery_postal_code or '—',
                shenase.created_at.strftime('%Y/%m/%d %H:%M') if shenase.created_at else '—'
            ]
            
            for col_num, value in enumerate(data_row, 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = value
                cell.font = cell_font
                cell.alignment = center_alignment
                cell.border = border
        
        # تنظیم عرض ستون‌ها
        column_widths = [8, 20, 15, 15, 25, 15, 15, 15, 20, 35, 12, 18]
        for col_num, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_num)].width = width
        
        # ذخیره فایل
        filename = f'shenase_takhsis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد فایل اکسل: {str(e)}'})


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def export_full_shenase_takhsis_excel(request):
    """
    خروجی اکسل کامل تمام شناسه‌های تخصیص
    """
    try:
        # دریافت تمام شناسه‌های تخصیص
        shenase_list = ShenaseTakhsis.objects.select_related(
            'purchase',
            'purchase__customer',
            'purchase__cargo',
            'purchase__unique_sales_agent'
        ).all().order_by('-created_at')
        
        # اعمال فیلتر جستجو اگر وجود دارد
        search_query = request.GET.get('search', '').strip()
        if search_query:
            shenase_list = shenase_list.filter(
                Q(code__icontains=search_query) |
                Q(purchase_number__icontains=search_query) |
                Q(purchase__invoice_id__icontains=search_query) |
                Q(purchase__customer__name__icontains=search_query) |
                Q(code_melli_tahvil__icontains=search_query) |
                Q(tahvil_phone_number__icontains=search_query) |
                Q(delivery_receiver_name__icontains=search_query)
            )
        
        # فیلتر بر اساس خرید خاص
        purchase_id = request.GET.get('purchase_id')
        if purchase_id:
            shenase_list = shenase_list.filter(purchase_id=purchase_id)
        
        # ایجاد فایل اکسل
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "شناسه‌های تخصیص"
        
        # تنظیم راست به چپ برای worksheet
        ws.sheet_view.rightToLeft = True
        
        # تنظیمات استایل
        header_fill = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")
        header_font = Font(name='B Nazanin', size=12, bold=True, color="FFFFFF")
        cell_font = Font(name='B Nazanin', size=11)
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # هدرهای جدول
        headers = [
            'ردیف',
            'شناسه تخصیص',
            'شماره خرید',
            'کد درون سازمانی',
            'نام مشتری',
            'وزن (کیلوگرم)',
            'کد ملی تحویل',
            'شماره تلفن تحویل',
            'نام تحویل گیرنده',
            'آدرس تحویل',
            'کد پستی',
            'تاریخ ثبت'
        ]
        
        # نوشتن هدرها
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = border
        
        # نوشتن داده‌ها
        for row_num, shenase in enumerate(shenase_list, 2):
            data_row = [
                row_num - 1,
                shenase.code or '—',
                shenase.purchase.purchase_number if shenase.purchase else (shenase.purchase_number or '—'),
                shenase.purchase.invoice_id if shenase.purchase else '—',
                shenase.purchase.customer.name if (shenase.purchase and shenase.purchase.customer) else '—',
                shenase.weight or 0,
                shenase.code_melli_tahvil or '—',
                shenase.tahvil_phone_number or '—',
                shenase.delivery_receiver_name or '—',
                shenase.delivery_address or '—',
                shenase.delivery_postal_code or '—',
                shenase.created_at.strftime('%Y/%m/%d %H:%M') if shenase.created_at else '—'
            ]
            
            for col_num, value in enumerate(data_row, 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = value
                cell.font = cell_font
                cell.alignment = center_alignment
                cell.border = border
        
        # تنظیم عرض ستون‌ها
        column_widths = [8, 20, 15, 15, 25, 15, 15, 15, 20, 35, 12, 18]
        for col_num, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_num)].width = width
        
        # ذخیره فایل
        filename = f'shenase_takhsis_full_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return HttpResponse(f'خطا در ایجاد فایل اکسل: {str(e)}', status=500)
