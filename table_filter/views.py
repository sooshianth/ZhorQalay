from django.shortcuts import render, redirect

import json
import openpyxl
from io import BytesIO
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from openpyxl.styles import Font, PatternFill, Alignment
from datetime import datetime
from django.contrib.auth.models import User
from django.db.models import Q
import logging

# Create your views here.

def table_filter_demo(request):
    """
    نمایش صفحه نمونه برای فیلتر جداول
    """
    return render(request, 'table_filter/demo.html')

@login_required
def bulk_edit_page(request):
    """نمایش صفحه ویرایش گروهی"""
    selected_ids = request.GET.get('ids', '').split(',')
    selected_ids = [id.strip() for id in selected_ids if id.strip()]
    
    model_name = request.GET.get('model', '')
    app_name = request.GET.get('app', 'core')
    table_type = request.GET.get('table_type', '')
    
    if not selected_ids:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': 'هیچ موردی انتخاب نشده است'
        })
    
    # تشخیص مدل
    if not model_name:
        referer = request.META.get('HTTP_REFERER', '')
        if 'purchase' in referer:
            model_name = 'Purchase'
            table_type = 'purchase'
        elif 'customer' in referer:
            model_name = 'Customer'
            table_type = 'customer'
    
    try:
        model = apps.get_model(app_name, model_name)
    except LookupError:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': f'مدل {model_name} یافت نشد'
        })
    
    # دریافت آبجکت‌های انتخاب شده
    objects = model.objects.filter(id__in=selected_ids)
    
    # دریافت فیلدهای قابل ویرایش
    editable_fields = get_editable_fields(model, table_type)
    
    context = {
        'objects': objects,
        'model_name': model_name,
        'app_name': app_name,
        'table_type': table_type,
        'editable_fields': editable_fields,
        'selected_count': len(selected_ids),
        'selected_ids': selected_ids,
    }
    
    return render(request, 'table_filter/bulk_edit.html', context)

def get_editable_fields(model, table_type):
    """دریافت فیلدهای قابل ویرایش برای هر مدل"""
    fields_map = {
        'purchase': [
            {'name': 'invoice_id', 'label': 'کد درون سازمانی', 'type': 'text'},
            {'name': 'purchase_number', 'label': 'شماره خرید', 'type': 'text', 'is_unique': True},
            {'name': 'order_weight', 'label': 'وزن سفارش (کیلوگرم)', 'type': 'number'},
            {'name': 'delivered_weight', 'label': 'وزن تحویلی (کیلوگرم)', 'type': 'number'},
            {'name': 'company_price', 'label': 'قیمت خرید (ریال)', 'type': 'number'},
            {'name': 'customer_price', 'label': 'قیمت فروش (ریال)', 'type': 'number'},
            {'name': 'amount_paid', 'label': 'مبلغ پرداختی (ریال)', 'type': 'number'},
            {'name': 'description', 'label': 'توضیحات', 'type': 'textarea'},
            {'name': 'state', 'label': 'وضعیت', 'type': 'select', 'choices': [
                ('INITIATED', 'شروع شده'),
                ('SMS_SENT', 'پیامک ارسال شده'),
                ('PAYMENT_VERIFIED', 'ثبت خرید در بازارگاه'),
                ('ALLOCATION_APPROVED', 'ثبت تخصیص در بازارگاه'),
                ('ADDRESS_SENT', 'ارسال آدرس به واردکننده'),
                ('WAITING_FOR_BARNAMEH', 'در انتظار بارنامه'),
                ('BARNAMEH_INCOMPLETE', 'صدور بارنامه (ناقص)'),
                ('BARNAMEH_ISSUED', 'صدور بارنامه'),
                ('PURCHASE_CLOSED', 'بستن خرید در بازارگاه'),
                ('PAY_KASRI', 'پرداخت کسری'),
                ('RECIEVE_SARAK', 'دریافت سرک'),
                ('DIFFERENCE_APPROVED', 'پرداخت کسری / دریافت سرک'),
                ('FULLY_SETTLED', 'تسویه کامل'),
                ('INVOICE_ISSUED', 'صدور فاکتور'),
                ('CANCELED', 'لغو شده'),
                ('ARCHIVED', 'آرشیو شده'),
            ]},
            {'name': 'is_urgent', 'label': 'فوری', 'type': 'checkbox'},
            {'name': 'is_factored', 'label': 'فاکتور صادر شده', 'type': 'checkbox'},
            {'name': 'is_archived', 'label': 'آرشیو شده', 'type': 'checkbox'},
            {'name': 'is_fully_tasvied', 'label': 'تسویه کامل', 'type': 'checkbox'},
        ],
        'customer': [
            {'name': 'name', 'label': 'نام مشتری', 'type': 'text'},
            {'name': 'phone_number', 'label': 'شماره تلفن', 'type': 'text', 'is_unique': True},
            {'name': 'address', 'label': 'آدرس', 'type': 'textarea'},
            {'name': 'national_code', 'label': 'کد ملی', 'type': 'text', 'is_unique': True},
        ]
    }
    
    # دریافت لیست فیلدهای مورد نظر
    fields = fields_map.get(table_type, [])
    
    # اضافه کردن ویژگی is_unique به فیلدها با بررسی مدل
    if model:
        # پیدا کردن فیلدهای یکتا
        unique_fields = []
        for field in model._meta.fields:
            if field.unique or field.primary_key:
                unique_fields.append(field.name)
        
        # اضافه کردن ویژگی is_unique به فیلدهای یکتا
        for field_data in fields:
            if field_data['name'] in unique_fields and 'is_unique' not in field_data:
                field_data['is_unique'] = True
    
    return fields

