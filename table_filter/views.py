from django.shortcuts import render, redirect
from core.decorators.decorators import role_required
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
import pandas as pd

# Create your views here.

def table_filter_demo(request):
    """
    نمایش صفحه نمونه برای فیلتر جداول
    """
    return render(request, 'table_filter/demo.html')

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def bulk_edit_page(request):
    """نمایش صفحه ویرایش گروهی"""
    selected_ids = request.GET.get('ids', '').split(',')
    selected_ids = [id.strip() for id in selected_ids if id.strip()]
    
    model_name = request.GET.get('model', '')
    app_name = request.GET.get('app', 'core')
    table_type = request.GET.get('table_type', '')
    
    print(f"DEBUG - Received parameters: model_name={model_name}, app_name={app_name}, table_type={table_type}, selected_ids={selected_ids}")
    
    if not selected_ids:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': 'هیچ موردی انتخاب نشده است'
        })
    
    # تشخیص مدل
    if not model_name:
        referer = request.META.get('HTTP_REFERER', '')
        print(f"DEBUG - Referer URL: {referer}")
        if 'purchase' in referer:
            model_name = 'Purchase'
            table_type = 'purchase'
        elif 'customer' in referer:
            model_name = 'Customer'
            table_type = 'customer'
        elif 'cargo_product' in referer or 'cargo-product' in referer:
            model_name = 'CargoProduct'
            table_type = 'cargo_product'
    
    # اگر model_name مشخص شده ولی table_type نه، آن را تشخیص دهیم
    if model_name and not table_type:
        if model_name == 'Purchase':
            table_type = 'purchase'
        elif model_name == 'Customer':
            table_type = 'customer'
        elif model_name == 'CargoProduct':
            table_type = 'cargo_product'
    
    print(f"DEBUG - Final parameters: model_name={model_name}, app_name={app_name}, table_type={table_type}")
    
    try:
        model = apps.get_model(app_name, model_name)
        print(f"DEBUG - Model found: {model.__name__}")
    except LookupError as e:
        print(f"DEBUG - LookupError: {e}")
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': f'مدل {model_name} در اپلیکیشن {app_name} یافت نشد'
        })
    
    # دریافت آبجکت‌های انتخاب شده
    objects = model.objects.filter(id__in=selected_ids)
    print(f"DEBUG - Found {objects.count()} objects")
    
    # دریافت فیلدهای قابل ویرایش
    editable_fields = get_editable_fields(model, table_type, selected_ids)
    print(f"DEBUG - Editable fields count: {len(editable_fields)}")
    print(f"DEBUG - Editable fields: {[f['name'] for f in editable_fields]}")
    
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

