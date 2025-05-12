import pandas as pd
import os
from django.conf import settings
from ..models.ExcelFileModel import ExcelFile
from ..models.BarnamehModel import Barnameh
from django.utils import timezone
from django_jalali.db import models as jmodels
import jdatetime

def handle_uploaded_file(file, file_name):
    """
    Handle the uploaded Excel file and save it to the server
    """
    excel_file = ExcelFile(
        file=file,
        name=file_name
    )
    excel_file.save()
    return excel_file

def process_excel_file(excel_file_id):
    """
    Process the uploaded Excel file and create Barnameh objects
    """
    try:
        excel_file = ExcelFile.objects.get(id=excel_file_id)
        
        # Read the Excel file
        file_path = os.path.join(settings.MEDIA_ROOT, excel_file.file.name)
        df = pd.read_excel(file_path)
        
        # Update the rows count
        excel_file.rows_count = len(df)
        excel_file.save()
        
        # Process each row
        processed_rows = 0
        for index, row in df.iterrows():
            try:
                # Extract data from Excel row
                barnameh_number = str(row.get('شماره بارنامه', ''))
                barnameh_serial = str(row.get('سریال بارنامه', ''))
                tonnage = float(row.get('وزن', 0))
                driver_phone = str(row.get('شماره تلفن راننده', ''))
                driver_name = str(row.get('نام راننده', ''))
                vehicle_plate = str(row.get('پلاک خودرو', ''))
                receiver_name = str(row.get('نام گیرنده', ''))
                destination = str(row.get('مقصد', ''))
                barnameh_date_str = row.get('تاریخ بارنامه', '')
                purchase_number = str(row.get('شناسه خرید', ''))
                shenase_takhsis_code = str(row.get('شناسه تخصیص', ''))
                
                # Convert date string to JDate
                barnameh_date = None
                if barnameh_date_str:
                    try:
                        if isinstance(barnameh_date_str, str):
                            # Assuming format is like '1402/01/01'
                            parts = barnameh_date_str.split('/')
                            if len(parts) == 3:
                                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                                barnameh_date = jdatetime.date(year, month, day)
                    except Exception as e:
                        print(f"Error parsing date: {e}")
                
                # Create or update Barnameh object
                barnameh, created = Barnameh.objects.update_or_create(
                    number=barnameh_number,
                    defaults={
                        'serial': barnameh_serial,
                        'tonnage': tonnage,
                        'driver_phone': driver_phone,
                        'driver_name': driver_name,
                        'vehicle_plate': vehicle_plate,
                        'receiver_name': receiver_name,
                        'destination': destination,
                        'barnameh_date': barnameh_date,
                        'purchase_number': purchase_number,
                        'shenase_takhsis_code': shenase_takhsis_code,
                        'is_created_by_excel': True,
                        'status': 'BARNAMEH_COMPLETE' if all([barnameh_number, barnameh_serial, tonnage]) else 'BARNAMEH_INCOMPLETE'
                    }
                )

                from core.PurchaseModel import Purchase
                if purchase_number and barnameh:
                    purchase=Purchase.objects.get(purchase_number=purchase_number)
                    purchase.barnameh=barnameh_number
                    purchase.barnameh_object=barnameh
                    purchase.save()

                processed_rows += 1
                
            except Exception as e:
                print(f"Error processing row {index}: {e}")
                continue
        
        # Update the processed rows count
        excel_file.processed_rows = processed_rows
        excel_file.processed = True
        excel_file.save()
        
        return {
            'success': True,
            'message': f'فایل با موفقیت پردازش شد. {processed_rows} از {excel_file.rows_count} ردیف پردازش شدند.',
            'processed_rows': processed_rows,
            'total_rows': excel_file.rows_count
        }
        
    except ExcelFile.DoesNotExist:
        return {
            'success': False,
            'message': 'فایل اکسل یافت نشد.'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'خطا در پردازش فایل: {str(e)}'
        }