@login_required
def bulk_edit_excel_page(request):
    """نمایش صفحه ویرایش با اکسل"""
    selected_ids = request.GET.get('ids', '').split(',')
    selected_ids = [id.strip() for id in selected_ids if id.strip()]
    
    model_name = request.GET.get('model', '')
    app_name = request.GET.get('app', 'core')
    table_type = request.GET.get('table_type', '')
    
    if not selected_ids:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': 'هیچ موردی انتخاب نشده است'
        })
    
    # تشخیص مدل
    if not model_name:
        referer = request.META.get('HTTP_REFERER', '')
        if 'purchase' in referer:
            model_name = 'Purchase'
            table_type = 'purchase'
        elif 'customer' in referer:
            model_name = 'Customer'
            table_type = 'customer'
    
    try:
        model = apps.get_model(app_name, model_name)
    except LookupError:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': f'مدل {model_name} یافت نشد'
        })
    
    # دریافت آبجکت‌های انتخاب شده
    objects = model.objects.filter(id__in=selected_ids)
    
    context = {
        'objects': objects,
        'model_name': model_name,
        'app_name': app_name,
        'table_type': table_type,
        'selected_count': len(selected_ids),
        'selected_ids': selected_ids,
    }
    
    return render(request, 'table_filter/bulk_edit_excel.html', context)

