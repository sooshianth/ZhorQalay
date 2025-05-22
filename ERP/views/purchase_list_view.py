from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase, PurchaseEditLog
from django.db.models import Q
from openpyxl import Workbook
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
import json
from django.utils import timezone
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from core.CargoProductModel import CargoProduct
from django.core.exceptions import ValidationError
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def purchase_list(request):
    # دریافت پارامتر جستجوی سریع
    global_search = request.GET.get('global_search', '')
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # فیلتر پایه: خریدهای آرشیو نشده و آرشیو شده
    active_purchases = Purchase.objects.exclude(state='ARCHIVED').exclude(is_archived=True).order_by('-created_at')
    archived_purchases = Purchase.objects.filter(Q(state='ARCHIVED') | Q(is_archived=True)).order_by('-created_at')

    # اگر کاربر کارشناس فروش است ولی نقش لجستیک ندارد، فقط خریدهای مشتریان خود را ببیند
    if user_role == 'sales_agent':
        active_purchases = active_purchases.filter(customer__sales_agent=request.user.sales_agent)
        archived_purchases = archived_purchases.filter(customer__sales_agent=request.user.sales_agent)

    # اعمال فیلتر جستجوی سریع
    if global_search:
        active_purchases = active_purchases.filter(
            Q(customer__name__icontains=global_search) |
            Q(customer__sales_agent__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(order_weight__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__product_type__icontains=global_search) |
            Q(cargo__country__icontains=global_search) |
            Q(created_at__contains=global_search)
        )
        archived_purchases = archived_purchases.filter(
            Q(customer__name__icontains=global_search) |
            Q(customer__sales_agent__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(order_weight__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__product_type__icontains=global_search) |
            Q(cargo__country__icontains=global_search) |
            Q(created_at__contains=global_search)
        )
    
    # فهرست وضعیت‌ها برای فیلتر
    all_states = dict(Purchase.STATUS_CHOICES)

    # دریافت ستون های انتخاب شده از کوکی
    selected_columns = request.COOKIES.get('selected_columns', '')
    if not selected_columns:
        selected_columns = 'date,customer,invoice_id,sales_agent,purchase_number,weight,cargo,status,actions'
    selected_columns = selected_columns.split(',')
    
    # تعریف ایندکس ستون ها برای نمایش/مخفی کردن آنها در جاوااسکریپت
    column_indices = {
        'date': 1,
        'customer': 2,
        'invoice_id': 3,
        'sales_agent': 4,
        'purchase_number': 5,
        'weight': 6,
        'cargo': 7,
        'status': 8,
        'actions': 9
    }
    
    # لیست همه ستون های ممکن با اطلاعات لازم
    all_columns = [
        {'id': 'date', 'name': 'تاریخ', 'field': 'created_at', 'format': 'date'},
        {'id': 'customer', 'name': 'مشتری', 'field': 'customer.name', 'editable': False},
        {'id': 'invoice_id', 'name': 'کد درون سازمانی', 'field': 'invoice_id', 'editable': True},
        {'id': 'sales_agent', 'name': 'نماینده فروش', 'field': 'customer.sales_agent.name', 'editable': False},
        {'id': 'purchase_number', 'name': 'شماره خرید', 'field': 'purchase_number', 'editable': True},
        {'id': 'weight', 'name': 'وزن (کیلوگرم)', 'field': 'order_weight', 'editable': True},
        {'id': 'cargo', 'name': 'کوتاژ', 'field': 'cargo.cottage', 'editable': True},
        {'id': 'status', 'name': 'وضعیت‌ها', 'field': 'state', 'editable': True},
        {'id': 'actions', 'name': 'جزئیات', 'editable': False},
    ]

    context = {
        'active_purchases': active_purchases,
        'archived_purchases': archived_purchases,
        'all_states': all_states,
        'user_role': user_role,  # افزودن نقش کاربر به context
        # پارامترهای جستجو برای حفظ وضعیت در فرم
        'search_params': {
            'global_search': global_search,
        },
        'selected_columns': selected_columns,
        'all_columns': all_columns,
        'column_mapping': {
            'date': 0,
            'customer': 1,
            'invoice_id': 2,
            'sales_agent': 3,
            'purchase_number': 4,
            'weight': 5,
            'cargo': 6,
            'status': 7,
            'actions': 8
        },
        'column_indices': json.dumps(column_indices),
        'actions_column_index': column_indices['actions']
    }
    
    return render(request, 'purchase_list.html', context)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@require_POST
@login_required
def update_columns(request):
    selected_columns = request.POST.getlist('columns[]')
    if not selected_columns and 'columns' in request.POST:
        selected_columns = request.POST.getlist('columns')
    
    if 'actions' not in selected_columns:
        selected_columns.append('actions')  # ستون جزئیات همیشه باید نمایش داده شود
    
    response = JsonResponse({'status': 'success'})
    response.set_cookie('selected_columns', ','.join(selected_columns), max_age=30*24*60*60)
    return response

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def export_to_excel(request):
    purchase_ids = request.GET.get('ids', '').split(',')
    selected_columns = request.GET.get('columns', '')
    
    if selected_columns:
        selected_columns = selected_columns.split(',')
    else:
        selected_columns = ['date', 'customer', 'invoice_id', 'sales_agent', 'purchase_number', 'weight', 'cargo', 'status']
    
    # فیلتر کردن آیدی‌های خالی
    purchase_ids = [pid for pid in purchase_ids if pid]
    
    if not purchase_ids:
        return JsonResponse({'status': 'error', 'message': 'هیچ خریدی انتخاب نشده است'}, status=400)
    
    try:
        # برای عملکرد بهتر، اگر تعداد خریدهای انتخاب شده زیاد است، در تکه‌های کوچکتر پردازش کنیم
        purchases = Purchase.objects.filter(id__in=purchase_ids).order_by('-created_at')
        
        wb = Workbook()
        ws = wb.active
        ws.title = "لیست خریدها"
        
        # تنظیم گردش متن از راست به چپ برای کل صفحه
        ws.sheet_view.rightToLeft = True
        
        # تعریف استایل‌ها
        header_font = Font(name='B Nazanin', size=12, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='4CAF50', end_color='4CAF50', fill_type='solid')  # رنگ سبز
        
        # استایل برای ردیف‌های زوج
        even_row_fill = PatternFill(start_color='E8F5E9', end_color='E8F5E9', fill_type='solid')  # سبز بسیار کمرنگ
        
        # تنظیم راست چین و وسط چین
        alignment = Alignment(horizontal='right', vertical='center', wrap_text=True)
        
        # تعریف خطوط جدول
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # مپینگ ستون‌ها به فیلدهای مدل
        column_mapping = {
            'date': ('تاریخ', lambda p: p.created_at.strftime("%Y/%m/%d")),
            'customer': ('مشتری', lambda p: p.customer.name),
            'invoice_id': ('کد درون سازمانی', lambda p: p.invoice_id or "تعیین نشده"),
            'sales_agent': ('نماینده فروش', lambda p: ", ".join([agent.name for agent in p.customer.sales_agent.all()])),
            'purchase_number': ('شماره خرید', lambda p: p.purchase_number or "تعیین نشده"),
            'weight': ('وزن (کیلوگرم)', lambda p: p.order_weight),
            'cargo': ('کوتاژ', lambda p: p.cargo.cottage if p.cargo else "-"),
            'status': ('وضعیت', lambda p: dict(Purchase.STATUS_CHOICES).get(p.state, p.state))
        }
        
        # فقط ستون‌های انتخاب شده را اضافه می‌کنیم
        headers = []
        for col in selected_columns:
            if col in column_mapping:
                headers.append(column_mapping[col][0])
        
        # افزودن هدرها به اکسل
        ws.append(headers)
        
        # تنظیم استایل برای سطر هدر
        for i, cell in enumerate(ws[1], 1):
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = alignment
            cell.border = thin_border
        
        # داده‌ها
        batch_size = 1000  # پردازش خریدها در گروه‌های 1000 تایی برای کارایی بهتر
        row_idx = 2
        
        for i in range(0, len(purchases), batch_size):
            batch = purchases[i:i+batch_size]
            for purchase in batch:
                row = []
                for col in selected_columns:
                    if col in column_mapping:
                        try:
                            value = column_mapping[col][1](purchase)
                            row.append(value)
                        except Exception as e:
                            row.append("-")
                ws.append(row)
                
                # تنظیم استایل برای سطرهای داده
                for j, cell in enumerate(ws[row_idx], 1):
                    cell.alignment = alignment
                    cell.border = thin_border
                    
                    # استایل متناوب برای سطرها
                    if row_idx % 2 == 0:
                        cell.fill = even_row_fill
                
                row_idx += 1
        
        # تنظیم عرض ستون‌ها
        for i, column in enumerate(ws.columns, 1):
            max_length = 0
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2) * 1.2
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = adjusted_width
        
        # اضافه کردن فریز به سطر هدر
        ws.freeze_panes = "A2"
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"purchases_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        wb.save(response)
        return response
        
    except Exception as e:
        # لاگ خطا
        print(f"Error in export_to_excel: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد فایل اکسل: {str(e)}'}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def update_purchase_field(request):
    """
    API برای به‌روزرسانی فیلدهای قابل ویرایش خرید
    """
    try:
        purchase_id = request.POST.get('id')
        field_name = request.POST.get('field')
        value = request.POST.get('value')
        old_value = request.POST.get('old_value')
        
        # بررسی دسترسی‌ها
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            return JsonResponse({'status': 'error', 'message': 'شما دسترسی ویرایش ندارید'}, status=403)
        
        purchase = Purchase.objects.get(id=purchase_id)
        
        # ذخیره مقدار قدیمی برای لاگ
        if field_name == 'invoice_id':
            old_value_for_log = purchase.invoice_id
        elif field_name == 'purchase_number':
            old_value_for_log = purchase.purchase_number
        elif field_name == 'order_weight':
            old_value_for_log = str(purchase.order_weight) if purchase.order_weight is not None else ""
        elif field_name == 'state':
            old_value_for_log = purchase.state
        else:
            old_value_for_log = old_value or ""
            
        # تعیین فیلدهای مجاز برای ویرایش
        allowed_fields = {
            'invoice_id': lambda p, v: setattr(p, 'invoice_id', v),
            'purchase_number': lambda p, v: setattr(p, 'purchase_number', v),
            'order_weight': lambda p, v: setattr(p, 'order_weight', float(v) if v else None),
            'state': lambda p, v: setattr(p, 'state', v)
        }
        
        if field_name in allowed_fields:
            # ذخیره تغییرات
            allowed_fields[field_name](purchase, value)
            purchase.save()
            
            # ثبت تغییرات در لاگ
            log_entry = PurchaseEditLog(
                purchase=purchase,
                user=request.user,
                field_name=field_name,
                old_value=old_value_for_log,
                new_value=value,
                edit_time=timezone.now()
            )
            log_entry.save()
            
            return JsonResponse({
                'status': 'success',
                'log_id': log_entry.id,  # برگرداندن شناسه لاگ برای استفاده احتمالی در بازگشت به نسخه قبلی
                'old_value': old_value_for_log
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'فیلد غیرمجاز'}, status=400)
    
    except Purchase.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'خرید یافت نشد'}, status=404)
    except ValueError as e:
        # خطای تبدیل داده (مثلاً وارد کردن حروف به جای عدد)
        return JsonResponse({'status': 'error', 'message': 'خطای تبدیل داده: لطفاً مقدار صحیح وارد کنید'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def revert_purchase_edit(request):
    """
    API برای بازگرداندن تغییرات یک فیلد به حالت قبلی
    """
    try:
        log_id = request.POST.get('log_id')
        
        if not log_id:
            return JsonResponse({'status': 'error', 'message': 'شناسه لاگ ارسال نشده است'}, status=400)
        
        # پیدا کردن لاگ مورد نظر
        log_entry = PurchaseEditLog.objects.get(id=log_id)
        purchase = log_entry.purchase
        
        # بررسی دسترسی‌ها
        user_role = determine_user_role(request.user)
        if user_role == 'sales_agent':
            return JsonResponse({'status': 'error', 'message': 'شما دسترسی بازگرداندن تغییرات را ندارید'}, status=403)
        
        # بازگرداندن مقدار به حالت قبلی
        if log_entry.field_name == 'invoice_id':
            purchase.invoice_id = log_entry.old_value
        elif log_entry.field_name == 'purchase_number':
            purchase.purchase_number = log_entry.old_value
        elif log_entry.field_name == 'order_weight':
            try:
                purchase.order_weight = float(log_entry.old_value) if log_entry.old_value else None
            except ValueError:
                purchase.order_weight = None
        elif log_entry.field_name == 'state':
            purchase.state = log_entry.old_value
            
        purchase.save()
        
        # ثبت عملیات بازگرداندن در لاگ
        revert_log = PurchaseEditLog(
            purchase=purchase,
            user=request.user,
            field_name=log_entry.field_name,
            old_value=log_entry.new_value,  # مقدار جدید به قدیمی تبدیل می‌شود
            new_value=log_entry.old_value,  # مقدار قدیمی به جدید تبدیل می‌شود
            edit_time=timezone.now(),
            is_revert=True,
            reverted_log=log_entry
        )
        revert_log.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'تغییرات با موفقیت بازگردانده شد',
            'field_name': log_entry.field_name,
            'value': log_entry.old_value,
            'purchase_id': purchase.id
        })
        
    except PurchaseEditLog.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'لاگ مورد نظر یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def get_purchase_edit_logs(request, purchase_id):
    """
    دریافت تاریخچه تغییرات یک خرید
    """
    try:
        purchase = Purchase.objects.get(id=purchase_id)
        logs = PurchaseEditLog.objects.filter(purchase=purchase).order_by('-edit_time')
        
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'field_name': log.field_name,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'user': log.user.username,
                'edit_time': log.edit_time.strftime("%Y/%m/%d %H:%M:%S"),
                'is_revert': log.is_revert
            })
            
        return JsonResponse({'status': 'success', 'logs': logs_data})
    
    except Purchase.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'خرید مورد نظر یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def cargo_products_list(request):
    """
    API برای دریافت لیست کوتاژها
    """
    try:
        # فیلتر بر اساس وضعیت فعال
        active_only = request.GET.get('active_only', '1') == '1'
        
        if active_only:
            cargos = CargoProduct.objects.filter(status=True).order_by('-created_at')
        else:
            cargos = CargoProduct.objects.all().order_by('-created_at')
        
        # جستجو بر اساس پارامتر search (اگر ارسال شده باشد)
        search_term = request.GET.get('search', '')
        if search_term:
            cargos = cargos.filter(
                Q(cottage__icontains=search_term) |
                Q(product_type__icontains=search_term) |
                Q(country__icontains=search_term) |
                Q(importer_name__icontains=search_term)
            )
        
        cargos_data = []
        for cargo in cargos:
            cargos_data.append({
                'id': cargo.id,
                'cottage': cargo.cottage,
                'type': cargo.type,
                'product_type': cargo.product_type,
                'product_type_display': cargo.get_product_type_display(),
                'country': cargo.country,
                'country_display': cargo.get_country_display(),
                'importer_name': cargo.importer_name,
                'weight': cargo.weight,
                'company_price': cargo.company_price,
                'customer_price': cargo.customer_price,
                'status': cargo.status
            })
            
        return JsonResponse({'status': 'success', 'cargos': cargos_data})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def cargo_product_details(request):
    """
    API برای دریافت جزئیات یک کوتاژ بر اساس شماره کوتاژ
    """
    try:
        cottage = request.GET.get('cottage', '')
        
        if not cottage:
            return JsonResponse({'status': 'error', 'message': 'شماره کوتاژ ارسال نشده است'}, status=400)
        
        try:
            cargo = CargoProduct.objects.get(cottage=cottage)
        except CargoProduct.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
        
        cargo_data = {
            'id': cargo.id,
            'cottage': cargo.cottage,
            'type': cargo.type,
            'product_type': cargo.product_type,
            'product_type_display': cargo.get_product_type_display(),
            'country': cargo.country,
            'country_display': cargo.get_country_display(),
            'importer_name': cargo.importer_name,
            'weight': cargo.weight,
            'company_price': cargo.company_price,
            'customer_price': cargo.customer_price,
            'status': cargo.status
        }
        
        return JsonResponse({'status': 'success', 'cargo': cargo_data})
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
def bulk_edit_cargo(request):
    """
    API برای ویرایش گروهی کوتاژ
    """
    try:
        # دریافت لیست خریدهای انتخاب شده
        purchase_ids = request.POST.get('purchase_ids', '').split(',')
        purchase_ids = [pid for pid in purchase_ids if pid]
        
        if not purchase_ids:
            return JsonResponse({'status': 'error', 'message': 'هیچ خریدی انتخاب نشده است'}, status=400)
        
        # دریافت اطلاعات کوتاژ
        cargo_id = request.POST.get('cargo_id', '')
        cottage = request.POST.get('cottage', '')
        
        # حالت اول: استفاده از یک کوتاژ موجود
        if cargo_id:
            try:
                cargo = CargoProduct.objects.get(id=cargo_id)
            except CargoProduct.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'کوتاژ مورد نظر یافت نشد'}, status=404)
                
        # حالت دوم: ایجاد کوتاژ جدید
        elif cottage:
            # بررسی اینکه آیا کوتاژ قبلاً وجود دارد
            if CargoProduct.objects.filter(cottage=cottage).exists():
                return JsonResponse({'status': 'error', 'message': 'این شماره کوتاژ قبلاً ثبت شده است'}, status=400)
                
            # ایجاد کوتاژ جدید
            try:
                cargo = CargoProduct(
                    cottage=cottage,
                    type=request.POST.get('type', 'bazaargah'),
                    product_type=request.POST.get('product_type', 'corn'),
                    country=request.POST.get('country', 'iran'),
                    importer_name=request.POST.get('importer_name', ''),
                    weight=int(request.POST.get('weight', 100000) or 100000),
                    company_price=int(request.POST.get('company_price', 50000) or 50000),
                    customer_price=int(request.POST.get('customer_price', 50000) or 50000),
                    status=request.POST.get('status') == 'on'
                )
                cargo.save()
            except ValidationError as e:
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'خطا در ایجاد کوتاژ جدید: {str(e)}'}, status=500)
        else:
            return JsonResponse({'status': 'error', 'message': 'اطلاعات کوتاژ ناقص است'}, status=400)
        
        # اعمال کوتاژ به خریدهای انتخاب شده
        purchases = Purchase.objects.filter(id__in=purchase_ids)
        updated_count = 0
        
        for purchase in purchases:
            purchase.cargo = cargo
            purchase.save()
            updated_count += 1
            
            # ثبت در لاگ تغییرات
            old_cargo = 'بدون کوتاژ' if not hasattr(purchase, 'old_cargo') or purchase.old_cargo is None else purchase.old_cargo
            log_entry = PurchaseEditLog(
                purchase=purchase,
                user=request.user,
                field_name='cargo',
                old_value=old_cargo,
                new_value=str(cargo),
                edit_time=timezone.now()
            )
            log_entry.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'کوتاژ با موفقیت به {updated_count} خرید اختصاص داده شد',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)