def get_editable_fields(model, table_type, selected_ids=None):
    """دریافت فیلدهای قابل ویرایش برای هر مدل به صورت کاملاً دینامیک"""
    
    # فیلدهایی که نباید ویرایش شوند
    excluded_fields = [
        'id', 'pk', 'created_at', 'updated_at', 'last_modified', 
        'date_joined', 'password', 'last_login', 'groups', 'user_permissions',
        'registration_date', 'total_purchase_weight', 'field_of_activity_list', 
        'purchase_preferences_list', 'product_preferences_list', 'phone_numbers'
    ]
    
    # فیلدهایی که منحصر به فرد هستند و نباید در ویرایش گروهی نمایش داده شوند
    unique_identifier_fields = {
        'Purchase': ['purchase_number', 'invoice_id'],
        'Customer': ['name', 'phone_number', 'city', 'address', 'quota', 'social_media', 'national_code', 'added_description'],
        'CargoProduct': ['cottage', 'invoice_id'],
        'Barbary': ['name'],
        'VaredKonandeh': ['name'],
    }
    
    model_name = model.__name__
    
    # اگر بیش از یک مورد انتخاب شده، فیلدهای منحصر به فرد را حذف کن
    excluded_for_bulk = []
    if selected_ids and len(selected_ids) > 1:
        unique_identifiers = unique_identifier_fields.get(model_name, [])
        excluded_for_bulk.extend(unique_identifiers)
        print(f"DEBUG - Excluding unique identifier fields for bulk edit: {unique_identifiers}")
    
    fields = []
    
    print(f"DEBUG - Processing model: {model_name}")
    print(f"DEBUG - All model fields: {[f.name for f in model._meta.get_fields()]}")
    
    # پردازش همه فیلدها (نه فقط فیلدهای مهم)
    for field in model._meta.get_fields():
        print(f"DEBUG - Processing field: {field.name}, type: {type(field).__name__}")
        
        # رد کردن فیلدهای غیرقابل ویرایش
        if field.name in excluded_fields:
            print(f"DEBUG - Excluding field {field.name} (in excluded list)")
            continue
            
        # رد کردن فیلدهای منحصر به فرد در ویرایش گروهی
        if field.name in excluded_for_bulk:
            print(f"DEBUG - Excluding field {field.name} (unique identifier for bulk edit)")
            continue
            
        # رد کردن فیلدهای reverse relation
        if hasattr(field, 'related_model') and hasattr(field, 'remote_field'):
            if field.remote_field and not hasattr(field, 'model'):
                print(f"DEBUG - Excluding field {field.name} (reverse relation)")
                continue
        
        # رد کردن فیلدهای ManyToMany که پیچیده هستند
        if hasattr(field, 'many_to_many') and field.many_to_many:
            print(f"DEBUG - Excluding field {field.name} (many_to_many)")
            continue
        
        # فقط فیلدهای واقعی مدل را در نظر بگیر
        if not hasattr(field, 'get_internal_type'):
            print(f"DEBUG - Excluding field {field.name} (no internal type)")
            continue
        
        # تعیین نوع فیلد
        field_type = 'text'
        field_choices = None
        
        # بررسی نوع فیلد Django
        internal_type = field.get_internal_type()
        print(f"DEBUG - Field {field.name} internal type: {internal_type}")
        
        if internal_type == 'BooleanField':
            field_type = 'checkbox'
        elif internal_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'SmallIntegerField']:
            field_type = 'number'
        elif internal_type in ['FloatField', 'DecimalField']:
            field_type = 'number'
        elif internal_type in ['TextField']:
            field_type = 'textarea'
        elif internal_type in ['DateField']:
            field_type = 'date'
        elif internal_type in ['DateTimeField']:
            field_type = 'datetime-local'
        elif internal_type in ['TimeField']:
            field_type = 'time'
        elif internal_type == 'EmailField':
            field_type = 'email'
        elif internal_type == 'URLField':
            field_type = 'url'
        elif internal_type == 'ForeignKey':
            field_type = 'select'
            # دریافت گزینه‌های ForeignKey
            try:
                related_model = field.related_model
                field_choices = [(obj.id, str(obj)) for obj in related_model.objects.all()[:100]]  # محدود به 100 مورد
                print(f"DEBUG - Relation field {field.name} has {len(field_choices)} choices")
            except Exception as e:
                print(f"DEBUG - Error getting relation choices for {field.name}: {e}")
                field_choices = []
        
        # بررسی وجود choices در فیلد
        if hasattr(field, 'choices') and field.choices:
            field_type = 'select'
            field_choices = field.choices
            print(f"DEBUG - Field {field.name} has choices: {len(field_choices)}")
        
        # تعیین برچسب فیلد با برچسب‌های فارسی مناسب برای Purchase
        if model_name == 'Purchase':
            field_labels = {
                'order_weight': 'وزن سفارش (کیلوگرم)',
                'delivered_weight': 'وزن بارنامه شده (کیلوگرم)',
                'company_price': 'فی خرید (ریال)',
                'customer_price': 'فی فروش (ریال)',
                'amount_paid': 'مبلغ پرداختی (ریال)',
                'state': 'وضعیت',
                'is_urgent': 'فوری',
                'is_canceled': 'لغو شده',
                'is_archived': 'آرشیو شده',
                'is_fully_tasvied': 'تسویه کامل',
                'is_factored': 'فاکتور صادر شده',
                'priority': 'اولویت',
                'address': 'آدرس',
                'description': 'توضیحات',
                'tracking_number': 'شماره پیگیری',
                'bazaargah_phone_number': 'شماره تلفن بازارگاه',
                'buyer_name': 'نام خریدار',
                'tahvil_phone_number': 'شماره تلفن تحویل',
                'code_melli_tahvil': 'کد ملی تحویل',
                'send_cottage_sms': 'ارسال پیامک کوتاژ',
                'total_weight': 'وزن کل (کیلوگرم)',
                'type': 'نوع خرید',
                'payment_method': 'شیوه پرداخت',
                'is_weight_costed': 'کسر از وزن موجود',
                'is_ap_af': 'اتوکامپلیت شده',
                'extelaf_type': 'نوع اختلاف',
                'extelaf_weight': 'وزن اختلاف (کیلوگرم)',
                'extelaf_amount': 'مبلغ اختلاف (ریال)',
                'priority_reason': 'دلیل اولویت',
                'factor_code': 'فاکتور مبنا'
            }
            field_label = field_labels.get(field.name, getattr(field, 'verbose_name', field.name.replace('_', ' ').title()))
        else:
            field_label = getattr(field, 'verbose_name', None)
            if not field_label:
                field_label = field.name.replace('_', ' ').title()
        
        # بررسی یکتا بودن فیلد
        is_unique = False
        if hasattr(field, 'unique'):
            is_unique = field.unique
        if hasattr(field, 'primary_key'):
            is_unique = is_unique or field.primary_key
        
        # ساخت دیکشنری فیلد
        field_data = {
            'name': field.name,
            'label': str(field_label),
            'type': field_type,
            'is_unique': is_unique,
        }
        
        # اضافه کردن choices اگر وجود دارد
        if field_choices:
            field_data['choices'] = field_choices
        
        # اضافه کردن محدودیت‌های اضافی
        if hasattr(field, 'max_length') and field.max_length:
            field_data['max_length'] = field.max_length
            
        if hasattr(field, 'null') and field.null:
            field_data['nullable'] = True
            
        if hasattr(field, 'blank') and field.blank:
            field_data['optional'] = True
            
        # اضافه کردن متن راهنما
        if hasattr(field, 'help_text') and field.help_text:
            field_data['help_text'] = str(field.help_text)
        
        fields.append(field_data)
        print(f"DEBUG - Added field: {field.name} as {field_type}")
    
    # مرتب‌سازی فیلدها بر اساس نام
    fields.sort(key=lambda x: x['name'])
    
    print(f"DEBUG - Final editable fields: {[f['name'] for f in fields]}")
    return fields

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def bulk_edit_excel_page(request):
    """نمایش صفحه ویرایش با اکسل"""
    selected_ids = request.GET.get('selected_ids', '').split()
    selected_ids = [id.strip() for id in selected_ids if id.strip()]
    
    model_name = request.GET.get('model', '')
    app_name = request.GET.get('app', 'core')
    table_type = request.GET.get('table_type', '')
    
    print(f"DEBUG - Excel page: model_name={model_name}, app_name={app_name}, table_type={table_type}")
    print(f"DEBUG - Selected IDs: {selected_ids}")
    
    if not selected_ids:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': 'هیچ موردی انتخاب نشده است'
        })
    
    # تشخیص مدل
    if not model_name:
        referer = request.META.get('HTTP_REFERER', '')
        print(f"DEBUG - Excel page referer: {referer}")
        if 'purchase' in referer:
            model_name = 'Purchase'
            table_type = 'purchase'
        elif 'customer' in referer:
            model_name = 'Customer'
            table_type = 'customer'
        elif 'cargo_product' in referer or 'cargo-product' in referer:
            model_name = 'CargoProduct'
            table_type = 'cargo_product'
    
    # اگر model_name مشخص شده ولی table_type نه، آن را تشخیص دهیم
    if model_name and not table_type:
        if model_name == 'Purchase':
            table_type = 'purchase'
        elif model_name == 'Customer':
            table_type = 'customer'
        elif model_name == 'CargoProduct':
            table_type = 'cargo_product'
    
    # دریافت مدل
    from django.apps import apps
    try:
        model = apps.get_model(app_name, model_name)
    except LookupError:
        return render(request, 'table_filter/bulk_edit_error.html', {
            'error': f'مدل {model_name} در اپلیکیشن {app_name} یافت نشد'
        })
    
    # دریافت آبجکت‌های انتخاب شده
    objects = model.objects.filter(id__in=selected_ids)
    
    context = {
        'selected_count': len(selected_ids),
        'selected_ids_str': ' '.join(selected_ids),  # برای URL در template
        'selected_ids': selected_ids,  # لیست برای loop در template
        'objects': objects,
        'model_name': model_name,
        'app_name': app_name,
        'table_type': table_type,
    }
    
    return render(request, 'table_filter/bulk_edit_excel.html', context)

