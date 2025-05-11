from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from .models.BarnamehModel import Barnameh
from .models.ExcelFileModel import ExcelFile
from .models.ApiLogModel import BKIApiLog
from core.decorators.decorators import role_required
from .excel_management.upload_excel import handle_uploaded_file, process_excel_file
from .API.insertBarnameh import send_barnameh_to_bki, send_multiple_barnameh_to_bki
from .API.EditBarnameh import update_barnameh, delete_barnameh
import json
import os
from django.conf import settings
import pandas as pd

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
    آپلود فایل اکسل بارنامه
    """
    if request.method == 'POST' and request.FILES.get('excel_file'):
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
def download_excel_template(request):
    """
    دانلود قالب اکسل بارنامه
    """
    template_path = os.path.join(settings.BASE_DIR, 'bki_barnameh/excel_management/example/barnameh_excel_example.xlsx')
    
    if os.path.exists(template_path):
        with open(template_path, 'rb') as template_file:
            response = HttpResponse(template_file.read(), content_type='application/vnd.ms-excel')
            response['Content-Disposition'] = 'attachment; filename="barnameh_template.xlsx"'
            return response
    else:
        messages.error(request, 'فایل قالب یافت نشد.')
        return redirect('barnameh_list')