@login_required
@require_http_methods(["POST"])
def bulk_edit_view(request):
    """Handle bulk editing of table rows"""
    try:
        selected_ids = request.POST.getlist('selected_ids')
        if not selected_ids:
            return JsonResponse({
                'status': 'error',
                'message': 'هیچ موردی انتخاب نشده است'
            })
        
        # تشخیص مدل بر اساس URL یا پارامتر
        model_name = request.POST.get('model_name')
        app_name = request.POST.get('app_name', 'core')
        
        if not model_name:
            # تلاش برای تشخیص از URL
            referer = request.META.get('HTTP_REFERER', '')
            if 'purchase' in referer or 'purchase_list' in referer:
                model_name = 'Purchase'
                app_name = 'core'
            elif 'customer' in referer:
                model_name = 'Customer' 
                app_name = 'core'
            elif 'barbary' in referer:
                model_name = 'Barbary'
                app_name = 'core'
            else:
                return JsonResponse({
                    'status': 'error',
                    'message': 'نوع مدل تشخیص داده نشد'
                })
        
        # دریافت مدل
        try:
            model = apps.get_model(app_name, model_name)
        except LookupError:
            return JsonResponse({
                'status': 'error',
                'message': f'مدل {model_name} یافت نشد'
            })
        
        # دریافت آبجکت‌های انتخاب شده
        queryset = model.objects.filter(id__in=selected_ids)
        
        if not queryset.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'موارد انتخاب شده یافت نشدند'
            })
        
        # آماده‌سازی داده‌های به‌روزرسانی
        update_data = {}
        
        # شناسایی فیلدهای یکتا در مدل
        unique_fields = []
        for field in model._meta.fields:
            if field.unique or field.primary_key:
                unique_fields.append(field.name)
        
        # لاگ فیلدهای یکتا برای اشکال‌زدایی
        print(f"Unique fields for {model_name}: {unique_fields}")
        
        # پردازش فیلدهای مختلف
        for field_name, value in request.POST.items():
            if field_name in ['selected_ids', 'model_name', 'app_name', 'csrfmiddlewaretoken']:
                continue
                
            if value and value.strip():  # فقط فیلدهای با مقدار
                # بررسی وجود فیلد در مدل
                try:
                    field = model._meta.get_field(field_name)
                    
                    # هشدار: اگر یک فیلد یکتا برای چندین رکورد تغییر کند
                    if field_name in unique_fields and len(selected_ids) > 1:
                        return JsonResponse({
                            'status': 'error',
                            'message': f'فیلد {field_name} دارای محدودیت یکتایی است و نمی‌تواند برای چندین رکورد یکسان باشد.'
                        })
                    
                    # تبدیل مقدار به نوع مناسب
                    if field.get_internal_type() in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField']:
                        try:
                            update_data[field_name] = int(value)
                        except ValueError:
                            continue
                    elif field.get_internal_type() in ['FloatField', 'DecimalField']:
                        try:
                            update_data[field_name] = float(value)
                        except ValueError:
                            continue
                    elif field.get_internal_type() == 'BooleanField':
                        update_data[field_name] = value.lower() in ['true', '1', 'yes', 'on']
                    else:
                        update_data[field_name] = value
                        
                except FieldDoesNotExist:
                    continue
        
        # پردازش چک‌باکس‌ها (که در POST نیستند اگر انتخاب نشده باشند)
        checkbox_fields = ['is_urgent', 'is_factored', 'is_archived', 'is_canceled', 'is_weight_costed', 'is_ap_af', 'is_fully_tasvied']
        for field_name in checkbox_fields:
            if field_name in request.POST:
                update_data[field_name] = True
            else:
                # اگر چک‌باکس وجود نداشت، آن را False کن (فقط اگر مدل این فیلد را دارد)
                try:
                    model._meta.get_field(field_name)
                    update_data[field_name] = False
                except FieldDoesNotExist:
                    continue
        
        # لاگ کردن داده‌های به‌روزرسانی
        print(f"Update data: {update_data}")
        
        # ایمپورت مدل لاگ
        from .models import BulkEditLog
        
        # اعمال تغییرات
        updated_count = 0
        errors = []
        
        with transaction.atomic():
            for obj in queryset:
                try:
                    # ذخیره مقادیر قبلی برای لاگ تغییرات
                    changes_dict = {}
                    
                    # اعمال تغییرات به آبجکت
                    for field_name, value in update_data.items():
                        # ذخیره مقدار قبلی
                        old_value = getattr(obj, field_name, None)
                        
                        # تنظیم مقدار جدید
                        setattr(obj, field_name, value)
                        
                        # ثبت تغییر در دیکشنری تغییرات
                        changes_dict[field_name] = {
                            'old': old_value,
                            'new': value
                        }
                    
                    obj.save()
                    updated_count += 1
                    
                    # ثبت تغییرات در لاگ
                    BulkEditLog.log_changes(
                        user=request.user,
                        app_name=app_name,
                        model_name=model_name,
                        object_id=str(obj.id),
                        action_type='FORM',
                        changes_dict=changes_dict
                    )
                    
                except Exception as e:
                    # اضافه کردن خطا به لیست خطاها
                    errors.append(f"خطا در به‌روزرسانی {obj.id}: {str(e)}")
                    print(f"Error updating object {obj.id}: {str(e)}")
                    continue
        
        # لاگ کردن نتیجه
        print(f"Updated {updated_count} objects")
        if errors:
            print(f"Errors: {errors}")
        
        # در صورت تکمیل موفق، بازگشت به صفحه قبلی یا JSON response
        if updated_count > 0:
            if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT') == 'application/json':
                return JsonResponse({
                    'status': 'success',
                    'updated_count': updated_count,
                    'message': f'{updated_count} مورد با موفقیت به‌روزرسانی شد',
                    'errors': errors[:10] if errors else []
                })
            else:
                # بازگشت به صفحه قبلی با پیام موفقیت
                from django.contrib import messages
                from django.shortcuts import redirect
                
                if errors:
                    messages.warning(request, f'{updated_count} مورد به‌روزرسانی شد، اما {len(errors)} خطا رخ داد.')
                else:
                    messages.success(request, f'{updated_count} مورد با موفقیت به‌روزرسانی شد')
                
                # تلاش برای بازگشت به صفحه قبلی
                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return redirect(referer)
                else:
                    return redirect('/')
        else:
            # همه موارد با خطا مواجه شدند
            error_message = 'خطا در به‌روزرسانی: ' + errors[0] if errors else 'خطا در به‌روزرسانی'
            
            if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT') == 'application/json':
                return JsonResponse({
                    'status': 'error',
                    'message': error_message,
                    'errors': errors[:10] if errors else []
                })
            else:
                from django.contrib import messages
                from django.shortcuts import redirect
                
                messages.error(request, error_message)
                
                referer = request.META.get('HTTP_REFERER')
                if referer:
                    return redirect(referer)
                else:
                    return redirect('/')
        
    except Exception as e:
        # چاپ خطا برای اشکال‌زدایی
        import traceback
        print(f"Error in bulk_edit_view: {str(e)}")
        print(traceback.format_exc())
        
        if request.headers.get('Content-Type') == 'application/json' or request.META.get('HTTP_ACCEPT') == 'application/json':
            return JsonResponse({
                'status': 'error',
                'message': f'خطا در به‌روزرسانی: {str(e)}'
            })
        else:
            from django.contrib import messages
            from django.shortcuts import redirect
            
            messages.error(request, f'خطا در به‌روزرسانی: {str(e)}')
            
            referer = request.META.get('HTTP_REFERER')
            if referer:
                return redirect(referer)
            else:
                return redirect('/')