@role_required('admin', 'logistics_manager', 'financial_manager')
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
            elif 'vared_konandeh' in referer:
                model_name = 'VaredKonandeh'
                app_name = 'core'
            elif 'cargo_product' in referer:
                model_name = 'CargoProduct'
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
        
        # پردازش فیلدهای مختلف - فقط فیلدهایی که مقدار دارند
        for field_name, value in request.POST.items():
            if field_name in ['selected_ids', 'model_name', 'app_name', 'csrfmiddlewaretoken']:
                continue
            
            # بررسی وجود فیلد در مدل ابتدا
            try:
                field = model._meta.get_field(field_name)
            except FieldDoesNotExist:
                continue
                
            # فقط فیلدهایی که مقدار دارند را پردازش کن
            if value is not None and str(value).strip():
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
                    update_data[field_name] = value.lower() in ['true', '1', 'yes', 'on', 'بله', 'فعال']
                elif field.get_internal_type() == 'ForeignKey':
                    # برای ForeignKey، مقدار باید ID باشد
                    try:
                        if value and value != '':
                            update_data[field_name + '_id'] = int(value)
                    except (ValueError, TypeError):
                        continue
                else:
                    update_data[field_name] = value
            
            # پردازش ویژه برای چک‌باکس‌ها - فقط اگر explicitly sent شده باشند
            elif field.get_internal_type() == 'BooleanField':
                # اگر چک‌باکس در POST است، یعنی true است
                if field_name in request.POST:
                    update_data[field_name] = True
                # اگر نیست و فیلد از نوع بولین است، False کن (فقط برای فیلدهای مشخص)
                elif field_name in ['is_urgent', 'is_factored', 'is_archived', 'is_canceled', 'is_weight_costed', 'is_ap_af', 'is_fully_tasvied', 'is_active', 'is_blocked', 'is_favorite', 'whatsapp_preference', 'sms_preference', 'is_bazaargah_enjoyer']:
                    # فقط اگر در form موجود بود ولی انتخاب نشده
                    form_checkbox_names = [name for name in request.POST.keys() if name.startswith('checkbox_') or name in ['is_urgent', 'is_factored', 'is_archived', 'is_canceled', 'is_weight_costed', 'is_ap_af', 'is_fully_tasvied', 'is_active', 'is_blocked', 'is_favorite', 'whatsapp_preference', 'sms_preference', 'is_bazaargah_enjoyer']]
                    if any(field_name in name for name in form_checkbox_names):
                        update_data[field_name] = False
        
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

