from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models.BarnamehModel import Barnameh
from .models.ExcelFileModel import ExcelFile
from .models.ApiLogModel import BKIApiLog
from core.decorators.decorators import role_required
from .API.insertBarnameh import send_barnameh_to_bki, send_multiple_barnameh_to_bki
from .API.EditBarnameh import edit_barnameh_api
import json
import os
from django.conf import settings
import pandas as pd
import jdatetime

# توابع اکسل به فولدر excel_management منتقل شده‌اند
from .excel_management.views import upload_excel_view, download_excel_template, export_excel_view

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

@role_required('logistics_manager', 'admin', 'financial_manager')
def barnameh_list(request):
    """
    نمایش لیست بارنامه ها
    """
    barnamehs = Barnameh.objects.all().order_by('-barnameh_created_at')
    return render(request, 'bki_barnameh/barnameh_list.html', {'barnamehs': barnamehs})

@role_required('logistics_manager', 'admin')
def barnameh_detail(request, barnameh_id):
    """
    نمایش جزئیات بارنامه
    """
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/barnameh_detail.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def barnameh_create(request):
    """
    ایجاد بارنامه جدید
    """
    if request.method == 'POST':
        data = {
            'number': request.POST.get('number'),
            'serial': request.POST.get('serial'),
            'tonnage': request.POST.get('tonnage'),
            'driver_phone': request.POST.get('driver_phone'),
            'driver_name': request.POST.get('driver_name'),
            'vehicle_plate': request.POST.get('vehicle_plate'),
            'receiver_name': request.POST.get('receiver_name'),
            'destination': request.POST.get('destination'),
            'barnameh_date': request.POST.get('barnameh_date'),
            'purchase_number': request.POST.get('purchase_number'),
            'shenase_takhsis_code': request.POST.get('shenase_takhsis_code'),
        }
        
        barnameh = Barnameh.objects.create(
            number=data['number'],
            serial=data['serial'],
            tonnage=data['tonnage'] if data['tonnage'] else None,
            driver_phone=data['driver_phone'],
            driver_name=data['driver_name'],
            vehicle_plate=data['vehicle_plate'],
            receiver_name=data['receiver_name'],
            destination=data['destination'],
            barnameh_date=data['barnameh_date'] if data['barnameh_date'] else None,
            purchase_number=data['purchase_number'],
            shenase_takhsis_code=data['shenase_takhsis_code'],
            status='BARNAMEH_COMPLETE' if all([data['number'], data['serial'], data['tonnage']]) else 'BARNAMEH_INCOMPLETE'
        )
        
        messages.success(request, 'بارنامه با موفقیت ایجاد شد.')
        return redirect('barnameh_detail', barnameh_id=barnameh.id)
    
    return render(request, 'bki_barnameh/barnameh_create.html')

