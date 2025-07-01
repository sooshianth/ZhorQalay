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
from .API.EstelameBarnameh import estelame_barnameh
import json
import os
from django.conf import settings
import pandas as pd
import jdatetime
import logging

# توابع اکسل به فولدر excel_management منتقل شده‌اند
from .excel_management.views import upload_excel_view, download_excel_template, export_excel_view

logger = logging.getLogger('bki_barnameh_views')

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
                logger.error(f"خطا در تبدیل تاریخ: {str(e)}")
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
        logger.error(f"بارنامه مورد نظر یافت نشد.")
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        logger.error(f"خطا در بروزرسانی بارنامه: {str(e)}")
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
            logger.error(f"بارنامه {barnameh_id} قبلاً به بازارگاه ارسال شده است و قابل حذف نیست.")
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
        logger.error(f"بارنامه {barnameh_id} یافت نشد.")
        return {
            'success': False,
            'message': 'بارنامه مورد نظر یافت نشد.'
        }
    except Exception as e:
        logger.error(f"خطا در حذف بارنامه: {str(e)}")
        return {
            'success': False,
            'message': f'خطا در حذف بارنامه: {str(e)}'
        }

@role_required('logistics_manager', 'admin', 'financial_manager')
def barnameh_list(request):
    """
    نمایش لیست بارنامه ها
    """
    # Get sorting parameters from request
    sort_field = request.GET.get('sort', 'barnameh_created_at')
    direction = request.GET.get('direction', 'desc')
    
    # Map frontend sort fields to model fields
    sort_mapping = {
        'number': 'number',
        'serial': 'serial',
        'tonnage': 'tonnage',
        'purchase_number': 'purchase_number',
        'shenase_takhsis_code': 'shenase_takhsis_code',
        'status': 'status',
        'driver_name': 'driver_name',
        'driver_phone': 'driver_phone',
        'vehicle_plate': 'vehicle_plate',
        'receiver_name': 'receiver_name',
        'destination': 'destination',
        'barnameh_date': 'barnameh_date',
        'created_at': 'barnameh_created_at',
    }
    
    # Use the mapped field or default to created_at
    sort_field_mapped = sort_mapping.get(sort_field, 'barnameh_created_at')
    
    # Apply direction
    if direction == 'desc' and not sort_field_mapped.startswith('-'):
        sort_field_mapped = f'-{sort_field_mapped}'
    elif direction == 'asc' and sort_field_mapped.startswith('-'):
        sort_field_mapped = sort_field_mapped[1:]
    
    # Apply filters
    filters = {}
    search_query = request.GET.get('search')
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if search_query:
        # Search in multiple fields
        from django.db.models import Q
        barnamehs = Barnameh.objects.filter(
            Q(number__icontains=search_query) | 
            Q(serial__icontains=search_query) | 
            Q(purchase_number__icontains=search_query) |
            Q(shenase_takhsis_code__icontains=search_query) |
            Q(driver_name__icontains=search_query)
        )
    else:
        barnamehs = Barnameh.objects.all()
    
    if status_filter:
        barnamehs = barnamehs.filter(status=status_filter)
    
    if date_from:
        barnamehs = barnamehs.filter(barnameh_date__gte=date_from)
    
    if date_to:
        barnamehs = barnamehs.filter(barnameh_date__lte=date_to)
    
    # Apply sorting
    barnamehs = barnamehs.order_by(sort_field_mapped)
    
    # Get logs for each barnameh
    for barnameh in barnamehs:
        barnameh.logs = barnameh.barnameh_logs.all().order_by('-log_date')[:3]  # Get the 3 most recent logs
    
    return render(request, 'bki_barnameh/barnameh_list.html', {
        'barnamehs': barnamehs,
        'current_sort': sort_field,
        'current_direction': direction
    })

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
                logger.error(f"بارنامه {barnameh_id} یافت نشد.")
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
                logger.error('شناسه بارنامه مشخص نشده است.')
                return JsonResponse({'success': False, 'message': 'شناسه بارنامه مشخص نشده است.'})
            
            result = delete_barnameh(barnameh_id)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f'خطا در حذف بارنامه: {str(e)}')
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
            error_count = 0
            error_messages = []
            success_details = []
            error_details = []
            
            for barnameh in barnamehs:
                # اگر بارنامه به بازارگاه ارسال نشده باشد
                if not barnameh.is_sent_to_bki:
                    try:
                        # پردازش مقدار بر اساس نوع فیلد
                        processed_value = new_value
                        
                        if field_to_update == 'tonnage':
                            try:
                                processed_value = float(new_value)
                            except ValueError:
                                error_count += 1
                                error_message = f'مقدار وارد شده برای وزن معتبر نیست: {new_value}'
                                error_messages.append(error_message)
                                error_details.append({
                                    'id': barnameh.id,
                                    'number': barnameh.number,
                                    'serial': barnameh.serial,
                                    'error': error_message
                                })
                                logger.error(f"مقدار وارد شده برای وزن معتبر نیست: {new_value}")
                                continue
                        
                        elif field_to_update == 'barnameh_date':
                            try:
                                # تبدیل تاریخ شمسی به فرمت مناسب
                                parts = new_value.split('/')
                                if len(parts) == 3:
                                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                                    processed_value = jdatetime.date(year, month, day)
                                else:
                                    error_count += 1
                                    error_message = f'فرمت تاریخ معتبر نیست: {new_value}. از فرمت 1402/01/01 استفاده کنید.'
                                    error_messages.append(error_message)
                                    error_details.append({
                                        'id': barnameh.id,
                                        'number': barnameh.number,
                                        'serial': barnameh.serial,
                                        'error': error_message
                                    })
                                    logger.error(f"فرمت تاریخ معتبر نیست: {new_value}. از فرمت 1402/01/01 استفاده کنید.")
                                    continue
                            except Exception as e:
                                error_count += 1
                                error_message = f'خطا در تبدیل تاریخ: {str(e)}'
                                error_messages.append(error_message)
                                error_details.append({
                                    'id': barnameh.id,
                                    'number': barnameh.number,
                                    'serial': barnameh.serial,
                                    'error': error_message
                                })
                                logger.error(f"خطا در تبدیل تاریخ: {str(e)}")
                                continue
                        
                        # بروزرسانی فیلد مورد نظر
                        setattr(barnameh, field_to_update, processed_value)
                        barnameh.save()
                        success_count += 1
                        
                        # اضافه کردن به لیست موفق‌ها
                        success_details.append({
                            'id': barnameh.id,
                            'number': barnameh.number,
                            'serial': barnameh.serial
                        })
                        
                        # ایجاد لاگ برای ویرایش
                        from django.utils import timezone
                        barnameh.barnameh_logs.create(
                            log_message=f"ویرایش گروهی: فیلد '{field_to_update}' به مقدار '{new_value}' تغییر کرد",
                            log_date=timezone.now()
                        )
                    except Exception as e:
                        error_count += 1
                        error_message = f'خطا در بروزرسانی بارنامه {barnameh.number}/{barnameh.serial}: {str(e)}'
                        error_messages.append(error_message)
                        error_details.append({
                            'id': barnameh.id,
                            'number': barnameh.number,
                            'serial': barnameh.serial,
                            'error': error_message
                        })
                        logger.error(f"خطا در بروزرسانی بارنامه {barnameh.number}/{barnameh.serial}: {str(e)}")
                else:
                    error_count += 1
                    error_message = f'بارنامه {barnameh.number}/{barnameh.serial} قبلاً به بازارگاه ارسال شده است و قابل ویرایش نیست.'
                    error_messages.append(error_message)
                    error_details.append({
                        'id': barnameh.id,
                        'number': barnameh.number,
                        'serial': barnameh.serial,
                        'error': error_message
                    })
                    logger.error(f"بارنامه {barnameh.number}/{barnameh.serial} قبلاً به بازارگاه ارسال شده است و قابل ویرایش نیست.")
            # ذخیره نتایج در سشن برای نمایش در صفحه نتایج
            request.session['bulk_edit_results'] = {
                'field': field_to_update,
                'value': new_value,
                'success_count': success_count,
                'error_count': error_count,
                'success_details': success_details,
                'error_details': error_details[:10]  # حداکثر 10 خطا را ذخیره می‌کنیم
            }
            
            if success_count > 0:
                messages.success(request, f'{success_count} بارنامه با موفقیت بروزرسانی شد.')
            
            if error_count > 0:
                messages.error(request, f'{error_count} بارنامه با خطا مواجه شد.')
                for error in error_messages[:5]:  # نمایش حداکثر 5 پیام خطا
                    messages.error(request, error)
                
                if len(error_messages) > 5:
                    messages.error(request, f'و {len(error_messages) - 5} خطای دیگر...')
            
            return redirect('barnameh_list')
        
        return render(request, 'bki_barnameh/bulk_edit.html', {'barnamehs': barnamehs})
    
    return redirect('barnameh_list')