@login_required
@require_http_methods(["POST"])
def bulk_edit_excel_view(request):
    """Handle bulk editing via Excel file upload"""
    try:
        if 'excel_file' not in request.FILES:
            from django.contrib import messages
            messages.error(request, 'فایل اکسل انتخاب نشده است')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        excel_file = request.FILES['excel_file']
        selected_ids = request.POST.getlist('selected_ids')
        
        if not selected_ids:
            from django.contrib import messages
            messages.error(request, 'هیچ موردی انتخاب نشده است')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # تشخیص مدل
        model_name = request.POST.get('model_name')
        app_name = request.POST.get('app_name', 'core')
        
        if not model_name:
            # تلاش برای تشخیص از URL
            referer = request.META.get('HTTP_REFERER', '')
            if 'purchase' in referer or 'purchase_list' in referer:
                model_name = 'Purchase'
                app_name = 'core'
            elif 'customer' in referer:
                model_name = 'Customer'
                app_name = 'core'
            elif 'barbary' in referer:
                model_name = 'Barbary'
                app_name = 'core'
            else:
                from django.contrib import messages
                messages.error(request, 'نوع مدل تشخیص داده نشد')
                return redirect(request.META.get('HTTP_REFERER', '/'))
        
        try:
            model = apps.get_model(app_name, model_name)
        except LookupError:
            from django.contrib import messages
            messages.error(request, f'مدل {model_name} یافت نشد')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # ایمپورت مدل لاگ
        from .models import BulkEditLog
        
        # خواندن فایل اکسل
        try:
            workbook = openpyxl.load_workbook(excel_file)
            worksheet = workbook.active
        except Exception as e:
            from django.contrib import messages
            messages.error(request, f'خطا در خواندن فایل اکسل: {str(e)}')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # خواندن هدرها (سطر اول)
        headers = []
        for cell in worksheet[1]:
            if cell.value:
                headers.append(str(cell.value).strip())
            else:
                break
        
        if 'ID' not in headers:
            from django.contrib import messages
            messages.error(request, 'ستون ID در فایل اکسل یافت نشد')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        id_index = headers.index('ID')
        
        # پردازش داده‌ها
        updated_count = 0
        errors = []
        log_details = []  # جزئیات لاگ برای نمایش به کاربر
        
        with transaction.atomic():
            for row_num, row in enumerate(worksheet.iter_rows(min_row=2), start=2):
                if not row[id_index].value:
                    continue
                    
                try:
                    obj_id = str(row[id_index].value).strip()
                    
                    # بررسی اینکه آبجکت در لیست انتخاب شده‌ها باشد
                    if obj_id not in selected_ids:
                        continue
                    
                    # دریافت آبجکت
                    try:
                        obj = model.objects.get(id=obj_id)
                    except model.DoesNotExist:
                        errors.append(f'سطر {row_num}: آبجکت با شناسه {obj_id} یافت نشد')
                        continue
                    
                    # جمع‌آوری تغییرات برای لاگ
                    changes_dict = {}
                    
                    # به‌روزرسانی فیلدها
                    for col_index, header in enumerate(headers):
                        if header == 'ID' or col_index >= len(row):
                            continue
                            
                        cell_value = row[col_index].value
                        
                        if cell_value is not None and str(cell_value).strip():
                            field_name = get_field_name_from_header(header, model_name)
                            
                            if field_name:
                                try:
                                    field = model._meta.get_field(field_name)
                                    
                                    # ذخیره مقدار قبلی
                                    old_value = getattr(obj, field_name, None)
                                    
                                    # تبدیل مقدار به نوع مناسب
                                    converted_value = convert_excel_value(cell_value, field)
                                    
                                    # تنظیم مقدار جدید
                                    setattr(obj, field_name, converted_value)
                                    
                                    # ثبت تغییر در دیکشنری تغییرات
                                    if old_value != converted_value:
                                        changes_dict[field_name] = {
                                            'old': old_value,
                                            'new': converted_value
                                        }
                                    
                                except (FieldDoesNotExist, ValueError, TypeError) as e:
                                    errors.append(f'سطر {row_num}, ستون {header}: {str(e)}')
                                    continue
                    
                    # ذخیره آبجکت فقط اگر تغییری وجود داشته باشد
                    if changes_dict:
                        obj.save()
                        updated_count += 1
                        
                        # ثبت تغییرات در لاگ
                        log_count = BulkEditLog.log_changes(
                            user=request.user,
                            app_name=app_name,
                            model_name=model_name,
                            object_id=str(obj.id),
                            action_type='EXCEL',
                            changes_dict=changes_dict
                        )
                        
                        # اضافه کردن به جزئیات لاگ
                        log_details.append({
                            'id': obj_id,
                            'changes': len(changes_dict),
                            'fields': list(changes_dict.keys())
                        })
                    
                except Exception as e:
                    errors.append(f'سطر {row_num}: خطا در پردازش - {str(e)}')
                    continue
        
        # استفاده از سیستم پیام‌ها برای نمایش نتیجه
        from django.contrib import messages
        
        if updated_count > 0:
            messages.success(request, f'{updated_count} مورد از فایل اکسل به‌روزرسانی شد')
        else:
            messages.warning(request, 'هیچ موردی به‌روزرسانی نشد')
        
        if errors:
            error_message = f'خطاها ({len(errors)}): ' + '، '.join(errors[:5])
            if len(errors) > 5:
                error_message += ' و ...'
            messages.error(request, error_message)
        
        # بازگشت به صفحه قبلی
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    except Exception as e:
        # چاپ خطا برای اشکال‌زدایی
        import traceback
        print(f"Error in bulk_edit_excel_view: {str(e)}")
        print(traceback.format_exc())
        
        from django.contrib import messages
        messages.error(request, f'خطا در پردازش فایل اکسل: {str(e)}')
        
        # بازگشت به صفحه قبلی
        return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def download_excel_template_view(request):
    """Download Excel template for bulk editing"""
    try:
        table_type = request.GET.get('table_type', 'generic')
        selected_ids = request.GET.get('selected_ids', '').split(',')
        selected_ids = [id.strip() for id in selected_ids if id.strip()]
        
        # تشخیص مدل
        model_name = None
        app_name = 'core'
        
        # تشخیص از URL اگر table_type ارسال نشده باشد
        if table_type == 'generic':
            referer = request.META.get('HTTP_REFERER', '')
            if 'purchase' in referer or 'purchase_list' in referer:
                table_type = 'purchase'
            elif 'customer' in referer:
                table_type = 'customer'
            elif 'barbary' in referer:
                table_type = 'barbary'
        
        if table_type == 'purchase':
            model_name = 'Purchase'
        elif table_type == 'customer':
            model_name = 'Customer'
        elif table_type == 'barbary':
            model_name = 'Barbary'
        else:
            return HttpResponse('نوع جدول پشتیبانی نمی‌شود', status=400)
        
        try:
            model = apps.get_model(app_name, model_name)
        except LookupError:
            return HttpResponse('مدل یافت نشد', status=400)
        
        # ایجاد فایل اکسل
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = f'Template_{model_name}'
        
        # تنظیم راست به چپ بودن شیت
        worksheet.sheet_view.rightToLeft = True
        
        # تعریف هدرها و فیلدها
        headers_fields = get_excel_headers_fields(table_type)
        headers = list(headers_fields.keys())
        
        # نوشتن هدرها
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # دریافت داده‌های موجود برای موارد انتخاب شده
        if selected_ids:
            queryset = model.objects.filter(id__in=selected_ids)
            
            for row_num, obj in enumerate(queryset, 2):
                for col_num, (header, field_name) in enumerate(headers_fields.items(), 1):
                    if field_name == 'id':
                        value = obj.id
                    else:
                        try:
                            value = getattr(obj, field_name, '')
                            
                            # تبدیل مقادیر خاص
                            if hasattr(obj, f'get_{field_name}_display'):
                                display_value = getattr(obj, f'get_{field_name}_display')()
                                if display_value:
                                    value = display_value
                            elif isinstance(value, bool):
                                value = 'بله' if value else 'خیر'
                            elif value is None:
                                value = ''
                                
                        except AttributeError:
                            value = ''
                    
                    cell = worksheet.cell(row=row_num, column=col_num, value=value)
                    # تنظیم alignment برای سلول‌ها
                    cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # تنظیم عرض ستون‌ها
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 5, 50)  # کمی عرض بیشتر برای خوانایی بهتر متن فارسی
            worksheet.column_dimensions[column].width = adjusted_width
        
        # تنظیم استایل کلی فایل
        for row in worksheet.rows:
            for cell in row:
                if cell.row > 1:  # برای همه سطرها به جز هدر
                    cell.font = Font(name='Tahoma', size=11)
        
        # ذخیره فایل در حافظه
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        # تنظیم response
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        filename = f'bulk_edit_template_{model_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        return HttpResponse(f'خطا در ایجاد قالب: {str(e)}', status=500)