@role_required('admin', 'logistics_manager', 'financial_manager')
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
        
        print(f"DEBUG - Bulk Excel: uploaded file: {excel_file.name}")
        print(f"DEBUG - Bulk Excel: selected_ids from POST: {selected_ids}")
        
        if not selected_ids:
            from django.contrib import messages
            messages.error(request, 'هیچ موردی انتخاب نشده است')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # تشخیص نوع مدل
        table_type = request.POST.get('table_type', 'Purchase')
        model_name = request.POST.get('model_name', 'Purchase')
        app_name = request.POST.get('app_name', 'core')
        
        print(f"DEBUG - Table type: {table_type}, Model: {model_name}, App: {app_name}")
        
        # دریافت مدل
        from django.apps import apps
        try:
            model = apps.get_model(app_name, model_name)
        except Exception as e:
            print(f"DEBUG - Error getting model: {e}")
            from django.contrib import messages
            messages.error(request, f'مدل یافت نشد: {e}')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # خواندن فایل اکسل
        try:
            # خواندن اکسل با دقت زیاد
            df = pd.read_excel(excel_file, engine='openpyxl')
            print(f"DEBUG - Excel file read successfully. Shape: {df.shape}")
            print(f"DEBUG - Excel columns: {list(df.columns)}")
            print(f"DEBUG - Excel head:\n{df.head()}")
            
            # پاک کردن ردیف‌های خالی
            df = df.dropna(how='all')
            
            # بررسی وجود ستون ID
            if 'ID' not in df.columns:
                from django.contrib import messages
                messages.error(request, 'ستون ID در فایل اکسل یافت نشد')
                return redirect(request.META.get('HTTP_REFERER', '/'))
            
        except Exception as e:
            print(f"DEBUG - Error reading Excel file: {e}")
            from django.contrib import messages
            messages.error(request, f'خطا در خواندن فایل اکسل: {e}')
            return redirect(request.META.get('HTTP_REFERER', '/'))
        
        # پردازش تغییرات - رویکرد ساده‌تر
        changes_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                obj_id = int(row['ID'])
                print(f"DEBUG - Processing row {index}: ID={obj_id}")
                
                # بررسی اینکه آیا این ID در لیست انتخاب شده‌ها هست
                if str(obj_id) not in selected_ids:
                    print(f"DEBUG - Skipping ID {obj_id} - not in selected list")
                    continue
                
                # دریافت object
                try:
                    obj = model.objects.get(id=obj_id)
                    print(f"DEBUG - Found object: {obj}")
                except model.DoesNotExist:
                    print(f"DEBUG - Object with ID {obj_id} not found")
                    errors.append(f'آبجکت با شناسه {obj_id} یافت نشد')
                    continue
                
                # بررسی و اعمال تغییرات
                obj_changed = False
                field_changes = {}
                
                # پردازش همه ستون‌های اکسل (به جز ID)
                for excel_column in df.columns:
                    if excel_column == 'ID':
                        continue
                    
                    # دریافت مقدار جدید از اکسل
                    new_value = row[excel_column]
                    
                    # اگر مقدار NaN باشد، رد کن
                    if pd.isna(new_value):
                        print(f"DEBUG - Skipping {excel_column} - value is NaN")
                        continue
                    
                    # تلاش برای پیدا کردن فیلد متناظر
                    field_name = _find_matching_field(model, excel_column)
                    if not field_name:
                        print(f"DEBUG - No matching field found for column: {excel_column}")
                        continue
                    
                    print(f"DEBUG - Processing column '{excel_column}' -> field '{field_name}' with value '{new_value}'")
                    
                    # دریافت مقدار فعلی از object
                    try:
                        current_value = getattr(obj, field_name)
                        print(f"DEBUG - Field {field_name}: current='{current_value}', new='{new_value}'")
                        
                        # تبدیل و مقایسه مقادیر
                        processed_new_value = _process_field_value_simple(obj, field_name, new_value, model)
                        
                        # مقایسه ساده
                        if str(current_value) != str(processed_new_value):
                            print(f"DEBUG - Change detected! Setting {field_name} from '{current_value}' to '{processed_new_value}'")
                            
                            setattr(obj, field_name, processed_new_value)
                            field_changes[field_name] = {
                                'old': current_value,
                                'new': processed_new_value
                            }
                            obj_changed = True
                        else:
                            print(f"DEBUG - No change for {field_name} (same value)")
                        
                    except Exception as e:
                        print(f"DEBUG - Error processing field {field_name}: {e}")
                        errors.append(f'خطا در پردازش فیلد {field_name} برای آبجکت {obj_id}: {e}')
                        continue
                
                # ذخیره تغییرات
                if obj_changed:
                    obj.save()
                    changes_count += 1
                    
                    print(f"DEBUG - Object {obj_id} updated with changes: {field_changes}")
                    
                    # ثبت تاریخچه تغییرات
                    try:
                        _log_bulk_edit_changes(request.user, obj, field_changes)
                    except Exception as e:
                        print(f"DEBUG - Error logging changes: {e}")
                else:
                    print(f"DEBUG - No changes detected for object {obj_id}")
                    
            except Exception as e:
                print(f"DEBUG - Error processing row {index}: {e}")
                errors.append(f'خطا در پردازش ردیف {index + 2}: {e}')
                continue
        
        # نمایش نتایج
        from django.contrib import messages
        if changes_count > 0:
            messages.success(request, f'{changes_count} مورد با موفقیت ویرایش شد')
        else:
            messages.warning(request, 'هیچ تغییری اعمال نشد - ممکن است داده‌های اکسل با داده‌های فعلی یکسان باشند')
        
        if errors:
            for error in errors[:5]:  # نمایش حداکثر 5 خطا
                messages.error(request, error)
            if len(errors) > 5:
                messages.error(request, f'و {len(errors) - 5} خطای دیگر...')
        
        return redirect(request.META.get('HTTP_REFERER', '/'))
        
    except Exception as e:
        print(f"DEBUG - General error in bulk_edit_excel_view: {e}")
        import traceback
        print(f"DEBUG - Traceback: {traceback.format_exc()}")
        from django.contrib import messages
        messages.error(request, f'خطای کلی: {e}')
        return redirect(request.META.get('HTTP_REFERER', '/'))

