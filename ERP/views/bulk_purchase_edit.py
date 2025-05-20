from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.conf import settings
import pandas as pd
import os
import json
import tempfile
import re

from core.PurchaseModel import Purchase, PurchaseHistory
from core.CargoProductModel import CargoProduct
from core.CustomerModel import Customer
from core.SalesAgentModel import SalesAgent
from core.decorators.decorators import role_required

@role_required('admin',)
@login_required
def bulk_purchase_edit(request):
    """
    ویو اصلی برای ویرایش فله‌ای خرید‌ها
    """
    # بررسی دسترسی
    if not request.user.is_superuser and not hasattr(request.user, 'admin_user'):
        messages.error(request, 'شما به این بخش دسترسی ندارید.')
        return redirect('dashboard')
    
    context = {
        'page_title': 'ویرایش فله‌ای خریدها',
        'purchase_statuses': dict(Purchase.STATUS_CHOICES),
        'product_types': dict(CargoProduct.PRODUCT_TYPE_CHOICES) if hasattr(CargoProduct, 'PRODUCT_TYPE_CHOICES') else {},
        'cargo_products': CargoProduct.objects.all(),
        'sales_agents': SalesAgent.objects.all()
    }
    
    return render(request, 'bulk_purchase_edit.html', context)

@role_required('admin')
@login_required
def upload_excel(request):
    """
    آپلود فایل اکسل حاوی شماره خریدها
    """
    if not request.user.is_superuser and not hasattr(request.user, 'admin_user'):
        return JsonResponse({'success': False, 'message': 'شما به این بخش دسترسی ندارید.'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر.'})
    
    # بررسی نوع درخواست (JSON یا فرم داده)
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            purchase_numbers = data.get('purchase_numbers', [])
            
            if not purchase_numbers:
                return JsonResponse({'success': False, 'message': 'هیچ شماره خریدی ارسال نشده است.'})
            
            # حذف فاصله‌های اضافی و تبدیل به فرمت عددی
            purchase_numbers = [re.sub(r'\s+', '', str(pn)) for pn in purchase_numbers]
            
            # یافتن خریدهای موجود در دیتابیس
            found_purchases = Purchase.objects.filter(purchase_number__in=purchase_numbers)
            
            # تهیه لیست خریدهای یافت شده و یافت نشده
            found_purchase_numbers = found_purchases.values_list('purchase_number', flat=True)
            not_found_numbers = list(set(purchase_numbers) - set(found_purchase_numbers))
            
            # تهیه دیتا برای نمایش در جدول
            purchase_data = []
            for purchase in found_purchases:
                purchase_data.append({
                    'id': purchase.id,
                    'purchase_number': purchase.purchase_number,
                    'invoice_id': purchase.invoice_id or '',
                    'customer_name': purchase.customer.name if purchase.customer else '',
                    'state': purchase.get_state_display(),
                    'state_value': purchase.state,
                    'company_price': purchase.company_price,
                    'customer_price': purchase.customer_price,
                    'cargo_name': purchase.cargo.cottage if purchase.cargo else '',
                    'cargo_country': purchase.cargo.get_country_display() if purchase.cargo else '',
                    'cargo_id': purchase.cargo.id if purchase.cargo else '',
                    'created_at': purchase.created_at.strftime('%Y-%m-%d') if purchase.created_at else '',
                    'amount_paid': purchase.amount_paid if purchase.amount_paid else 0,
                    'delivered_weight': purchase.delivered_weight if purchase.delivered_weight else 0,
                    'order_weight': purchase.order_weight if purchase.order_weight else 0,
                })
            
            # ذخیره شماره خریدها در سشن
            request.session['bulk_edit_purchase_ids'] = [p.id for p in found_purchases]
            
            return JsonResponse({
                'success': True,
                'message': f'{len(found_purchase_numbers)} خرید از {len(purchase_numbers)} خرید یافت شد.',
                'purchase_data': purchase_data,
                'not_found': not_found_numbers
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'داده JSON نامعتبر است.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'خطا در پردازش داده‌ها: {str(e)}'})
    
    # روش قدیمی با آپلود فایل
    if 'excel_file' not in request.FILES:
        return JsonResponse({'success': False, 'message': 'فایل اکسل انتخاب نشده است.'})
    
    excel_file = request.FILES['excel_file']
    
    # بررسی پسوند فایل
    if not excel_file.name.endswith(('.xlsx', '.xls')):
        return JsonResponse({'success': False, 'message': 'فرمت فایل باید Excel (.xlsx یا .xls) باشد.'})
    
    try:
        # ذخیره موقت فایل
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as temp_file:
            for chunk in excel_file.chunks():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # خواندن فایل اکسل
        df = pd.read_excel(temp_file_path)
        
        # حذف فایل موقت
        os.unlink(temp_file_path)
        
        # بررسی ستون‌های فایل
        if 'شماره_خرید' not in df.columns and 'شماره خرید' not in df.columns and 'purchase_number' not in df.columns:
            return JsonResponse({
                'success': False, 
                'message': 'فایل اکسل باید شامل ستونی با عنوان "شماره_خرید" یا "شماره خرید" یا "purchase_number" باشد.'
            })
        
        # تعیین نام ستون شماره خرید
        purchase_number_column = None
        for col in ['شماره_خرید', 'شماره خرید', 'purchase_number']:
            if col in df.columns:
                purchase_number_column = col
                break
        
        # استخراج شماره خریدها
        purchase_numbers = df[purchase_number_column].dropna().astype(str).tolist()
        
        # حذف فاصله‌های اضافی و تبدیل به فرمت عددی
        purchase_numbers = [re.sub(r'\s+', '', pn) for pn in purchase_numbers]
        
        # یافتن خریدهای موجود در دیتابیس
        found_purchases = Purchase.objects.filter(purchase_number__in=purchase_numbers)
        
        # تهیه لیست خریدهای یافت شده و یافت نشده
        found_purchase_numbers = found_purchases.values_list('purchase_number', flat=True)
        not_found_numbers = list(set(purchase_numbers) - set(found_purchase_numbers))
        
        # تهیه دیتا برای نمایش در جدول
        purchase_data = []
        for purchase in found_purchases:
            purchase_data.append({
                'id': purchase.id,
                'purchase_number': purchase.purchase_number,
                'invoice_id': purchase.invoice_id or '',
                'customer_name': purchase.customer.name if purchase.customer else '',
                'state': purchase.get_state_display(),
                'state_value': purchase.state,
                'company_price': purchase.company_price,
                'customer_price': purchase.customer_price,
                'cargo_name': purchase.cargo.cottage if purchase.cargo else '',
                'cargo_country': purchase.cargo.get_country_display() if purchase.cargo else '',
                'cargo_id': purchase.cargo.id if purchase.cargo else '',
                'created_at': purchase.created_at.strftime('%Y-%m-%d') if purchase.created_at else '',
                'amount_paid': purchase.amount_paid if purchase.amount_paid else 0,
                'delivered_weight': purchase.delivered_weight if purchase.delivered_weight else 0,
                'order_weight': purchase.order_weight if purchase.order_weight else 0,
            })
        
        # ذخیره شماره خریدها در سشن
        request.session['bulk_edit_purchase_ids'] = [p.id for p in found_purchases]
        
        return JsonResponse({
            'success': True,
            'message': f'{len(found_purchase_numbers)} خرید از {len(purchase_numbers)} خرید یافت شد.',
            'purchase_data': purchase_data,
            'not_found': not_found_numbers
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در پردازش فایل: {str(e)}'})

@role_required('admin')
@login_required
def apply_bulk_edit(request):
    """
    اعمال تغییرات فله‌ای بر روی خریدهای انتخاب شده
    """
    if not request.user.is_superuser and not hasattr(request.user, 'admin_user'):
        return JsonResponse({'success': False, 'message': 'شما به این بخش دسترسی ندارید.'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'درخواست نامعتبر.'})
    
    try:
        # دریافت و پردازش داده‌ها
        data = json.loads(request.body)
        purchase_ids = data.get('purchase_ids', [])
        
        # بررسی وجود خریدهای انتخابی
        if not purchase_ids:
            purchase_ids = request.session.get('bulk_edit_purchase_ids', [])
            if not purchase_ids:
                return JsonResponse({'success': False, 'message': 'هیچ خریدی انتخاب نشده است.'})
        
        changes = data.get('changes', {})
        if not changes:
            return JsonResponse({'success': False, 'message': 'هیچ تغییری برای اعمال مشخص نشده است.'})
        
        # دریافت خریدهای انتخابی
        purchases = Purchase.objects.filter(id__in=purchase_ids)
        
        # آمارها
        total_count = len(purchases)
        updated_count = 0
        errors = []
        
        # لیست فیلدهای قابل تغییر
        allowed_fields = {
            'state': 'وضعیت',
            'company_price': 'فی خرید',
            'customer_price': 'فی فروش',
            'cargo': 'محصول',
            'address': 'آدرس',
            'description': 'توضیحات',
            'amount_paid': 'مبلغ پرداختی',
            'payment_method': 'روش پرداخت',
            'is_urgent': 'فوری',
            'priority': 'اولویت',
            'priority_reason': 'دلیل اولویت',
            'delivered_weight': 'وزن تحویلی',
            'order_weight': 'وزن سفارش',
            'extelaf_type': 'نوع اختلاف',
            'extelaf_weight': 'وزن اختلاف',
            'extelaf_amount': 'مبلغ اختلاف',
        }
        
        # بررسی فیلدهای مجاز
        for field in changes.keys():
            if field not in allowed_fields and field != 'sales_agent':
                return JsonResponse({
                    'success': False, 
                    'message': f'فیلد "{field}" برای ویرایش فله‌ای مجاز نیست.'
                })
        
        # اعمال تغییرات بر روی هر خرید
        for purchase in purchases:
            try:
                change_log = []
                
                # تنظیم فیلدهای عادی
                for field, value in changes.items():
                    if field == 'sales_agent':
                        continue  # پردازش جداگانه برای کارشناس فروش
                    
                    if field == 'cargo' and value:
                        try:
                            cargo = CargoProduct.objects.get(id=value)
                            old_value = purchase.cargo.cottage if purchase.cargo else "ندارد"
                            purchase.cargo = cargo
                            change_log.append(f"محصول: {old_value} -> {cargo.cottage}")
                        except CargoProduct.DoesNotExist:
                            errors.append(f"خطا در خرید {purchase.purchase_number}: محصول با شناسه {value} یافت نشد.")
                            continue
                    elif value is not None:
                        old_value = getattr(purchase, field)
                        setattr(purchase, field, value)
                        
                        # نمایش متن فارسی برای فیلدهای خاص
                        if field == 'state':
                            old_display = dict(Purchase.STATUS_CHOICES).get(old_value, old_value)
                            new_display = dict(Purchase.STATUS_CHOICES).get(value, value)
                            change_log.append(f"وضعیت: {old_display} -> {new_display}")
                        else:
                            field_name = allowed_fields.get(field, field)
                            change_log.append(f"{field_name}: {old_value} -> {value}")
                
                # پردازش کارشناس فروش
                if 'sales_agent' in changes and changes['sales_agent']:
                    try:
                        sales_agent_id = changes['sales_agent']
                        sales_agent = SalesAgent.objects.get(id=sales_agent_id)
                        
                        # بررسی وجود کارشناس فروش در خرید
                        if not purchase.sales_agent.filter(id=sales_agent_id).exists():
                            purchase.sales_agent.add(sales_agent)
                            change_log.append(f"کارشناس فروش: {sales_agent.user.get_full_name() if sales_agent.user else sales_agent.id} اضافه شد")
                    except SalesAgent.DoesNotExist:
                        errors.append(f"خطا در خرید {purchase.purchase_number}: کارشناس فروش با شناسه {changes['sales_agent']} یافت نشد.")
                
                purchase.save()
                
                # ثبت تاریخچه تغییرات
                if change_log:
                    PurchaseHistory.objects.create(
                        purchase=purchase,
                        user=request.user,
                        changes="ویرایش فله‌ای: " + " | ".join(change_log)
                    )
                    updated_count += 1
                
            except Exception as e:
                errors.append(f"خطا در خرید {purchase.purchase_number}: {str(e)}")
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} خرید از {total_count} خرید با موفقیت به‌روزرسانی شد.',
            'updated_count': updated_count,
            'total_count': total_count,
            'errors': errors
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در اعمال تغییرات: {str(e)}'})

@role_required('admin')
@login_required
def get_purchase_details(request, purchase_id):
    """
    دریافت جزئیات یک خرید برای نمایش
    """
    if not request.user.is_superuser and not hasattr(request.user, 'admin_user'):
        return JsonResponse({'success': False, 'message': 'شما به این بخش دسترسی ندارید.'})
    
    try:
        purchase = Purchase.objects.get(id=purchase_id)
        
        # تهیه داده‌های پاسخ
        purchase_data = {
            'id': purchase.id,
            'purchase_number': purchase.purchase_number,
            'invoice_id': purchase.invoice_id,
            'customer_name': purchase.customer.name if purchase.customer else 'نامشخص',
            'state': purchase.get_state_display(),
            'cargo_name': purchase.cargo.cottage if purchase.cargo else '',
            'cargo_country': purchase.cargo.get_country_display() if purchase.cargo else '',
            'company_price': purchase.company_price,
            'customer_price': purchase.customer_price,
            'order_weight': purchase.order_weight,
            'delivered_weight': purchase.delivered_weight,
            'amount_paid': purchase.amount_paid,
            'payment_method': purchase.payment_method,
            'created_at': purchase.created_at.strftime('%Y-%m-%d') if purchase.created_at else '',
            'extelaf_type': purchase.extelaf_type,
            'extelaf_weight': purchase.extelaf_weight,
            'extelaf_amount': purchase.extelaf_amount,
            'address': purchase.address,
            'description': purchase.description,
            'sales_agents': [{'id': agent.id, 'name': agent.name} for agent in purchase.customer.sales_agent.all()]
        }
        
        return JsonResponse({
            'success': True,
            'data': purchase_data
        })
    
    except Purchase.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'خرید مورد نظر یافت نشد.'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'خطا در دریافت اطلاعات: {str(e)}'})

@role_required('admin')
@login_required
def export_purchase_list(request):
    """
    خروجی اکسل از لیست خریدهای انتخاب شده
    """
    if not request.user.is_superuser and not hasattr(request.user, 'admin_user'):
        messages.error(request, 'شما به این بخش دسترسی ندارید.')
        return redirect('dashboard')
    
    purchase_ids = request.session.get('bulk_edit_purchase_ids', [])
    if not purchase_ids:
        messages.error(request, 'هیچ خریدی برای خروجی انتخاب نشده است.')
        return redirect('bulk_purchase_edit')
    
    purchases = Purchase.objects.filter(id__in=purchase_ids)
    
    # ایجاد دیتافریم
    data = []
    for purchase in purchases:
        data.append({
            'شماره خرید': purchase.purchase_number,
            'کد سیستمی': purchase.invoice_id or '',
            'نام مشتری': purchase.customer.name if purchase.customer else '',
            'وضعیت': purchase.get_state_display(),
            'محصول': purchase.cargo.cottage if purchase.cargo else '',
            'فی خرید': purchase.company_price,
            'فی فروش': purchase.customer_price,
            'مبلغ پرداختی': purchase.amount_paid if purchase.amount_paid else 0,
            'وزن تحویلی': purchase.delivered_weight if purchase.delivered_weight else 0,
            'وزن سفارش': purchase.order_weight if purchase.order_weight else 0,
            'نوع اختلاف': purchase.extelaf_type or '',
            'وزن اختلاف': purchase.extelaf_weight or 0,
            'مبلغ اختلاف': purchase.extelaf_amount or 0,
            'تاریخ ثبت': purchase.created_at.strftime('%Y-%m-%d') if purchase.created_at else '',
            'آدرس': purchase.address or '',
            'روش پرداخت': purchase.payment_method or '',
            'اولویت': dict(Purchase.PRIORITY_CHOICES).get(purchase.priority, purchase.priority) if hasattr(purchase, 'PRIORITY_CHOICES') else purchase.priority,
        })
    
    df = pd.DataFrame(data)
    
    # ایجاد فایل اکسل
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=purchases_export.xlsx'
    
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    return response