def get_field_name_from_header(header, model_name):
    """Map Excel header to model field name"""
    mapping = {
        'purchase': {
            'کد درون سازمانی': 'invoice_id',
            'شماره خرید': 'purchase_number',
            'وزن سفارش': 'order_weight',
            'قیمت خرید': 'company_price',
            'قیمت فروش': 'customer_price',
            'وضعیت': 'state',
            'فوری': 'is_urgent',
            'فاکتور صادر شده': 'is_factored',
            'آرشیو شده': 'is_archived',
            'وزن تحویلی': 'delivered_weight',
            'مبلغ پرداختی': 'amount_paid',
            'توضیحات': 'description',
        },
        'customer': {
            'نام مشتری': 'name',
            'شماره تلفن': 'phone_number',
            'آدرس': 'address',
            'کد ملی': 'national_code',
        }
    }
    
    model_mapping = mapping.get(model_name.lower(), {})
    return model_mapping.get(header)

def convert_excel_value(value, field):
    """Convert Excel cell value to appropriate field type"""
    if field.get_internal_type() in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField']:
        return int(float(value)) if value else 0
    elif field.get_internal_type() in ['FloatField', 'DecimalField']:
        return float(value) if value else 0.0
    elif field.get_internal_type() == 'BooleanField':
        return str(value).lower() in ['بله', 'true', '1', 'yes', 'on', 'فعال']
    else:
        return str(value) if value else ''