def _create_field_mapping(model, fields, excel_columns):
    """ایجاد mapping بین فیلدهای مدل و ستون‌های اکسل"""
    mapping = {}
    
    print(f"DEBUG - Creating field mapping for {len(fields)} fields and {len(excel_columns)} excel columns")
    
    # ایجاد دیکشنری برای سهولت جستجو
    field_dict = {}
    for field in fields:
        field_dict[field['name']] = field['label']
    
    print(f"DEBUG - Available fields: {list(field_dict.keys())}")
    print(f"DEBUG - Excel columns: {excel_columns}")
    
    # mapping دقیق بین headers و field names
    for excel_column in excel_columns:
        if excel_column == 'ID':
            continue  # Skip ID column
            
        # جستجوی مستقیم با نام فیلد
        if excel_column in field_dict:
            mapping[excel_column] = excel_column
            print(f"DEBUG - Direct mapping: {excel_column} -> {excel_column}")
            continue
        
        # جستجوی با label
        for field_name, field_label in field_dict.items():
            if excel_column == field_label:
                mapping[excel_column] = field_name
                print(f"DEBUG - Label mapping: {excel_column} -> {field_name}")
                break
        
        # اگر هنوز پیدا نشد، جستجوی fuzzy
        if excel_column not in mapping:
            # normalize کردن برای مقایسه بهتر
            normalized_excel = excel_column.lower().strip()
            
            for field_name, field_label in field_dict.items():
                normalized_label = field_label.lower().strip()
                normalized_field = field_name.lower().strip()
                
                # چک کردن شباهت
                if (normalized_excel == normalized_label or 
                    normalized_excel == normalized_field or
                    normalized_excel in normalized_label or
                    normalized_label in normalized_excel):
                    mapping[excel_column] = field_name
                    print(f"DEBUG - Fuzzy mapping: {excel_column} -> {field_name}")
                    break
    
    print(f"DEBUG - Final mapping: {mapping}")
    return mapping

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def download_excel_template_view(request):
    """دانلود قالب اکسل برای ویرایش گروهی"""
    try:
        table_type = request.GET.get('table_type', 'purchase')
        model_name = request.GET.get('model', 'Purchase')
        app_name = request.GET.get('app', 'core')
        selected_ids = request.GET.get('selected_ids', '').split()
        
        print(f"DEBUG - Template download: table_type={table_type}, model={model_name}, app={app_name}")
        print(f"DEBUG - Template download: selected_ids={selected_ids}")
        
        # دریافت مدل
        from django.apps import apps
        try:
            model = apps.get_model(app_name, model_name)
        except Exception as e:
            print(f"DEBUG - Error getting model for template: {e}")
            from django.http import HttpResponse
            return HttpResponse('مدل یافت نشد', status=400)
        
        # دریافت فیلدهای قابل ویرایش
        editable_fields = get_editable_fields(model, table_type, selected_ids)
        print(f"DEBUG - Template fields: {[f['name'] for f in editable_fields]}")
        
        # دریافت آبجکت‌های انتخاب شده
        objects = model.objects.filter(id__in=selected_ids)
        print(f"DEBUG - Template objects count: {objects.count()}")
        
        # ساخت فایل اکسل
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from django.http import HttpResponse
        
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = f"{model_name} Template"
        
        # تنظیم هدرها
        headers = ['ID']  # شروع با ستون ID
        for field in editable_fields:
            headers.append(field['label'])
        
        print(f"DEBUG - Template headers: {headers}")
        
        # نوشتن هدرها
        for col_num, header in enumerate(headers, 1):
            cell = worksheet.cell(row=1, column=col_num)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # نوشتن داده‌ها
        for row_num, obj in enumerate(objects, 2):
            # ستون ID
            worksheet.cell(row=row_num, column=1, value=obj.id)
            
            # سایر ستون‌ها
            for col_num, field in enumerate(editable_fields, 2):
                field_name = field['name']
                try:
                    value = getattr(obj, field_name)
                    
                    # تبدیل مقدار برای نمایش در اکسل
                    if isinstance(value, bool):
                        display_value = 'بله' if value else 'خیر'
                    elif value is None:
                        display_value = ''
                    elif hasattr(value, '__call__'):  # برای method ها
                        display_value = str(value())
                    else:
                        display_value = str(value)
                    
                    worksheet.cell(row=row_num, column=col_num, value=display_value)
                    
                except Exception as e:
                    print(f"DEBUG - Error getting field {field_name} for object {obj.id}: {e}")
                    worksheet.cell(row=row_num, column=col_num, value='')
        
        # تنظیم عرض ستون‌ها
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # ایجاد HttpResponse
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"{model_name}_template_{len(selected_ids)}_items.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # ذخیره workbook در response
        workbook.save(response)
        
        print(f"DEBUG - Template created successfully: {filename}")
        return response
        
    except Exception as e:
        print(f"DEBUG - Error creating template: {e}")
        import traceback
        print(f"DEBUG - Traceback: {traceback.format_exc()}")
        from django.http import HttpResponse
        return HttpResponse(f'خطا در ایجاد قالب: {e}', status=500)