@role_required('logistics_manager', 'admin')
def estelame_barnameh_view(request, barnameh_id):
    """
    استعلام بارنامه از بازارگاه
    """
    if request.method == 'POST':
        # Get date parameters from request
        from_date = request.POST.get('from_date', None)
        to_date = request.POST.get('to_date', None)
        
        # Call API function
        result = estelame_barnameh(barnameh_id, from_date, to_date)
        
        if result['success']:
            messages.success(request, 'استعلام بارنامه با موفقیت انجام شد.')
            # Pass data to template
            barnameh = get_object_or_404(Barnameh, id=barnameh_id)
            return render(request, 'bki_barnameh/barnameh_estelam.html', {
                'barnameh': barnameh,
                'estelam_data': result['data']
            })
        else:
            messages.error(request, result['message'])
            return redirect('barnameh_detail', barnameh_id=barnameh_id)
    else:
        return redirect('barnameh_detail', barnameh_id=barnameh_id)

@role_required('logistics_manager', 'admin')
def bulk_delete(request):
    """
    حذف گروهی بارنامه‌ها
    """
    if request.method == 'POST':
        barnameh_ids = request.POST.getlist('barnameh_ids')
        
        if not barnameh_ids:
            messages.error(request, 'هیچ بارنامه‌ای انتخاب نشده است.')
            return redirect('barnameh_list')
        
        success_count = 0
        error_count = 0
        
        for barnameh_id in barnameh_ids:
            try:
                barnameh = Barnameh.objects.get(id=barnameh_id)
                # فقط بارنامه‌هایی که به بازارگاه ارسال نشده‌اند را حذف می‌کنیم
                if not barnameh.is_sent_to_bki:
                    barnameh.delete()
                    success_count += 1
                else:
                    error_count += 1
            except Barnameh.DoesNotExist:
                error_count += 1
                continue
        
        if success_count > 0:
            messages.success(request, f'{success_count} بارنامه با موفقیت حذف شد.')
        if error_count > 0:
            messages.error(request, f'{error_count} بارنامه به دلیل ارسال به بازارگاه یا خطای دیگر حذف نشد.')
        
        return redirect('barnameh_list')
    
    return redirect('barnameh_list')