def get_excel_headers_fields(table_type):
    """Get headers and corresponding field names for Excel template"""
    mappings = {
        'purchase': {
            'ID': 'id',
            'کد درون سازمانی': 'invoice_id',
            'شماره خرید': 'purchase_number',
            'وزن سفارش (کیلوگرم)': 'order_weight',
            'قیمت خرید (ریال)': 'company_price',
            'قیمت فروش (ریال)': 'customer_price',
            'وضعیت': 'state',
            'فوری': 'is_urgent',
            'فاکتور صادر شده': 'is_factored',
            'آرشیو شده': 'is_archived',
            'توضیحات': 'description',
        },
        'customer': {
            'ID': 'id',
            'نام مشتری': 'name',
            'شماره تلفن': 'phone_number',
            'آدرس': 'address',
            'کد ملی': 'national_code',
        }
    }
    
    return mappings.get(table_type, {'ID': 'id'})

@login_required
def edit_history_view(request):
    """نمایش تاریخچه تغییرات"""
    from .models import BulkEditLog
    
    # پارامترهای فیلتر
    app_name = request.GET.get('app_name', '')
    model_name = request.GET.get('model_name', '')
    object_id = request.GET.get('object_id', '')
    user_id = request.GET.get('user_id', '')
    action_type = request.GET.get('action_type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # ساخت کوئری
    logs = BulkEditLog.objects.all().order_by('-timestamp')
    
    if app_name:
        logs = logs.filter(app_name=app_name)
    if model_name:
        logs = logs.filter(model_name=model_name)
    if object_id:
        logs = logs.filter(object_id=object_id)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if action_type:
        logs = logs.filter(action_type=action_type)
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    # پارامترهای pagination
    from django.core.paginator import Paginator
    page = request.GET.get('page', 1)
    paginator = Paginator(logs, 50)  # 50 لاگ در هر صفحه
    logs_page = paginator.get_page(page)
    
    # تجمیع لاگ‌ها بر اساس عملیات
    from collections import defaultdict
    from django.contrib.auth.models import User
    
    grouped_logs = defaultdict(list)
    users_dict = {}
    
    for log in logs_page:
        key = f"{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_{log.model_name}_{log.object_id}_{log.user_id}"
        grouped_logs[key].append(log)
        
        if log.user_id and log.user_id not in users_dict:
            try:
                users_dict[log.user_id] = User.objects.get(id=log.user_id)
            except User.DoesNotExist:
                users_dict[log.user_id] = None
    
    # لیست اپلیکیشن‌ها و مدل‌ها برای فیلتر
    apps_models = BulkEditLog.objects.values('app_name', 'model_name').distinct()
    apps = set()
    models = set()
    
    for item in apps_models:
        apps.add(item['app_name'])
        models.add(item['model_name'])
    
    # لیست کاربران برای فیلتر
    users = User.objects.filter(id__in=BulkEditLog.objects.values_list('user_id', flat=True).distinct())
    
    context = {
        'logs_page': logs_page,
        'grouped_logs': dict(grouped_logs),
        'users_dict': users_dict,
        'apps': sorted(apps),
        'models': sorted(models),
        'users': users,
        'filters': {
            'app_name': app_name,
            'model_name': model_name,
            'object_id': object_id,
            'user_id': user_id,
            'action_type': action_type,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'table_filter/edit_history.html', context)

@login_required
def object_edit_history_view(request, app_name, model_name, object_id):
    """نمایش تاریخچه تغییرات یک آبجکت خاص"""
    from .models import BulkEditLog
    from django.contrib.auth.models import User
    from django.apps import apps
    
    try:
        # دریافت آبجکت
        model = apps.get_model(app_name, model_name)
        obj = model.objects.get(id=object_id)
        
        # دریافت لاگ‌های مربوط به این آبجکت
        logs = BulkEditLog.objects.filter(
            app_name=app_name,
            model_name=model_name,
            object_id=object_id
        ).order_by('-timestamp')
        
        # دریافت اطلاعات کاربران
        user_ids = logs.values_list('user_id', flat=True).distinct()
        users = User.objects.filter(id__in=user_ids)
        users_dict = {user.id: user for user in users}
        
        # تجمیع لاگ‌ها بر اساس زمان
        from collections import defaultdict
        grouped_logs = defaultdict(list)
        
        for log in logs:
            timestamp_key = log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            grouped_logs[timestamp_key].append(log)
        
        context = {
            'object': obj,
            'app_name': app_name,
            'model_name': model_name,
            'object_id': object_id,
            'logs': logs,
            'grouped_logs': dict(grouped_logs),
            'users_dict': users_dict,
        }
        
        return render(request, 'table_filter/object_edit_history.html', context)
        
    except Exception as e:
        from django.contrib import messages
        messages.error(request, f'خطا در نمایش تاریخچه: {str(e)}')
        return redirect('table_filter:edit_history')

@login_required
@require_http_methods(["POST"])
def restore_field_view(request, log_id):
    """بازگرداندن مقدار فیلد به مقدار قبلی"""
    from .models import BulkEditLog
    
    try:
        log = BulkEditLog.objects.get(id=log_id)
        
        # بررسی دسترسی (مثلاً فقط مدیران یا خود کاربر)
        if not request.user.is_staff and log.user_id != request.user.id:
            return JsonResponse({
                'status': 'error',
                'message': 'شما اجازه دسترسی به این عملیات را ندارید'
            })
        
        # بازگرداندن مقدار
        success, message = log.restore_value()
        
        if success:
            # ثبت عملیات بازگشت در لاگ
            new_log = BulkEditLog(
                user=request.user,
                app_name=log.app_name,
                model_name=log.model_name,
                object_id=log.object_id,
                action_type=log.action_type,
                field_name=log.field_name,
                old_value=log.new_value,  # مقدار فعلی به عنوان مقدار قدیمی
                new_value=log.old_value  # مقدار قدیمی به عنوان مقدار جدید
            )
            new_log.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'مقدار فیلد {log.field_name} با موفقیت بازگردانده شد'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': message
            })
    
    except BulkEditLog.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'لاگ مورد نظر یافت نشد'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در بازگرداندن مقدار: {str(e)}'
        })