def get_field_name_from_header(header, model_name):
    """Map Excel header to model field name به صورت دینامیک"""
    try:
        # دریافت مدل
        model = apps.get_model('core', model_name)
        
        # جستجو در فیلدهای مدل
        for field in model._meta.get_fields():
            # بررسی verbose_name
            if hasattr(field, 'verbose_name') and field.verbose_name:
                if field.verbose_name.strip() == header.strip():
                    return field.name
            
            # بررسی نام فیلد به صورت مستقیم
            if field.name == header:
                return field.name
        
        # جستجوی فازی برای موارد مشابه
        header_lower = header.lower().strip()
        for field in model._meta.get_fields():
            field_name_lower = field.name.lower()
            if hasattr(field, 'verbose_name') and field.verbose_name:
                verbose_name_lower = field.verbose_name.lower().strip()
                
                # بررسی تشابه کلمات کلیدی
                if ('کوتاژ' in header_lower and 'cottage' in field_name_lower) or \
                   ('محصول' in header_lower and 'product' in field_name_lower) or \
                   ('کشور' in header_lower and 'country' in field_name_lower) or \
                   ('وزن' in header_lower and 'weight' in field_name_lower) or \
                   ('قیمت' in header_lower and 'price' in field_name_lower) or \
                   ('توضیحات' in header_lower and 'description' in field_name_lower) or \
                   ('وضعیت' in header_lower and 'status' in field_name_lower) or \
                   ('نام' in header_lower and 'name' in field_name_lower) or \
                   ('تلفن' in header_lower and 'phone' in field_name_lower) or \
                   ('آدرس' in header_lower and 'address' in field_name_lower):
                    return field.name
        
        return None
        
    except Exception as e:
        print(f"Error in get_field_name_from_header: {e}")
        return None

def convert_excel_value(value, field):
    """Convert Excel cell value to appropriate field type"""
    if field.get_internal_type() in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField']:
        return int(float(value)) if value else 0
    elif field.get_internal_type() in ['FloatField', 'DecimalField']:
        return float(value) if value else 0.0
    elif field.get_internal_type() == 'BooleanField':
        return str(value).lower() in ['بله', 'yes', 'true', '1']
    else:
        return str(value) if value else ''

def get_excel_headers_fields(table_type, selected_ids=None):
    """بازگرداندن لیست هدرهای اکسل و فیلدهای متناظر به صورت دینامیک"""
    try:
        # تبدیل table_type به model_name
        model_map = {
            'purchase': 'Purchase',
            'customer': 'Customer',
            'barbary': 'Barbary',
            'cargo_product': 'CargoProduct',
            'vared_konandeh': 'VaredKonandeh'
        }
        model_name = model_map.get(table_type)
        
        if not model_name:
            print(f"DEBUG - get_excel_headers_fields: Unknown table_type {table_type}")
            return []
        
        # دریافت مدل
        try:
            model = apps.get_model('core', model_name)
            print(f"DEBUG - get_excel_headers_fields: Found model {model.__name__}")
        except LookupError as e:
            print(f"DEBUG - get_excel_headers_fields: LookupError {e}")
            return []
        
        # دریافت فیلدهای قابل ویرایش
        editable_fields = get_editable_fields(model, table_type, selected_ids)
        print(f"DEBUG - get_excel_headers_fields: Found {len(editable_fields)} editable fields")
        
        # تبدیل به فرمت مورد نیاز برای اکسل
        headers_fields = []
        for field_data in editable_fields:
            header = field_data['label']
            field_name = field_data['name']
            headers_fields.append((header, field_name))
        
        return headers_fields
        
    except Exception as e:
        print(f"Error in get_excel_headers_fields: {e}")
        import traceback
        traceback.print_exc()
        return []

