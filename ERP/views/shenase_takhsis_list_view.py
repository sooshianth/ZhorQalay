from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from core.decorators.decorators import role_required
from core.PurchaseModel import ShenaseTakhsis
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import json
import logging

logger = logging.getLogger("shenase_takhsis_list_view")


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def shenase_takhsis_list(request):
    """
    نمایش لیست شناسه‌های تخصیص با فیلتر سمت سرور
    """
    logger.warning(f"لیست شناسه‌های تخصیص توسط {request.user.username} باز شد")
    
    # برای server-side filtering، فقط template خالی برمی‌گردانیم
    # داده‌ها از طریق AJAX API بارگذاری می‌شوند
    
    context = {
        'total_count': 0,  # JavaScript این را بروزرسانی می‌کند
    }
    
    return render(request, 'shenase_takhsis_list.html', context)


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
def export_shenase_takhsis_excel(request):
    """
    خروجی اکسل شناسه‌های تخصیص انتخاب شده
    """
    try:
        data = json.loads(request.body)
        selected_ids = data.get('selected_ids', [])
        
        if not selected_ids:
            return JsonResponse({'status': 'error', 'message': 'هیچ شناسه تخصیصی انتخاب نشده است'})
        
        # دریافت شناسه‌های تخصیص انتخاب شده
        shenase_list = ShenaseTakhsis.objects.filter(id__in=selected_ids).select_related(
            'purchase',
            'purchase__customer',
            'purchase__cargo',
            'purchase__unique_sales_agent'
        ).order_by('-created_at')
        
        # ایجاد فایل اکسل
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "شناسه‌های تخصیص"
        
        # تنظیم راست به چپ برای worksheet
        ws.sheet_view.rightToLeft = True
        
        # تنظیمات استایل
        header_fill = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")
        header_font = Font(name='B Nazanin', size=12, bold=True, color="FFFFFF")
        cell_font = Font(name='B Nazanin', size=11)
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # هدرهای جدول
        headers = [
            'ردیف',
            'شناسه تخصیص',
            'شماره خرید',
            'کد درون سازمانی',
            'نام مشتری',
            'وزن (کیلوگرم)',
            'کد ملی تحویل',
            'شماره تلفن تحویل',
            'نام تحویل گیرنده',
            'آدرس تحویل',
            'کد پستی',
            'تاریخ ثبت'
        ]
        
        # نوشتن هدرها
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = border
        
        # نوشتن داده‌ها
        for row_num, shenase in enumerate(shenase_list, 2):
            data_row = [
                row_num - 1,
                shenase.code or '—',
                shenase.purchase.purchase_number if shenase.purchase else (shenase.purchase_number or '—'),
                shenase.purchase.invoice_id if shenase.purchase else '—',
                shenase.purchase.customer.name if (shenase.purchase and shenase.purchase.customer) else '—',
                shenase.weight or 0,
                shenase.code_melli_tahvil or '—',
                shenase.tahvil_phone_number or '—',
                shenase.delivery_receiver_name or '—',
                shenase.delivery_address or '—',
                shenase.delivery_postal_code or '—',
                shenase.created_at.strftime('%Y/%m/%d %H:%M') if shenase.created_at else '—'
            ]
            
            for col_num, value in enumerate(data_row, 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = value
                cell.font = cell_font
                cell.alignment = center_alignment
                cell.border = border
        
        # تنظیم عرض ستون‌ها
        column_widths = [8, 20, 15, 15, 25, 15, 15, 15, 20, 35, 12, 18]
        for col_num, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_num)].width = width
        
        # ذخیره فایل
        filename = f'shenase_takhsis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد فایل اکسل: {str(e)}'})


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def export_full_shenase_takhsis_excel(request):
    """
    خروجی اکسل کامل تمام شناسه‌های تخصیص
    """
    try:
        # دریافت تمام شناسه‌های تخصیص
        shenase_list = ShenaseTakhsis.objects.select_related(
            'purchase',
            'purchase__customer',
            'purchase__cargo',
            'purchase__unique_sales_agent'
        ).all().order_by('-created_at')
        
        # اعمال فیلتر جستجو اگر وجود دارد
        search_query = request.GET.get('search', '').strip()
        if search_query:
            shenase_list = shenase_list.filter(
                Q(code__icontains=search_query) |
                Q(purchase_number__icontains=search_query) |
                Q(purchase__invoice_id__icontains=search_query) |
                Q(purchase__customer__name__icontains=search_query) |
                Q(code_melli_tahvil__icontains=search_query) |
                Q(tahvil_phone_number__icontains=search_query) |
                Q(delivery_receiver_name__icontains=search_query)
            )
        
        # فیلتر بر اساس خرید خاص
        purchase_id = request.GET.get('purchase_id')
        if purchase_id:
            shenase_list = shenase_list.filter(purchase_id=purchase_id)
        
        # ایجاد فایل اکسل
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "شناسه‌های تخصیص"
        
        # تنظیم راست به چپ برای worksheet
        ws.sheet_view.rightToLeft = True
        
        # تنظیمات استایل
        header_fill = PatternFill(start_color="065F46", end_color="065F46", fill_type="solid")
        header_font = Font(name='B Nazanin', size=12, bold=True, color="FFFFFF")
        cell_font = Font(name='B Nazanin', size=11)
        center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # هدرهای جدول
        headers = [
            'ردیف',
            'شناسه تخصیص',
            'شماره خرید',
            'کد درون سازمانی',
            'نام مشتری',
            'وزن (کیلوگرم)',
            'کد ملی تحویل',
            'شماره تلفن تحویل',
            'نام تحویل گیرنده',
            'آدرس تحویل',
            'کد پستی',
            'تاریخ ثبت'
        ]
        
        # نوشتن هدرها
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.value = header
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_alignment
            cell.border = border
        
        # نوشتن داده‌ها
        for row_num, shenase in enumerate(shenase_list, 2):
            data_row = [
                row_num - 1,
                shenase.code or '—',
                shenase.purchase.purchase_number if shenase.purchase else (shenase.purchase_number or '—'),
                shenase.purchase.invoice_id if shenase.purchase else '—',
                shenase.purchase.customer.name if (shenase.purchase and shenase.purchase.customer) else '—',
                shenase.weight or 0,
                shenase.code_melli_tahvil or '—',
                shenase.tahvil_phone_number or '—',
                shenase.delivery_receiver_name or '—',
                shenase.delivery_address or '—',
                shenase.delivery_postal_code or '—',
                shenase.created_at.strftime('%Y/%m/%d %H:%M') if shenase.created_at else '—'
            ]
            
            for col_num, value in enumerate(data_row, 1):
                cell = ws.cell(row=row_num, column=col_num)
                cell.value = value
                cell.font = cell_font
                cell.alignment = center_alignment
                cell.border = border
        
        # تنظیم عرض ستون‌ها
        column_widths = [8, 20, 15, 15, 25, 15, 15, 15, 20, 35, 12, 18]
        for col_num, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(col_num)].width = width
        
        # ذخیره فایل
        filename = f'shenase_takhsis_full_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        
        return response
        
    except Exception as e:
        return HttpResponse(f'خطا در ایجاد فایل اکسل: {str(e)}', status=500)


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
def apply_shenase_takhsis_filter(request):
    """
    API برای اعمال فیلتر سمت سرور به شناسه‌های تخصیص
    """
    logger.warning(f"درخواست فیلتر شناسه‌های تخصیص توسط {request.user.username} انجام شده.")
    
    try:
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        sort_config = json.loads(request.POST.get('sort', '{}'))
        page_param = request.POST.get('page', '1')
        per_page_param = request.POST.get('per_page', '25')
        global_search = request.POST.get('global_search', '').strip()
        
        try:
            page = int(page_param)
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            page = 1
            per_page = 25
        
        # ایجاد QuerySet پایه
        base_queryset = ShenaseTakhsis.objects.select_related(
            'purchase',
            'purchase__customer',
            'purchase__cargo',
            'purchase__unique_sales_agent'
        ).all().order_by('-created_at')
        
        # اعمال فیلترها
        if filters:
            filter_conditions = Q()
            
            for column_id, filter_data in filters.items():
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if column_id == 'code':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(code__in=values)
                        else:
                            filter_conditions &= ~Q(code__in=values)
                            
                elif column_id == 'purchase_number':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= (Q(purchase__purchase_number__in=values) | Q(purchase_number__in=values))
                        else:
                            filter_conditions &= ~(Q(purchase__purchase_number__in=values) | Q(purchase_number__in=values))
                            
                elif column_id == 'invoice_id':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__invoice_id__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__invoice_id__in=values)
                            
                elif column_id == 'customer':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(purchase__customer__name__in=values)
                        else:
                            filter_conditions &= ~Q(purchase__customer__name__in=values)
                            
                elif column_id == 'weight':
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(int(cleaned_value))
                        
                        numeric_values = list(set(numeric_values))
                        if numeric_values:
                            if filter_type == 'include':
                                filter_conditions &= Q(weight__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(weight__in=numeric_values)
                    except (ValueError, TypeError):
                        continue
                        
                elif column_id == 'code_melli_tahvil':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(code_melli_tahvil__in=values)
                        else:
                            filter_conditions &= ~Q(code_melli_tahvil__in=values)
                            
                elif column_id == 'tahvil_phone_number':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(tahvil_phone_number__in=values)
                        else:
                            filter_conditions &= ~Q(tahvil_phone_number__in=values)
                            
                elif column_id == 'delivery_receiver_name':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(delivery_receiver_name__in=values)
                        else:
                            filter_conditions &= ~Q(delivery_receiver_name__in=values)
                            
                elif column_id == 'delivery_address':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(delivery_address__in=values)
                        else:
                            filter_conditions &= ~Q(delivery_address__in=values)
                            
                elif column_id == 'delivery_postal_code':
                    values = list(set([v for v in values if v and v.strip()]))
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(delivery_postal_code__in=values)
                        else:
                            filter_conditions &= ~Q(delivery_postal_code__in=values)
                
                else:
                    # برای فیلدهای دینامیک دیگر
                    try:
                        field = ShenaseTakhsis._meta.get_field(column_id)
                        values = [v for v in values if v and v.strip()]
                        
                        if values:
                            field_type = field.get_internal_type()
                            
                            if field_type in ['IntegerField', 'PositiveIntegerField', 'BigIntegerField']:
                                numeric_values = set()
                                for v in values:
                                    try:
                                        cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                        if cleaned_value.isdigit():
                                            numeric_values.add(int(cleaned_value))
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
            logger.info(f"اعمال جستجوی سریع با عبارت: {global_search}")
            search_conditions = Q()
            
            # جستجو در فیلدهای مستقیم شناسه تخصیص
            search_conditions |= Q(code__icontains=global_search)
            search_conditions |= Q(purchase_number__icontains=global_search)
            search_conditions |= Q(code_melli_tahvil__icontains=global_search)
            search_conditions |= Q(tahvil_phone_number__icontains=global_search)
            search_conditions |= Q(delivery_receiver_name__icontains=global_search)
            search_conditions |= Q(delivery_address__icontains=global_search)
            search_conditions |= Q(delivery_postal_code__icontains=global_search)
            
            # جستجو در فیلدهای مرتبط با خرید (فقط برای رکوردهایی که purchase دارند)
            search_conditions |= Q(purchase__isnull=False, purchase__invoice_id__icontains=global_search)
            search_conditions |= Q(purchase__isnull=False, purchase__purchase_number__icontains=global_search)
            search_conditions |= Q(purchase__isnull=False, purchase__customer__isnull=False, purchase__customer__name__icontains=global_search)
            
            before_count = base_queryset.count()
            base_queryset = base_queryset.filter(search_conditions).distinct()
            after_count = base_queryset.count()
            logger.info(f"جستجو: {before_count} -> {after_count} نتیجه")
        
        # اعمال مرتب‌سازی
        if sort_config and sort_config.get('column'):
            sort_column = sort_config['column']
            sort_direction = sort_config.get('direction', 'asc')
            
            sort_field_mapping = {
                'code': 'code',
                'purchase_number': 'purchase__purchase_number',
                'invoice_id': 'purchase__invoice_id',
                'customer': 'purchase__customer__name',
                'weight': 'weight',
                'code_melli_tahvil': 'code_melli_tahvil',
                'tahvil_phone_number': 'tahvil_phone_number',
                'delivery_receiver_name': 'delivery_receiver_name',
                'delivery_address': 'delivery_address',
                'delivery_postal_code': 'delivery_postal_code',
                'created_at': 'created_at',
            }
            
            sort_field = sort_field_mapping.get(sort_column, sort_column)
            
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
        if per_page >= 10000:  # نمایش همه
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
        for shenase in page_obj:
            result = {
                'id': shenase.id,
                'code': shenase.code or '',
                'purchase_id': shenase.purchase.id if shenase.purchase else None,
                'purchase_number': shenase.purchase.purchase_number if shenase.purchase else (shenase.purchase_number or ''),
                'invoice_id': shenase.purchase.invoice_id if shenase.purchase else '',
                'customer': shenase.purchase.customer.name if (shenase.purchase and shenase.purchase.customer) else '',
                'weight': shenase.weight or 0,
                'code_melli_tahvil': shenase.code_melli_tahvil or '',
                'tahvil_phone_number': shenase.tahvil_phone_number or '',
                'delivery_receiver_name': shenase.delivery_receiver_name or '',
                'delivery_address': shenase.delivery_address or '',
                'delivery_postal_code': shenase.delivery_postal_code or '',
                'created_at': shenase.created_at.strftime("%Y/%m/%d %H:%M") if shenase.created_at else '',
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
        logger.error(f"خطا در اعمال فیلتر به شناسه‌های تخصیص: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در اعمال فیلتر: {str(e)}'
        }, status=500)


@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
def get_shenase_takhsis_column_values(request):
    """
    API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر شناسه‌های تخصیص
    """
    try:
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
        base_queryset = ShenaseTakhsis.objects.select_related(
            'purchase',
            'purchase__customer',
            'purchase__cargo',
            'purchase__unique_sales_agent'
        ).all().order_by('-created_at')
        
        # اعمال فیلترهای فعلی (بجز فیلتر ستون فعلی)
        if current_filters:
            filter_conditions = Q()
            
            for filter_column_id, filter_data in current_filters.items():
                if filter_column_id == column_id:
                    continue
                    
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                # اعمال فیلترهای مشابه تابع قبلی
                if filter_column_id == 'code':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(code__in=values)
                        else:
                            filter_conditions &= ~Q(code__in=values)
            
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع
        if global_search:
            search_conditions = Q()
            
            # جستجو در فیلدهای مستقیم شناسه تخصیص
            search_conditions |= Q(code__icontains=global_search)
            search_conditions |= Q(purchase_number__icontains=global_search)
            search_conditions |= Q(code_melli_tahvil__icontains=global_search)
            search_conditions |= Q(tahvil_phone_number__icontains=global_search)
            search_conditions |= Q(delivery_receiver_name__icontains=global_search)
            search_conditions |= Q(delivery_address__icontains=global_search)
            search_conditions |= Q(delivery_postal_code__icontains=global_search)
            
            # جستجو در فیلدهای مرتبط با خرید (فقط برای رکوردهایی که purchase دارند)
            search_conditions |= Q(purchase__isnull=False, purchase__invoice_id__icontains=global_search)
            search_conditions |= Q(purchase__isnull=False, purchase__purchase_number__icontains=global_search)
            search_conditions |= Q(purchase__isnull=False, purchase__customer__isnull=False, purchase__customer__name__icontains=global_search)
            
            base_queryset = base_queryset.filter(search_conditions).distinct()
        
        # دریافت مقادیر بر اساس نوع ستون
        values = []
        
        if column_id == 'code':
            values_qs = base_queryset.values_list('code', flat=True).distinct().exclude(code__isnull=True).exclude(code='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'purchase_number':
            values_set = set()
            for shenase in base_queryset:
                if shenase.purchase and shenase.purchase.purchase_number:
                    values_set.add(shenase.purchase.purchase_number)
                elif shenase.purchase_number:
                    values_set.add(shenase.purchase_number)
            values = sorted(list(values_set))
            
        elif column_id == 'invoice_id':
            values_qs = base_queryset.filter(purchase__invoice_id__isnull=False).values_list('purchase__invoice_id', flat=True).distinct().exclude(purchase__invoice_id='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'customer':
            values_qs = base_queryset.filter(purchase__customer__isnull=False).values_list('purchase__customer__name', flat=True).distinct()
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'weight':
            values_qs = base_queryset.values_list('weight', flat=True).distinct().exclude(weight__isnull=True)
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'code_melli_tahvil':
            values_qs = base_queryset.values_list('code_melli_tahvil', flat=True).distinct().exclude(code_melli_tahvil__isnull=True).exclude(code_melli_tahvil='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'tahvil_phone_number':
            values_qs = base_queryset.values_list('tahvil_phone_number', flat=True).distinct().exclude(tahvil_phone_number__isnull=True).exclude(tahvil_phone_number='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'delivery_receiver_name':
            values_qs = base_queryset.values_list('delivery_receiver_name', flat=True).distinct().exclude(delivery_receiver_name__isnull=True).exclude(delivery_receiver_name='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'delivery_address':
            values_qs = base_queryset.values_list('delivery_address', flat=True).distinct().exclude(delivery_address__isnull=True).exclude(delivery_address='')
            values = sorted(list(set(values_qs)))
            
        elif column_id == 'delivery_postal_code':
            values_qs = base_queryset.values_list('delivery_postal_code', flat=True).distinct().exclude(delivery_postal_code__isnull=True).exclude(delivery_postal_code='')
            values = sorted(list(set(values_qs)))
        
        else:
            # برای فیلدهای دینامیک دیگر
            try:
                field = ShenaseTakhsis._meta.get_field(column_id)
                values_qs = base_queryset.values_list(column_id, flat=True).distinct().exclude(**{f'{column_id}__isnull': True})
                
                formatted_values = set()
                for value in values_qs:
                    if value is not None:
                        if hasattr(value, 'strftime'):  # تاریخ
                            formatted_values.add(value.strftime('%Y/%m/%d'))
                        elif isinstance(value, bool):  # بولین
                            formatted_values.add('بله' if value else 'خیر')
                        else:
                            formatted_values.add(str(value))
                
                values = sorted(list(formatted_values))
                
            except Exception as e:
                logger.warning(f"فیلد {column_id} در مدل یافت نشد یا خطا در دریافت مقادیر: {e}")
                values = []
        
        # فیلتر کردن بر اساس search_term و حذف تکراری‌های احتمالی
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
        logger.error(f"خطا در دریافت مقادیر ستون شناسه‌های تخصیص: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت مقادیر: {str(e)}'
        }, status=500)