@login_required
def edit_history_api(request):
    """API برای دریافت تاریخچه تغییرات"""
    from .models import BulkEditLog
    
    # پارامترهای فیلتر
    app_name = request.GET.get('app_name', '')
    model_name = request.GET.get('model_name', '')
    object_id = request.GET.get('object_id', '')
    user = request.GET.get('user', '')
    action_type = request.GET.get('action_type', '')
    field_name = request.GET.get('field_name', '')
    date_str = request.GET.get('date', '')
    
    # ساخت کوئری
    logs = BulkEditLog.objects.all().order_by('-timestamp')
    
    if app_name:
        logs = logs.filter(app_name=app_name)
    if model_name:
        logs = logs.filter(model_name=model_name)
    if object_id:
        logs = logs.filter(object_id=object_id)
    if user:
        logs = logs.filter(user_id=user)
    if action_type:
        logs = logs.filter(action_type=action_type)
    if field_name:
        logs = logs.filter(field_name=field_name)
    if date_str:
        try:
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date=date_obj)
        except ValueError:
            pass
    
    # پارامترهای pagination
    from django.core.paginator import Paginator
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    paginator = Paginator(logs, page_size)
    logs_page = paginator.get_page(page)
    
    # تبدیل به فرمت JSON
    results = []
    for log in logs_page:
        # دریافت نام کاربر
        user_name = ''
        if log.user_id:
            try:
                user = User.objects.get(id=log.user_id)
                user_name = user.get_full_name() or user.username
            except User.DoesNotExist:
                user_name = f'کاربر {log.user_id}'
        
        results.append({
            'id': log.id,
            'user_id': log.user_id,
            'user_name': user_name,
            'app_name': log.app_name,
            'model_name': log.model_name,
            'object_id': log.object_id,
            'field_name': log.field_name,
            'old_value': log.old_value,
            'new_value': log.new_value,
            'action_type': log.action_type,
            'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # لیست کاربران و فیلدها برای فیلتر
    users = []
    fields = []
    
    if page == 1:  # فقط در صفحه اول لیست‌ها را ارسال کن
        users_ids = BulkEditLog.objects.filter(
            Q(app_name=app_name) if app_name else Q()
        ).filter(
            Q(model_name=model_name) if model_name else Q()
        ).values_list('user_id', flat=True).distinct()
        
        for user_id in users_ids:
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    users.append({
                        'id': user_id,
                        'username': user.get_full_name() or user.username
                    })
                except User.DoesNotExist:
                    users.append({'id': user_id, 'username': f'کاربر {user_id}'})
        
        fields = BulkEditLog.objects.filter(
            Q(app_name=app_name) if app_name else Q()
        ).filter(
            Q(model_name=model_name) if model_name else Q()
        ).values_list('field_name', flat=True).distinct()
        fields = sorted(list(set(fields)))
    
    # ارسال پاسخ
    response_data = {
        'count': paginator.count,
        'page_size': page_size,
        'pages': paginator.num_pages,
        'current_page': page,
        'results': results,
        'users': users,
        'fields': fields
    }
    
    return JsonResponse(response_data)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def restore_value_api(request):
    """API برای بازگرداندن مقدار فیلد به مقدار قبلی"""
    from .models import BulkEditLog
    from django.apps import apps
    import json
    
    # تنظیم لاگر
    logger = logging.getLogger(__name__)
    logger.info("Restore value API called")
    
    try:
        # بررسی محتوای درخواست
        if request.body:
            try:
                data = json.loads(request.body)
                logger.info(f"Received data: {data}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return JsonResponse({'success': False, 'error': 'خطا در خواندن داده‌های JSON'})
        else:
            logger.error("Request body is empty")
            return JsonResponse({'success': False, 'error': 'بدنه درخواست خالی است'})
        
        # دریافت پارامترهای لازم
        app_name = data.get('app_name')
        model_name = data.get('model_name')
        object_id = data.get('object_id')
        field_name = data.get('field_name')
        value = data.get('value')
        
        logger.info(f"Parsed parameters: app_name={app_name}, model_name={model_name}, object_id={object_id}, field_name={field_name}")
        
        # بررسی وجود تمام پارامترهای لازم
        if not all([app_name, model_name, object_id, field_name]):
            missing = []
            if not app_name: missing.append('app_name')
            if not model_name: missing.append('model_name')
            if not object_id: missing.append('object_id')
            if not field_name: missing.append('field_name')
            
            logger.error(f"Missing parameters: {missing}")
            return JsonResponse({'success': False, 'error': f'پارامترهای ناقص: {", ".join(missing)}'})
        
        # دسترسی به مدل و آبجکت مورد نظر
        try:
            model = apps.get_model(app_name, model_name)
            logger.info(f"Found model: {model}")
            
            obj = model.objects.get(id=object_id)
            logger.info(f"Found object with ID {object_id}")
        except Exception as e:
            logger.error(f"Error accessing object: {str(e)}")
            return JsonResponse({'success': False, 'error': f'خطا در دسترسی به آبجکت: {str(e)}'})
        
        # بررسی وجود فیلد در مدل
        if not hasattr(obj, field_name):
            logger.error(f"Field {field_name} not found in model {model_name}")
            return JsonResponse({'success': False, 'error': f'فیلد {field_name} در مدل {model_name} وجود ندارد'})
        
        # دریافت مقدار فعلی برای ثبت در لاگ
        old_value = getattr(obj, field_name)
        logger.info(f"Current value of {field_name}: {old_value}")
        
        try:
            # تبدیل داده به نوع مناسب بر اساس فیلد
            field = model._meta.get_field(field_name)
            logger.info(f"Field type: {field.get_internal_type()}")
            
            # ذخیره مقدار جدید
            setattr(obj, field_name, value)
            obj.save(update_fields=[field_name])
            logger.info(f"Value updated successfully to: {value}")
            
            # ثبت لاگ تغییرات
            log_entry = BulkEditLog.objects.create(
                user=request.user,
                app_name=app_name,
                model_name=model_name,
                object_id=object_id,
                field_name=field_name,
                old_value=str(old_value),
                new_value=str(value),
                action_type='UPDATE'
            )
            logger.info(f"Created log entry with ID: {log_entry.id}")
            
            return JsonResponse({'success': True, 'message': 'مقدار با موفقیت بازگردانی شد'})
            
        except Exception as e:
            logger.error(f"Error updating value: {str(e)}")
            return JsonResponse({'success': False, 'error': f'خطا در بروزرسانی مقدار: {str(e)}'})
            
    except Exception as e:
        logger.error(f"System error: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'خطای سیستمی: {str(e)}'})