@role_required('admin', 'logistics_manager', 'financial_manager')
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

@role_required('admin', 'logistics_manager', 'financial_manager')
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

@role_required('admin', 'logistics_manager', 'financial_manager')
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

def _normalize_value_for_comparison(value):
    """تبدیل مقدار به فرمت استاندارد برای مقایسه"""
    if value is None:
        return None
    
    # تبدیل boolean
    if isinstance(value, bool):
        return value
    
    # تبدیل عدد
    if isinstance(value, (int, float)):
        return float(value)
    
    # تبدیل رشته
    if isinstance(value, str):
        # حذف فاصله‌های اضافی
        value = value.strip()
        
        # تبدیل مقادیر فارسی boolean
        if value.lower() in ['بله', 'yes', 'true', '1']:
            return True
        if value.lower() in ['خیر', 'no', 'false', '0']:
            return False
        
        # تلاش برای تبدیل به عدد
        try:
            if '.' in value:
                return float(value)
            else:
                return float(int(value))
        except (ValueError, TypeError):
            pass
        
        return value
    
    # سایر موارد
    return str(value)

def _process_field_value(obj, field_name, value, model):
    """پردازش مقدار فیلد بر اساس نوع فیلد"""
    try:
        field = model._meta.get_field(field_name)
        field_type = field.get_internal_type()
        
        print(f"DEBUG - Processing field {field_name} with type {field_type}, value: {value}")
        
        # اگر مقدار خالی باشد
        if value is None or (isinstance(value, str) and value.strip() == ''):
            if field.null:
                return None
            elif field_type == 'BooleanField':
                return False
            else:
                return value
        
        # پردازش بر اساس نوع فیلد
        if field_type == 'BooleanField':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                value = value.strip().lower()
                return value in ['بله', 'yes', 'true', '1', 'فعال']
            return bool(value)
        
        elif field_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'SmallIntegerField']:
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                # حذف کاما و فاصله
                value = value.replace(',', '').replace(' ', '')
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    pass
            return int(value)
        
        elif field_type in ['FloatField', 'DecimalField']:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # حذف کاما و فاصله
                value = value.replace(',', '').replace(' ', '')
                try:
                    return float(value)
                except (ValueError, TypeError):
                    pass
            return float(value)
        
        elif field_type == 'ForeignKey':
            # اگر مقدار یک ID است
            if isinstance(value, (int, float)):
                try:
                    related_model = field.related_model
                    return related_model.objects.get(id=int(value))
                except related_model.DoesNotExist:
                    return None
            # اگر مقدار یک رشته است (نام object)
            elif isinstance(value, str):
                try:
                    related_model = field.related_model
                    # جستجو بر اساس نام یا __str__
                    if hasattr(related_model, 'name'):
                        return related_model.objects.get(name=value)
                    else:
                        # جستجو در تمام رکوردها
                        for obj in related_model.objects.all():
                            if str(obj) == value:
                                return obj
                        return None
                except:
                    return None
            return value
        
        else:
            # سایر فیلدها (TextField, CharField, etc.)
            return str(value)
            
    except Exception as e:
        print(f"DEBUG - Error processing field {field_name}: {e}")
        return value

def _log_bulk_edit_changes(user, obj, field_changes):
    """ثبت تغییرات ویرایش گروهی در سیستم لاگ"""
    try:
        from .models import BulkEditLog
        
        # ثبت هر تغییر به صورت جداگانه
        for field_name, change in field_changes.items():
            BulkEditLog.objects.create(
                user=user,
                app_name=obj._meta.app_label,
                model_name=obj._meta.model_name,
                object_id=str(obj.id),
                field_name=field_name,
                old_value=str(change['old']) if change['old'] is not None else '',
                new_value=str(change['new']) if change['new'] is not None else '',
                action_type='EXCEL'
            )
        
        print(f"DEBUG - Logged {len(field_changes)} changes for object {obj.id}")
        
    except Exception as e:
        print(f"DEBUG - Error logging changes: {e}")
        pass

