import pandas as pd
import os
from django.conf import settings
from ..models.ExcelFileModel import ExcelFile
from ..models.BarnamehModel import Barnameh
from django.utils import timezone
from django_jalali.db import models as jmodels
import jdatetime
import logging

logger = logging.getLogger('bki_barnameh_upload_excel')

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

def clean_numeric_value(value):
    """
    تبدیل اعداد اعشاری به صحیح (بدون اعشار) و تبدیل به رشته
    """
    if pd.isna(value) or value == '':
        return ''
        
    try:
        # اگر عدد اعشاری باشد، اعشار آن را حذف می‌کنیم
        if isinstance(value, (int, float)):
            return str(int(value))
        # اگر رشته باشد که حاوی عدد اعشاری است، آن را تبدیل می‌کنیم
        elif isinstance(value, str) and '.' in value and value.replace('.', '', 1).isdigit():
            try:
                return str(int(float(value)))
            except:
                return value
        # در غیر این صورت، همان مقدار را برمی‌گردانیم
        return str(value)
    except:
        # در صورت بروز خطا، همان مقدار را به صورت رشته برمی‌گردانیم
        return str(value) if value is not None else ''

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
        updated_rows = 0  # Counter for updated duplicate rows
        duplicate_numbers = []  # List to store duplicate barnameh numbers
        
        for index, row in df.iterrows():
            try:
                # Extract data from Excel row and clean numeric values
                barnameh_number = clean_numeric_value(row.get('شماره بارنامه', ''))
                barnameh_serial = str(row.get('سریال بارنامه', ''))
                
                # تبدیل وزن به عدد با حفظ دقت اعشار (اگر لازم باشد)
                tonnage_raw = row.get('وزن', 0)
                if pd.isna(tonnage_raw):
                    tonnage = 0
                else:
                    try:
                        tonnage = float(tonnage_raw)
                    except:
                        tonnage = 0
                
                driver_phone = str(row.get('شماره تلفن راننده', ''))
                driver_name = str(row.get('نام راننده', ''))
                vehicle_plate = str(row.get('پلاک خودرو', ''))
                receiver_name = str(row.get('نام گیرنده', ''))
                destination = str(row.get('مقصد', ''))
                barnameh_date_str = row.get('تاریخ بارنامه', '')
                
                # پاکسازی شناسه خرید و شناسه تخصیص
                purchase_number = clean_numeric_value(row.get('شناسه خرید', ''))
                shenase_takhsis_code = clean_numeric_value(row.get('شناسه تخصیص', ''))
                
                # Convert date string to JDate
                barnameh_date = None
                if barnameh_date_str:
                    try:
                        if isinstance(barnameh_date_str, str):
                            # Assuming format is like '1402/01/01' or '02/01/01'
                            parts = barnameh_date_str.split('/')
                            if len(parts) == 3:
                                year = int(parts[0])
                                # If year is less than 100, assume it's a short year format
                                if year < 100:
                                    # Convert to full year format (e.g., 04 -> 1404)
                                    year = 1400 + year
                                month = int(parts[1])
                                day = int(parts[2])
                                barnameh_date = jdatetime.date(year, month, day)
                    except Exception as e:
                        logger.error(f"Error parsing date in excel file: {e}")
                
                # Check if barnameh with this number already exists
                existing_barnameh = None
                if barnameh_number:
                    try:
                        existing_barnameh = Barnameh.objects.get(number=barnameh_number)
                        # Record as duplicate for reporting
                        duplicate_numbers.append(barnameh_number)
                        updated_rows += 1
                    except Barnameh.DoesNotExist:
                        existing_barnameh = None
                
                # Create new or update existing Barnameh object
                barnameh_data = {
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
                
                if existing_barnameh:
                    # Update existing barnameh with new data
                    for key, value in barnameh_data.items():
                        setattr(existing_barnameh, key, value)
                    existing_barnameh.save()
                    barnameh = existing_barnameh
                else:
                    # Create new barnameh
                    barnameh = Barnameh.objects.create(
                        number=barnameh_number,
                        **barnameh_data
                    )

                from core.PurchaseModel import Purchase
                # Only try to associate with purchase if purchase_number is not empty or just whitespace
                if purchase_number and purchase_number.strip() and barnameh:
                    try:
                        # استفاده از شناسه خرید تمیز شده
                        purchase = Purchase.objects.get(purchase_number=purchase_number)
                        purchase.barnameh = barnameh_number
                        purchase.barnameh_object = barnameh
                        purchase.save()
                    except Purchase.DoesNotExist:
                        logger.error(f"Purchase with number {purchase_number} not found")
                        # Continue processing without failing

                processed_rows += 1
                
            except Exception as e:
                logger.error(f"Error processing row {index}: {e}")
                continue
        
        # Update the processed rows count and add duplicate info
        excel_file.processed_rows = processed_rows
        excel_file.processed = True
        excel_file.debug_info = f"تعداد بارنامه‌های بروزرسانی شده: {updated_rows}\nشماره بارنامه‌های بروزرسانی شده: {', '.join(duplicate_numbers)}"
        logger.warning(f"Excel file {excel_file.name} processed successfully. تعداد بارنامه‌های بروزرسانی شده: {updated_rows}\nشماره بارنامه‌های بروزرسانی شده: {', '.join(duplicate_numbers)}")
        excel_file.save()
        
        return {
            'success': True,
            'message': f'فایل با موفقیت پردازش شد. {processed_rows} از {excel_file.rows_count} ردیف پردازش شدند. {updated_rows} بارنامه به دلیل تکراری بودن بروزرسانی شدند.',
            'processed_rows': processed_rows,
            'updated_rows': updated_rows,
            'total_rows': excel_file.rows_count,
            'duplicate_numbers': duplicate_numbers
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