@role_required('logistics_manager', 'admin')
def barnameh_edit(request, barnameh_id):
    """
    ویرایش بارنامه
    """
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    
    if request.method == 'POST':
        data = {
            'number': request.POST.get('number'),
            'serial': request.POST.get('serial'),
            'tonnage': request.POST.get('tonnage'),
            'driver_phone': request.POST.get('driver_phone'),
            'driver_name': request.POST.get('driver_name'),
            'vehicle_plate': request.POST.get('vehicle_plate'),
            'receiver_name': request.POST.get('receiver_name'),
            'destination': request.POST.get('destination'),
            'barnameh_date': request.POST.get('barnameh_date'),
            'purchase_number': request.POST.get('purchase_number'),
            'shenase_takhsis_code': request.POST.get('shenase_takhsis_code'),
        }
        
        result = update_barnameh(barnameh_id, data)
        barnameh.log_barnameh_edit(request)
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('barnameh_detail', barnameh_id=barnameh.id)
        else:
            messages.error(request, result['message'])
    
    return render(request, 'bki_barnameh/barnameh_edit.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def barnameh_delete(request, barnameh_id):
    """
    حذف بارنامه
    """
    if request.method == 'POST':
        result = delete_barnameh(barnameh_id)
        
        if result['success']:
            messages.success(request, result['message'])
            return redirect('barnameh_list')
        else:
            messages.error(request, result['message'])
            return redirect('barnameh_detail', barnameh_id=barnameh_id)
    
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/barnameh_delete.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def upload_excel(request):
    """
    آپلود فایل اکسل بارنامه - ریدایرکت به ویو جدید
    """
    return upload_excel_view(request)

@role_required('logistics_manager', 'admin', 'financial_manager')
def export_excel(request):
    """
    خروجی اکسل از بارنامه‌ها
    """
    return export_excel_view(request)

@role_required('logistics_manager', 'admin')
def send_to_bki(request, barnameh_id):
    """
    ارسال بارنامه به بازارگاه
    """
    if request.method == 'POST':
        result = send_barnameh_to_bki(barnameh_id)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        return redirect('barnameh_detail', barnameh_id=barnameh_id)
    
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/send_to_bki.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def bulk_send_to_bki(request):
    """
    ارسال گروهی بارنامه‌ها به بازارگاه
    """
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        
        if not barnameh_ids:
            messages.error(request, 'هیچ بارنامه‌ای انتخاب نشده است.')
            return redirect('barnameh_list')
        
        result = send_multiple_barnameh_to_bki(barnameh_ids)
        
        if result['success'] > 0:
            messages.success(request, f"{result['success']} بارنامه با موفقیت به بازارگاه ارسال شد.")
        
        if result['failed'] > 0:
            messages.error(request, f"{result['failed']} بارنامه با خطا مواجه شد.")
            for message in result['messages']:
                messages.error(request, message)
        
        return redirect('barnameh_list')
    
    return redirect('barnameh_list')

@csrf_exempt
@role_required('logistics_manager', 'admin')
def barnameh_api(request):
    """
    API برای مدیریت بارنامه‌ها
    """
    if request.method == 'GET':
        barnameh_id = request.GET.get('id')
        
        if barnameh_id:
            try:
                barnameh = Barnameh.objects.get(id=barnameh_id)
                data = {
                    'id': barnameh.id,
                    'number': barnameh.number,
                    'serial': barnameh.serial,
                    'tonnage': float(barnameh.tonnage) if barnameh.tonnage else None,
                    'driver_phone': barnameh.driver_phone,
                    'driver_name': barnameh.driver_name,
                    'vehicle_plate': barnameh.vehicle_plate,
                    'receiver_name': barnameh.receiver_name,
                    'destination': barnameh.destination,
                    'barnameh_date': str(barnameh.barnameh_date) if barnameh.barnameh_date else None,
                    'purchase_number': barnameh.purchase_number,
                    'shenase_takhsis_code': barnameh.shenase_takhsis_code,
                    'status': barnameh.status,
                    'is_sent_to_bki': barnameh.is_sent_to_bki,
                }
                return JsonResponse({'success': True, 'data': data})
            except Barnameh.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'بارنامه مورد نظر یافت نشد.'})
        else:
            barnamehs = Barnameh.objects.all().order_by('-barnameh_created_at')
            data = []
            for barnameh in barnamehs:
                data.append({
                    'id': barnameh.id,
                    'number': barnameh.number,
                    'serial': barnameh.serial,
                    'tonnage': float(barnameh.tonnage) if barnameh.tonnage else None,
                    'status': barnameh.status,
                    'is_sent_to_bki': barnameh.is_sent_to_bki,
                })
            return JsonResponse({'success': True, 'data': data})
    
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            barnameh_id = data.get('id')
            
            if barnameh_id:
                # Update existing barnameh
                result = update_barnameh(barnameh_id, data)
            else:
                # Create new barnameh
                barnameh = Barnameh.objects.create(
                    number=data.get('number'),
                    serial=data.get('serial'),
                    tonnage=data.get('tonnage'),
                    driver_phone=data.get('driver_phone'),
                    driver_name=data.get('driver_name'),
                    vehicle_plate=data.get('vehicle_plate'),
                    receiver_name=data.get('receiver_name'),
                    destination=data.get('destination'),
                    barnameh_date=data.get('barnameh_date'),
                    purchase_number=data.get('purchase_number'),
                    shenase_takhsis_code=data.get('shenase_takhsis_code'),
                    status='BARNAMEH_COMPLETE' if all([data.get('number'), data.get('serial'), data.get('tonnage')]) else 'BARNAMEH_INCOMPLETE'
                )
                result = {
                    'success': True,
                    'message': 'بارنامه با موفقیت ایجاد شد.',
                    'barnameh': barnameh
                }
            
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'خطا: {str(e)}'})
    
    elif request.method == 'DELETE':
        try:
            data = json.loads(request.body)
            barnameh_id = data.get('id')
            
            if not barnameh_id:
                return JsonResponse({'success': False, 'message': 'شناسه بارنامه مشخص نشده است.'})
            
            result = delete_barnameh(barnameh_id)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'خطا: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'درخواست نامعتبر است.'})

@role_required('logistics_manager', 'admin')
def edit_barnameh_in_bki(request, barnameh_id):
    """
    ویرایش بارنامه در بازارگاه
    """
    if request.method == 'POST':
        result = edit_barnameh_api(barnameh_id)
        
        if result['success']:
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
        
        return redirect('barnameh_detail', barnameh_id=barnameh_id)
    
    barnameh = get_object_or_404(Barnameh, id=barnameh_id)
    return render(request, 'bki_barnameh/edit_barnameh_in_bki.html', {'barnameh': barnameh})

@role_required('logistics_manager', 'admin')
def bulk_edit(request):
    """
    ویرایش گروهی بارنامه‌ها
    """
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        
        if not barnameh_ids:
            messages.error(request, 'هیچ بارنامه‌ای انتخاب نشده است.')
            return redirect('barnameh_list')
        
        # دریافت بارنامه‌های انتخاب شده
        barnamehs = Barnameh.objects.filter(id__in=barnameh_ids)
        
        # اگر فرم ویرایش ارسال شده باشد
        if 'save_changes' in request.POST:
            field_to_update = request.POST.get('field_to_update')
            new_value = request.POST.get('new_value')
            
            if not field_to_update or not new_value:
                messages.error(request, 'لطفاً فیلد و مقدار جدید را وارد کنید.')
                return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
            
            # بررسی معتبر بودن فیلد
            valid_fields = ['tonnage', 'driver_name', 'driver_phone', 'vehicle_plate', 
                           'receiver_name', 'destination', 'barnameh_date']
            
            if field_to_update not in valid_fields:
                messages.error(request, 'فیلد انتخاب شده معتبر نیست.')
                return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
            
            # اعمال تغییرات برای همه بارنامه‌های انتخاب شده
            success_count = 0
            for barnameh in barnamehs:
                # اگر بارنامه به بازارگاه ارسال نشده باشد
                if not barnameh.is_sent_to_bki:
                    try:
                        # بروزرسانی فیلد مورد نظر
                        setattr(barnameh, field_to_update, new_value)
                        barnameh.save()
                        success_count += 1
                        barnameh.log_barnameh_edit(request)
                    except Exception as e:
                        continue
            
            messages.success(request, f'{success_count} بارنامه با موفقیت بروزرسانی شد.')
            return redirect('barnameh_list')
        
        return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
    
    return redirect('barnameh_list')

