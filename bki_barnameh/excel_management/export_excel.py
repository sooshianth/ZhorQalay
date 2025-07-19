import pandas as pd
from django.http import HttpResponse
from ..models.BarnamehModel import Barnameh
import datetime
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

def export_to_excel(barnameh_ids=None):
    """
    Export Barnameh objects to Excel file (completely simple version without any styling)
    
    Args:
        barnameh_ids: List of Barnameh IDs to export, if None export all
    
    Returns:
        HttpResponse: Excel file as response
    """
    try:
        if barnameh_ids:
            barnamehs = Barnameh.objects.filter(id__in=barnameh_ids).order_by('-barnameh_created_at')
        else:
            barnamehs = Barnameh.objects.all().order_by('-barnameh_created_at')
        
        # Create DataFrame
        data = []
        for barnameh in barnamehs:
            data.append({
                'شماره بارنامه': barnameh.number,
                'سریال بارنامه': barnameh.serial,
                'وزن': barnameh.tonnage,
                'شماره تلفن راننده': barnameh.driver_phone,
                'نام راننده': barnameh.driver_name,
                'پلاک خودرو': barnameh.vehicle_plate,
                'نام گیرنده': barnameh.receiver_name,
                'مقصد': barnameh.destination,
                'تاریخ بارنامه': barnameh.barnameh_date,
                'شناسه خرید': barnameh.purchase_number,
                'شناسه تخصیص': barnameh.shenase_takhsis_code,
                'وضعیت': dict(Barnameh.STATUS_CHOICES).get(barnameh.status, ''),
                'ارسال به بازارگاه': 'بله' if barnameh.is_sent_to_bki else 'خیر',
                'تاریخ ارسال به بازارگاه': barnameh.is_sent_to_bki_at,
            })
        
        df = pd.DataFrame(data)
        
        # Create HTTP response with Excel file
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=barnamehs_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        # Create workbook and worksheet manually to avoid any styling
        wb = Workbook()
        ws = wb.active
        ws.title = 'بارنامه‌ها'
        
        # Add headers
        headers = list(df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            # Remove any styling from header cells
            cell.font = None
            cell.fill = None
            cell.border = None
            cell.alignment = None
        
        # Add data rows
        for row_idx, row_data in enumerate(df.values, 2):
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                # Remove any styling from data cells
                cell.font = None
                cell.fill = None
                cell.border = None
                cell.alignment = None
        
        # Save to response
        wb.save(response)
        return response
        
    except Exception as e:
        # In case of error, return empty Excel file with error message
        wb = Workbook()
        ws = wb.active
        ws.title = 'خطا'
        
        cell = ws.cell(row=1, column=1, value=f'خطا در ایجاد فایل اکسل: {str(e)}')
        cell.font = None
        cell.fill = None
        cell.border = None
        cell.alignment = None
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        wb.save(response)
        return response
