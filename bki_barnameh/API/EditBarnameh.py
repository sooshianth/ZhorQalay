from ..models.BarnamehModel import Barnameh
import jdatetime

def update_barnameh(barnameh_id, data):
    """
    Update a Barnameh object with new data
    
    Args:
        barnameh_id: ID of the Barnameh object to update
        data: Dictionary containing the fields to update
    
    Returns:
        dict: Result of the update operation
    """
    try:
        barnameh = Barnameh.objects.get(id=barnameh_id)
        
        # Check if barnameh is already sent to BKI
        if barnameh.is_sent_to_bki and not data.get('force_update', False):
            return {
                'success': False,
                'message': 'این بارنامه قبلاً به بازارگاه ارسال شده است و قابل ویرایش نیست.'
            }
        
        # Update fields
        if 'number' in data:
            barnameh.number = data['number']
        
        if 'serial' in data:
            barnameh.serial = data['serial']
        
        if 'tonnage' in data:
            barnameh.tonnage = data['tonnage']
        
        if 'driver_phone' in data:
            barnameh.driver_phone = data['driver_phone']
        
        if 'driver_name' in data:
            barnameh.driver_name = data['driver_name']
        
        if 'vehicle_plate' in data:
            barnameh.vehicle_plate = data['vehicle_plate']
        
        if 'receiver_name' in data:
            barnameh.receiver_name = data['receiver_name']
        
        if 'destination' in data:
            barnameh.destination = data['destination']
        
        if 'barnameh_date' in data:
            try:
                if isinstance(data['barnameh_date'], str):
                    # Assuming format is like '1402/01/01'
                    parts = data['barnameh_date'].split('/')
                    if len(parts) == 3:
                        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                        barnameh.barnameh_date = jdatetime.date(year, month, day)
                else:
                    barnameh.barnameh_date = data['barnameh_date']
            except Exception as e:
                return {
                    'success': False,
                    'message': f'خطا در تبدیل تاریخ: {str(e)}'
                }
        
        if 'purchase_number' in data:
            barnameh.purchase_number = data['purchase_number']
        
        if 'shenase_takhsis_code' in data:
            barnameh.shenase_takhsis_code = data['shenase_takhsis_code']
        
        # Check if barnameh is complete
        if all([barnameh.number, barnameh.serial, barnameh.tonnage]):
            barnameh.status = 'BARNAMEH_COMPLETE'
        else:
            barnameh.status = 'BARNAMEH_INCOMPLETE'
        
        barnameh.save()
        
        return {
            'success': True,
            'message': 'بارنامه با موفقیت بروزرسانی شد.',
            'barnameh': barnameh
        }
        
    except Barnameh.DoesNotExist:
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'خطا در بروزرسانی بارنامه: {str(e)}'
        }

def delete_barnameh(barnameh_id):
    """
    Delete a Barnameh object
    
    Args:
        barnameh_id: ID of the Barnameh object to delete
    
    Returns:
        dict: Result of the delete operation
    """
    try:
        barnameh = Barnameh.objects.get(id=barnameh_id)
        
        # Check if barnameh is already sent to BKI
        if barnameh.is_sent_to_bki:
            return {
                'success': False,
                'message': 'این بارنامه قبلاً به بازارگاه ارسال شده است و قابل حذف نیست.'
            }
        
        barnameh.delete()
        
        return {
            'success': True,
            'message': 'بارنامه با موفقیت حذف شد.'
        }
        
    except Barnameh.DoesNotExist:
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        return {
            'success': False,
            'message': f'خطا در حذف بارنامه: {str(e)}'
        }
