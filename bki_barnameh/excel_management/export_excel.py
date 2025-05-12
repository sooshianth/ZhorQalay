import pandas as pd
import os
from django.conf import settings
from django.http import HttpResponse
from ..models.BarnamehModel import Barnameh
import datetime

def export_to_excel(barnameh_ids=None):
    """
    Export Barnameh objects to Excel file
    
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
                'وزن': float(barnameh.tonnage) if barnameh.tonnage else None,
                'شماره تلفن راننده': barnameh.driver_phone,
                'نام راننده': barnameh.driver_name,
                'پلاک خودرو': barnameh.vehicle_plate,
                'نام گیرنده': barnameh.receiver_name,
                'مقصد': barnameh.destination,
                'تاریخ بارنامه': str(barnameh.barnameh_date) if barnameh.barnameh_date else None,
                'شناسه خرید': barnameh.purchase_number,
                'شناسه تخصیص': barnameh.shenase_takhsis_code,
                'وضعیت': dict(Barnameh.STATUS_CHOICES).get(barnameh.status, ''),
                'ارسال به بازارگاه': 'بله' if barnameh.is_sent_to_bki else 'خیر',
                'تاریخ ارسال به بازارگاه': str(barnameh.is_sent_to_bki_at) if barnameh.is_sent_to_bki_at else None,
            })
        
        df = pd.DataFrame(data)
        
        # Create HTTP response with Excel file
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=barnamehs_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        # Write DataFrame to Excel
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='بارنامه‌ها')
            
            # Auto-adjust columns' width
            worksheet = writer.sheets['بارنامه‌ها']
            for i, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + i)].width = max_length
        
        return response
        
    except Exception as e:
        # In case of error, return empty Excel file with error message
        df = pd.DataFrame([{'خطا': f'خطا در ایجاد فایل اکسل: {str(e)}'}])
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='خطا')
        
        return response
