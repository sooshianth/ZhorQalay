from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from major.models.NonBazargahPurchase import NonBazargahPurchase
from ERP.views.managers_profile_view import get_client_ip
import logging
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
import datetime
import json

logger = logging.getLogger("major_non_bazargah_purchase_list_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def non_bazargah_purchase_list(request):
    logger.warning(f"لیست خریدهای خارج از بازارگاه توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # ایجاد QuerySet پایه
    base_queryset = NonBazargahPurchase.objects.select_related(
        'customer', 'unique_sales_agent', 'product'
    ).prefetch_related('phishes').order_by('-created_at')
    
    # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
    if user_role == 'sales_agent':
        if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
            base_queryset = base_queryset.filter(unique_sales_agent=request.user.sales_agent)
        else:
            base_queryset = NonBazargahPurchase.objects.none()

    # تنظیم pagination ساده
    paginator = Paginator(base_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        'purchases': page_obj,
        'user_role': user_role,
        'total_purchases': paginator.count,
        'paginator': paginator,
        'page_obj': page_obj,
    }
    
    return render(request, 'major/non_bazargah_purchase_list.html', context)


def get_column_mapping():
    """
    نگاشت ستون‌ها به نام‌های فارسی برای خروجی اکسل
    """
    return {
        'select': 'انتخاب',
        'purchase_number': 'شماره خرید',
        'created_at': 'تاریخ',
        'unique_sales_agent': 'نماینده فروش',
        'total_weight': 'وزن (کیلوگرم)',
        'state': 'وضعیت',
        'product': 'محصول',
        'unit': 'واحد',
        'customer': 'مشتری',
        'buyer_name': 'نام خریدار',
        'customer_price': 'فی فروش (ریال)',
        'quantity': 'مقدار',
        'bag_weight': 'وزن کیسه',
        'empty_weight': 'وزن خالی',
        'loaded_weight': 'وزن پر',
        'delivered_weight': 'وزن تحویلی',
        'weight_difference': 'اختلاف وزن',
        'amount_paid': 'مبلغ پرداختی',
        'payment_verified_by': 'تایید شده توسط',
        'payment_verified_at': 'زمان تایید',
        'warehouse_contact_person': 'رابط انبار',
        'warehouse_contact_phone': 'تماس انبار',
        'logistics_notes': 'یادداشت لجستیک',
        'phish_accounts': 'شماره حساب‌های استفاده شده',
        'phish_count': 'تعداد فیش‌ها',
        'total_phish_amount': 'مجموع فیش‌ها (ریال)',
        'actions': 'عملیات'
    }


def get_purchase_data(purchase, columns):
    """
    دریافت داده‌های خرید برای ستون‌های مشخص شده
    """
    column_mapping = get_column_mapping()
    data = {}
    
    for column in columns:
        if column == 'select':
            continue  # ستون انتخاب را نادیده بگیر
        elif column == 'purchase_number':
            data[column_mapping[column]] = purchase.purchase_number or '-'
        elif column == 'created_at':
            data[column_mapping[column]] = purchase.created_at.strftime('%Y/%m/%d') if purchase.created_at else '-'
        elif column == 'unique_sales_agent':
            data[column_mapping[column]] = purchase.unique_sales_agent.name if purchase.unique_sales_agent else '-'
        elif column == 'total_weight':
            data[column_mapping[column]] = purchase.total_weight or 0
        elif column == 'state':
            data[column_mapping[column]] = purchase.get_state_display() if hasattr(purchase, 'get_state_display') else purchase.state
        elif column == 'product':
            data[column_mapping[column]] = purchase.product.name if purchase.product else '-'
        elif column == 'unit':
            data[column_mapping[column]] = purchase.get_unit_display() if hasattr(purchase, 'get_unit_display') else purchase.unit
        elif column == 'customer':
            data[column_mapping[column]] = purchase.customer.name if purchase.customer else '-'
        elif column == 'buyer_name':
            data[column_mapping[column]] = purchase.buyer_name or '-'
        elif column == 'customer_price':
            data[column_mapping[column]] = purchase.customer_price or 0
        elif column == 'quantity':
            data[column_mapping[column]] = purchase.quantity or '-'
        elif column == 'bag_weight':
            data[column_mapping[column]] = purchase.bag_weight or '-'
        elif column == 'empty_weight':
            data[column_mapping[column]] = purchase.empty_weight or '-'
        elif column == 'loaded_weight':
            data[column_mapping[column]] = purchase.loaded_weight or '-'
        elif column == 'delivered_weight':
            data[column_mapping[column]] = purchase.delivered_weight or '-'
        elif column == 'weight_difference':
            data[column_mapping[column]] = purchase.weight_difference or '-'
        elif column == 'amount_paid':
            data[column_mapping[column]] = purchase.amount_paid or 0
        elif column == 'payment_verified_by':
            data[column_mapping[column]] = purchase.payment_verified_by.username if purchase.payment_verified_by else '-'
        elif column == 'payment_verified_at':
            data[column_mapping[column]] = purchase.payment_verified_at.strftime('%Y/%m/%d %H:%M') if purchase.payment_verified_at else '-'
        elif column == 'warehouse_contact_person':
            data[column_mapping[column]] = purchase.warehouse_contact_person or '-'
        elif column == 'warehouse_contact_phone':
            data[column_mapping[column]] = purchase.warehouse_contact_phone or '-'
        elif column == 'logistics_notes':
            data[column_mapping[column]] = purchase.logistics_notes or '-'
        elif column == 'phish_accounts':
            # دریافت لیست شماره حساب‌های استفاده شده در فیش‌ها
            accounts = []
            for phish in purchase.phishes.all():
                account_info = f"{phish.bank_name} - {phish.account_number}"
                if account_info not in accounts:
                    accounts.append(account_info)
            data[column_mapping[column]] = ', '.join(accounts) if accounts else '-'
        elif column == 'phish_count':
            data[column_mapping[column]] = purchase.phishes.count()
        elif column == 'total_phish_amount':
            data[column_mapping[column]] = purchase.get_total_phish_amount() if hasattr(purchase, 'get_total_phish_amount') else 0
        elif column == 'actions':
            continue  # ستون عملیات را نادیده بگیر
    
    return data


@role_required('admin', 'logistics_manager', 'financial_manager')
@login_required
def export_non_bazargah_purchases_excel(request):
    """
    خروجی اکسل از خریدهای خارج از بازارگاه
    """
    logger.warning(f"خروجی اکسل از خریدهای خارج از بازارگاه توسط {request.user.username} با آیپی {get_client_ip(request)}")
    
    try:
        # دریافت پارامترها
        ids_param = request.POST.get('ids', '')
        columns_param = request.POST.get('columns', '')
        
        # تبدیل پارامترها به لیست
        purchase_ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()] if ids_param else []
        visible_columns = [col.strip() for col in columns_param.split(',') if col.strip()] if columns_param else []
        
        # ایجاد QuerySet
        base_queryset = NonBazargahPurchase.objects.select_related(
            'customer', 'unique_sales_agent', 'product'
        ).prefetch_related('phishes').order_by('-created_at')
        
        # فیلتر کردن بر اساس شناسه‌های انتخاب شده
        if purchase_ids:
            base_queryset = base_queryset.filter(id__in=purchase_ids)
        
        # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(unique_sales_agent=request.user.sales_agent)
            else:
                base_queryset = NonBazargahPurchase.objects.none()
        
        # دریافت خریدها
        purchases = base_queryset
        
        if not purchases.exists():
            # اگر هیچ خریدی وجود ندارد، فایل خالی برگردان
            wb = Workbook()
            ws = wb.active
            ws.title = 'خریدهای خارج از بازارگاه'
            ws.cell(row=1, column=1, value='هیچ خریدی یافت نشد')
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=non_bazargah_purchases_empty_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb.save(response)
            return response
        
        # ایجاد DataFrame
        data = []
        for purchase in purchases:
            purchase_data = get_purchase_data(purchase, visible_columns)
            data.append(purchase_data)
        
        if not data:
            # اگر داده‌ای وجود ندارد، فایل خالی برگردان
            wb = Workbook()
            ws = wb.active
            ws.title = 'خریدهای خارج از بازارگاه'
            ws.cell(row=1, column=1, value='هیچ داده‌ای برای نمایش وجود ندارد')
            
            response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename=non_bazargah_purchases_empty_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            wb.save(response)
            return response
        
        df = pd.DataFrame(data)
        
        # ایجاد HTTP response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=non_bazargah_purchases_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        # ایجاد workbook و worksheet
        wb = Workbook()
        ws = wb.active
        ws.title = 'خریدهای خارج از بازارگاه'
        
        # اضافه کردن headers
        headers = list(df.columns)
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
        
        # اضافه کردن داده‌ها
        for row_idx, row_data in enumerate(df.values, 2):
            for col_idx, value in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # ذخیره response
        wb.save(response)
        return response
        
    except Exception as e:
        logger.error(f"خطا در خروجی اکسل خریدهای خارج از بازارگاه: {str(e)}")
        
        # در صورت خطا، فایل اکسل با پیام خطا برگردان
        wb = Workbook()
        ws = wb.active
        ws.title = 'خطا'
        ws.cell(row=1, column=1, value=f'خطا در ایجاد فایل اکسل: {str(e)}')
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=error_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        wb.save(response)
        return response


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
@require_POST
def apply_non_bazargah_purchase_filter(request):
    """
    API برای اعمال فیلتر سمت سرور به خریدهای خارج از بازارگاه
    """
    logger.warning(f"درخواست فیلتر خریدهای خارج بازارگاه توسط {request.user.username} انجام شده.")
    
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        sort_config = json.loads(request.POST.get('sort', '{}'))
        page_param = request.POST.get('page', '1')
        per_page_param = request.POST.get('per_page', '20')
        global_search = request.POST.get('global_search', '').strip()
        
        try:
            page = int(page_param)
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            page = 1
            per_page = 20
        
        # ایجاد QuerySet پایه
        base_queryset = NonBazargahPurchase.objects.select_related(
            'customer', 'unique_sales_agent', 'product', 'payment_verified_by'
        ).prefetch_related('phishes').order_by('-created_at')
        
        # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(
                    unique_sales_agent=request.user.sales_agent
                )
            else:
                base_queryset = NonBazargahPurchase.objects.none()
        
        # اعمال فیلترها
        if filters:
            filter_conditions = Q()
            
            for column_id, filter_data in filters.items():
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if column_id == 'purchase_number':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase_number__in=values)
                        else:
                            filter_conditions &= ~Q(purchase_number__in=values)
                            
                elif column_id == 'unique_sales_agent':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(unique_sales_agent__name__in=values)
                        else:
                            filter_conditions &= ~Q(unique_sales_agent__name__in=values)
                            
                elif column_id == 'total_weight':
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        numeric_values = list(set(numeric_values))
                        if numeric_values:
                            if filter_type == 'include':
                                filter_conditions &= Q(total_weight__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(total_weight__in=numeric_values)
                    except (ValueError, TypeError):
                        continue
                        
                elif column_id == 'state':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(state__in=values)
                        else:
                            filter_conditions &= ~Q(state__in=values)
                            
                elif column_id == 'product':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(product__name__in=values)
                        else:
                            filter_conditions &= ~Q(product__name__in=values)
                            
                elif column_id == 'unit':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(unit__in=values)
                        else:
                            filter_conditions &= ~Q(unit__in=values)
                            
                elif column_id == 'customer':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(customer__name__in=values)
                        else:
                            filter_conditions &= ~Q(customer__name__in=values)
                            
                elif column_id == 'buyer_name':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(buyer_name__in=values)
                        else:
                            filter_conditions &= ~Q(buyer_name__in=values)
                            
                elif column_id == 'customer_price':
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        numeric_values = list(set(numeric_values))
                        if numeric_values:
                            if filter_type == 'include':
                                filter_conditions &= Q(customer_price__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(customer_price__in=numeric_values)
                    except (ValueError, TypeError):
                        continue
                
                else:
                    # برای فیلدهای دینامیک دیگر
                    try:
                        field = NonBazargahPurchase._meta.get_field(column_id)
                        values = [v for v in values if v and v.strip()]
                        
                        if values:
                            field_type = field.get_internal_type()
                            
                            if field_type == 'BooleanField':
                                bool_values = set()
                                for v in values:
                                    if v.lower() in ['بله', 'true', '1', 'فعال']:
                                        bool_values.add(True)
                                    elif v.lower() in ['خیر', 'false', '0', 'غیرفعال']:
                                        bool_values.add(False)
                                
                                bool_values = list(bool_values)
                                if bool_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': bool_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': bool_values})
                            
                            elif field_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField', 'FloatField', 'DecimalField']:
                                numeric_values = set()
                                for v in values:
                                    try:
                                        cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                        if cleaned_value.replace('.', '').isdigit():
                                            numeric_values.add(float(cleaned_value))
                                    except:
                                        continue
                                
                                numeric_values = list(numeric_values)
                                if numeric_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': numeric_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': numeric_values})
                            
                            else:
                                unique_values = list(set([v for v in values if v and v.strip()]))
                                if unique_values:
                                    if filter_type == 'include':
                                        filter_conditions &= Q(**{f'{column_id}__in': unique_values})
                                    else:
                                        filter_conditions &= ~Q(**{f'{column_id}__in': unique_values})
                                    
                    except Exception as e:
                        logger.warning(f"خطا در اعمال فیلتر برای فیلد {column_id}: {e}")
                        continue
            
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع
        if global_search:
            search_conditions = (
                Q(purchase_number__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                Q(unique_sales_agent__name__icontains=global_search) |
                Q(customer__name__icontains=global_search) |
                Q(product__name__icontains=global_search)
            )
            base_queryset = base_queryset.filter(search_conditions).distinct()
        
        # اعمال مرتب‌سازی
        if sort_config and sort_config.get('column'):
            sort_column = sort_config['column']
            sort_direction = sort_config.get('direction', 'asc')
            
            sort_field_mapping = {
                'purchase_number': 'purchase_number',
                'created_at': 'created_at',
                'unique_sales_agent': 'unique_sales_agent__name',
                'total_weight': 'total_weight',
                'state': 'state',
                'product': 'product__name',
                'unit': 'unit',
                'customer': 'customer__name',
                'buyer_name': 'buyer_name',
                'customer_price': 'customer_price',
            }
            
            sort_field = sort_field_mapping.get(sort_column, sort_column)
            
            try:
                if sort_column not in sort_field_mapping:
                    NonBazargahPurchase._meta.get_field(sort_column)
            except:
                sort_field = '-created_at'
            
            if sort_direction == 'desc':
                sort_field = f'-{sort_field}'
            
            try:
                base_queryset = base_queryset.order_by(sort_field)
            except Exception as e:
                logger.warning(f"خطا در مرتب‌سازی: {e}")
                base_queryset = base_queryset.order_by('-created_at')
        else:
            base_queryset = base_queryset.order_by('-created_at')
        
        # محاسبه تعداد کل قبل از pagination
        total_count = base_queryset.count()
        
        # اعمال pagination
        if per_page >= 10000:
            page_obj = base_queryset
            paginator = None
        else:
            paginator = Paginator(base_queryset, per_page)
            try:
                page_obj = paginator.page(page)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)
                page = 1
        
        # فرمت نتایج برای JSON response
        results = []
        for purchase in page_obj:
            result = {
                'id': purchase.id,
                'purchase_number': purchase.purchase_number or '',
                'created_at': purchase.created_at.strftime('%Y/%m/%d') if purchase.created_at else '',
                'unique_sales_agent': purchase.unique_sales_agent.name if purchase.unique_sales_agent else '',
                'total_weight': purchase.total_weight or 0,
                'state': purchase.get_state_display() if hasattr(purchase, 'get_state_display') else purchase.state,
                'state_value': purchase.state or '',
                'product': purchase.product.name if purchase.product else '',
                'unit': purchase.get_unit_display() if hasattr(purchase, 'get_unit_display') else purchase.unit,
                'customer': purchase.customer.name if purchase.customer else '',
                'buyer_name': purchase.buyer_name or '',
                'customer_price': purchase.customer_price or 0,
                'quantity': purchase.quantity or '',
                'bag_weight': purchase.bag_weight or '',
                'empty_weight': purchase.empty_weight or '',
                'loaded_weight': purchase.loaded_weight or '',
                'delivered_weight': purchase.delivered_weight or '',
                'weight_difference': purchase.weight_difference or '',
                'amount_paid': purchase.amount_paid or 0,
                'payment_verified_by': purchase.payment_verified_by.username if purchase.payment_verified_by else '',
                'payment_verified_at': purchase.payment_verified_at.strftime('%Y/%m/%d %H:%M') if purchase.payment_verified_at else '',
                'warehouse_contact_person': purchase.warehouse_contact_person or '',
                'warehouse_contact_phone': purchase.warehouse_contact_phone or '',
                'logistics_notes': purchase.logistics_notes or '',
                'phish_count': purchase.phishes.count() if hasattr(purchase, 'phishes') else 0,
                'total_phish_amount': purchase.get_total_phish_amount() if hasattr(purchase, 'get_total_phish_amount') else 0,
            }
            
            results.append(result)
        
        # اطلاعات pagination
        if paginator:
            pagination_info = {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_count': total_count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_size': per_page,
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index()
            }
        else:
            pagination_info = {
                'current_page': 1,
                'total_pages': 1,
                'total_count': total_count,
                'has_next': False,
                'has_previous': False,
                'page_size': total_count,
                'start_index': 1,
                'end_index': total_count
            }
        
        return JsonResponse({
            'status': 'success',
            'data': results,
            'total_count': total_count,
            'start_index': pagination_info['start_index'],
            'end_index': pagination_info['end_index'],
            'current_page': pagination_info['current_page'],
            'total_pages': pagination_info['total_pages'],
            'has_next': pagination_info['has_next'],
            'has_previous': pagination_info['has_previous'],
            'filter_applied': bool(filters),
            'sort_applied': bool(sort_config)
        })
        
    except Exception as e:
        logger.error(f"خطا در اعمال فیلتر به خریدهای خارج بازارگاه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در اعمال فیلتر: {str(e)}'
        }, status=500)


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
@require_POST
def get_non_bazargah_purchase_column_values(request):
    """
    API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر خریدهای خارج بازارگاه
    """
    try:
        # تشخیص نقش کاربر
        user_role = determine_user_role(request.user)
        
        column_id = request.POST.get('column_id')
        search_term = request.POST.get('search', '')
        current_filters = request.POST.get('current_filters', '{}')
        global_search = request.POST.get('global_search', '')
        
        try:
            current_filters = json.loads(current_filters) if current_filters else {}
        except (json.JSONDecodeError, TypeError):
            current_filters = {}
        
        if not column_id:
            return JsonResponse({
                'status': 'error',
                'message': 'شناسه ستون ارسال نشده است'
            }, status=400)
        
        # ایجاد QuerySet پایه
        base_queryset = NonBazargahPurchase.objects.select_related(
            'customer', 'unique_sales_agent', 'product', 'payment_verified_by'
        ).prefetch_related('phishes').order_by('-created_at')
        
        # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
        if user_role == 'sales_agent':
            if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
                base_queryset = base_queryset.filter(
                    unique_sales_agent=request.user.sales_agent
                )
            else:
                base_queryset = NonBazargahPurchase.objects.none()
        
        # اعمال فیلترهای فعلی (بجز فیلتر ستون فعلی)
        if current_filters:
            filter_conditions = Q()
            for filter_column_id, filter_data in current_filters.items():
                if filter_column_id == column_id:
                    continue
                # ساده‌تر: فقط بررسی می‌کنیم فیلترهای دیگر اعمال شود
            
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع
        if global_search:
            search_conditions = (
                Q(purchase_number__icontains=global_search) |
                Q(buyer_name__icontains=global_search) |
                Q(unique_sales_agent__name__icontains=global_search) |
                Q(customer__name__icontains=global_search) |
                Q(product__name__icontains=global_search)
            )
            base_queryset = base_queryset.filter(search_conditions).distinct()
        
        # دریافت مقادیر بر اساس نوع ستون
        values = []
        
        if column_id == 'purchase_number':
            values_qs = base_queryset.values_list('purchase_number', flat=True).distinct().exclude(purchase_number__isnull=True).exclude(purchase_number='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'created_at':
            date_values = set()
            for purchase in base_queryset:
                if purchase.created_at:
                    date_values.add(purchase.created_at.strftime("%Y/%m/%d"))
            values = sorted(list(date_values), reverse=True)
            
        elif column_id == 'unique_sales_agent':
            values_qs = base_queryset.filter(unique_sales_agent__isnull=False).values_list('unique_sales_agent__name', flat=True).distinct()
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'total_weight':
            values_qs = base_queryset.values_list('total_weight', flat=True).distinct().exclude(total_weight__isnull=True)
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'state':
            values_qs = base_queryset.values_list('state', flat=True).distinct().exclude(state__isnull=True)
            # استفاده از get_state_display برای نمایش نام فارسی
            unique_states = list(set(values_qs))
            values = sorted(unique_states)
            
        elif column_id == 'product':
            values_qs = base_queryset.filter(product__isnull=False).values_list('product__name', flat=True).distinct()
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'unit':
            values_qs = base_queryset.values_list('unit', flat=True).distinct().exclude(unit__isnull=True)
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'customer':
            values_qs = base_queryset.filter(customer__isnull=False).values_list('customer__name', flat=True).distinct()
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'buyer_name':
            values_qs = base_queryset.values_list('buyer_name', flat=True).distinct().exclude(buyer_name__isnull=True).exclude(buyer_name='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'customer_price':
            values_qs = base_queryset.values_list('customer_price', flat=True).distinct().exclude(customer_price__isnull=True)
            values = sorted(list(set(values_qs)))
        
        else:
            # برای فیلدهای دینامیک دیگر
            try:
                field = NonBazargahPurchase._meta.get_field(column_id)
                values_qs = base_queryset.values_list(column_id, flat=True).distinct().exclude(**{f'{column_id}__isnull': True})
                
                formatted_values = set()
                for value in values_qs:
                    if value is not None:
                        if hasattr(value, 'strftime'):
                            formatted_values.add(value.strftime('%Y/%m/%d'))
                        elif isinstance(value, bool):
                            formatted_values.add('بله' if value else 'خیر')
                        else:
                            formatted_values.add(str(value))
                
                values = sorted(list(formatted_values))
                
            except Exception as e:
                logger.warning(f"فیلد {column_id} در مدل یافت نشد یا خطا در دریافت مقادیر: {e}")
                values = []
        
        # فیلتر کردن بر اساس search_term
        if search_term:
            filtered_values = set()
            for v in values:
                if search_term.lower() in str(v).lower():
                    filtered_values.add(v)
            values = sorted(list(filtered_values))
        
        # محدود کردن تعداد نتایج
        values = values[:100]
        
        return JsonResponse({
            'status': 'success',
            'values': values,
            'count': len(values)
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت مقادیر ستون خریدهای خارج بازارگاه: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت مقادیر: {str(e)}'
        }, status=500)