def _find_matching_field(model, excel_column):
    """پیدا کردن فیلد متناظر با ستون اکسل"""
    
    # ابتدا بررسی مستقیم نام فیلد
    try:
        field = model._meta.get_field(excel_column)
        print(f"DEBUG - Direct field match: {excel_column}")
        return excel_column
    except:
        pass
    
    # mapping خاص برای مدل Purchase
    if model.__name__ == 'Purchase':
        purchase_mappings = {
            'وزن سفارش (کیلوگرم)': 'order_weight',
            'وزن بارنامه شده (کیلوگرم)': 'delivered_weight', 
            'فی خرید (ریال)': 'company_price',
            'فی فروش (ریال)': 'customer_price',
            'مبلغ پرداختی (ریال)': 'amount_paid',
            'وضعیت': 'state',
            'فوری': 'is_urgent',
            'لغو شده': 'is_canceled',
            'آرشیو شده': 'is_archived',
            'تسویه کامل': 'is_fully_tasvied',
            'فاکتور صادر شده': 'is_factored',
            'اولویت': 'priority',
            'آدرس': 'address',
            'توضیحات': 'description',
            'شماره پیگیری': 'tracking_number',
            'شماره تلفن بازارگاه': 'bazaargah_phone_number',
            'نام خریدار': 'buyer_name',
            'شماره تلفن تحویل': 'tahvil_phone_number',
            'کد ملی تحویل': 'code_melli_tahvil',
            'ارسال پیامک کوتاژ': 'send_cottage_sms',
            'وزن کل (کیلوگرم)': 'total_weight',
            'نوع خرید': 'type',
            'شیوه پرداخت': 'payment_method',
            'کسر از وزن موجود': 'is_weight_costed',
            'اتوکامپلیت شده': 'is_ap_af',
            'نوع اختلاف': 'extelaf_type',
            'وزن اختلاف (کیلوگرم)': 'extelaf_weight',
            'مبلغ اختلاف (ریال)': 'extelaf_amount',
            'دلیل اولویت': 'priority_reason',
            'فاکتور مبنا': 'factor_code'
        }
        
        if excel_column in purchase_mappings:
            field_name = purchase_mappings[excel_column]
            print(f"DEBUG - Purchase mapping: {excel_column} -> {field_name}")
            return field_name
    
    # جستجو در فیلدهای موجود
    all_fields = model._meta.get_fields()
    for field in all_fields:
        # بررسی نام فیلد
        if field.name.lower() == excel_column.lower():
            print(f"DEBUG - Field name match: {excel_column} -> {field.name}")
            return field.name
        
        # بررسی verbose_name
        if hasattr(field, 'verbose_name') and field.verbose_name:
            if str(field.verbose_name).lower() == excel_column.lower():
                print(f"DEBUG - Verbose name match: {excel_column} -> {field.name}")
                return field.name
    
    print(f"DEBUG - No matching field found for: {excel_column}")
    return None

def _process_field_value_simple(obj, field_name, value, model):
    """پردازش ساده مقدار فیلد"""
    try:
        field = model._meta.get_field(field_name)
        field_type = field.get_internal_type()
        
        print(f"DEBUG - Processing field {field_name} with type {field_type}, value: '{value}' (type: {type(value)})")
        
        # اگر مقدار خالی باشد
        if value is None or (isinstance(value, str) and value.strip() == ''):
            if field.null:
                return None
            elif field_type == 'BooleanField':
                return False
            else:
                return value
        
        # پردازش بر اساس نوع فیلد
        if field_type == 'BooleanField':
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                value_lower = value.strip().lower()
                return value_lower in ['بله', 'yes', 'true', '1', 'فعال', 'on']
            if isinstance(value, (int, float)):
                return bool(value)
            return bool(value)
        
        elif field_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'SmallIntegerField']:
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                # حذف کاما و فاصله
                clean_value = value.replace(',', '').replace(' ', '').strip()
                try:
                    return int(float(clean_value))
                except (ValueError, TypeError):
                    return 0
            return int(value) if value else 0
        
        elif field_type in ['FloatField', 'DecimalField']:
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                # حذف کاما و فاصله
                clean_value = value.replace(',', '').replace(' ', '').strip()
                try:
                    return float(clean_value)
                except (ValueError, TypeError):
                    return 0.0
            return float(value) if value else 0.0
        
        elif field_type == 'CharField':
            # برای choice fields
            if hasattr(field, 'choices') and field.choices:
                # بررسی اینکه آیا مقدار در choices هست
                choice_values = [choice[0] for choice in field.choices]
                if value in choice_values:
                    return value
                
                # جستجو با display value
                for choice_value, choice_display in field.choices:
                    if str(choice_display).lower() == str(value).lower():
                        return choice_value
            
            return str(value)
        
        else:
            # سایر فیلدها (TextField, etc.)
            return str(value)
            
    except Exception as e:
        print(f"DEBUG - Error processing field {field_name}: {e}")
        return value

@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def debug_excel_processing(request):
    """تابع debug برای بررسی مشکل پردازش اکسل"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'})
    
    try:
        # تست با یک فایل نمونه
        excel_file = request.FILES.get('excel_file')
        if not excel_file:
            return JsonResponse({'error': 'No Excel file provided'})
        
        # خواندن فایل
        df = pd.read_excel(excel_file, engine='openpyxl')
        
        debug_info = {
            'file_name': excel_file.name,
            'shape': df.shape,
            'columns': list(df.columns),
            'sample_data': df.head(2).to_dict('records'),
            'dtypes': df.dtypes.to_dict(),
            'null_counts': df.isnull().sum().to_dict()
        }
        
        return JsonResponse({
            'status': 'success',
            'debug_info': debug_info
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'type': type(e).__name__
        })
