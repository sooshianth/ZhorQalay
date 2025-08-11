from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, F, Max
from django.utils import timezone
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from core.decorators.decorators import role_required
from core.CustomerModel import Customer, ActivityField, PaymentPreference, ProductPreference
from django.utils.timezone import timedelta
from django.conf import settings
from sms_api.apis import queue_sms, render_template
from sms_api.models import SmsTemplate
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger("sales_customer_list_view")

@role_required('sales_agent', 'admin')
@login_required
def enhanced_customer_list_view(request):
    """
    نمایش لیست پیشرفته مشتریان با فیلتر سمت سرور
    """
    if not hasattr(request.user, 'sales_agent'):
        messages.error(request, "شما مجاز به مشاهده این بخش نیستید.")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent
    
    # دریافت لیست‌های مورد نیاز برای فیلترها
    all_cities = Customer.objects.values_list('city', flat=True).distinct().exclude(city__isnull=True).exclude(city='').order_by('city')
    all_activities = ActivityField.objects.all().order_by('code')
    all_payment_preferences = PaymentPreference.objects.all().order_by('code')
    all_product_preferences = ProductPreference.objects.all().order_by('code')

    # محاسبه سهمیه پیامک
    sms_quota = getattr(settings, 'SALES_AGENT_SMS_QOUTA', 0)
    
    # محاسبه تعداد کل مشتریان
    total_customers = sales_agent.get_all_customers().count()

    # آماده‌سازی context - فقط اطلاعات اولیه
    context = {
        'all_cities': all_cities,
        'all_activities': all_activities,
        'all_payment_preferences': all_payment_preferences,
        'all_product_preferences': all_product_preferences,
        'sms_quota': sms_quota,
        'total_customers': total_customers,
        'has_filters': False,  # فیلترها در سمت کلاینت مدیریت می‌شوند
        'search_query': '',
        'favorites_only': False,
        'city_filter': [],
        'activity_filter': [],
        'payment_filter': [],
        'product_filter': [],
        'status_filter': '',
        'min_purchases': '',
        'last_purchase_days': '',
        'sms_preference': '',
        'whatsapp_preference': '',
        'sort_key': 'name_asc',
    }
    
    return render(request, 'customer_list.html', context)

@role_required('sales_agent', 'admin')
@login_required
@require_POST
def toggle_favorite(request):
    """تغییر وضعیت مورد علاقه بودن مشتری"""
    customer_id = request.POST.get('customer_id')
    
    if not customer_id:
        return JsonResponse({'success': False, 'error': 'شناسه مشتری وارد نشده است'}, status=400)
    
    try:
        customer = Customer.objects.get(id=customer_id)
        
        # بررسی دسترسی کارشناس به این مشتری
        if not request.user.is_superuser and request.user.sales_agent not in customer.sales_agent.all():
            return JsonResponse({'success': False, 'error': 'شما دسترسی به این مشتری ندارید'}, status=403)
        
        # تغییر وضعیت مورد علاقه
        customer.is_favorite = not customer.is_favorite
        customer.save()
        
        return JsonResponse({
            'success': True, 
            'is_favorite': customer.is_favorite,
            'message': f"مشتری {customer.name} {'به لیست علاقه‌مندی‌ها اضافه شد' if customer.is_favorite else 'از لیست علاقه‌مندی‌ها حذف شد'}"
        })
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'مشتری یافت نشد'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@role_required('sales_agent', 'admin')
@login_required
def get_sms_templates(request):
    """دریافت قالب‌های پیامک برای استفاده در صفحه لیست مشتریان"""
    # فقط قالب‌های custom را برمی‌گردانیم
    templates = SmsTemplate.objects.filter(is_for_salesmen=True).order_by('-updated_at')
    
    # تبدیل قالب‌ها به فرمت مناسب برای JSON
    templates_list = []
    for template in templates:
        templates_list.append({
            'id': template.id,
            'name': template.name,
            'content': template.content,
            'status': template.status,
            'status_display': template.get_status_display(),
        })
    
    return JsonResponse({
        'templates': templates_list,
        'count': len(templates_list)
    })

@role_required('sales_agent', 'admin')
@login_required
@require_POST
def send_sms_to_selected(request):
    """ارسال پیامک به مشتریان انتخاب شده"""
    # دریافت آرایه customer_ids از FormData
    customer_ids = request.POST.getlist('customer_ids[]')
    # اگر با getlist پیدا نشد، شاید به صورت رشته JSON ارسال شده باشد
    if not customer_ids:
        try:
            import json
            data = json.loads(request.body.decode('utf-8'))
            customer_ids = data.get('customer_ids', [])
        except:
            pass
    
    template_id = request.POST.get('template_id')
    product_info = request.POST.get('product_info', '')
    
    if not customer_ids:
        return JsonResponse({'success': False, 'error': 'هیچ مشتری انتخاب نشده است'}, status=400)
    
    if not template_id:
        return JsonResponse({'success': False, 'error': 'لطفا یک قالب پیامک انتخاب کنید'}, status=400)
    
    try:
        # دریافت قالب پیامک
        template = SmsTemplate.objects.get(id=template_id)
    except SmsTemplate.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'قالب پیامک یافت نشد'}, status=404)
    
    sales_agent = request.user.sales_agent
    sms_quota = getattr(settings, 'SALES_AGENT_SMS_QOUTA', 0)
    
    # بررسی اینکه آیا سهمیه پیامک کافی است
    selected_customers = Customer.objects.filter(id__in=customer_ids, sales_agent=sales_agent)
    total_phone_numbers = 0
    
    for customer in selected_customers:
        phone_numbers = customer.get_all_phone_numbers()
        total_phone_numbers += len(phone_numbers)
    
    if total_phone_numbers > sms_quota:
        return JsonResponse({
            'success': False, 
            'error': f'سهمیه پیامک شما ({sms_quota}) کمتر از تعداد شماره‌های مشتریان انتخاب شده ({total_phone_numbers}) است'
        }, status=400)
    
    # ارسال پیامک به مشتریان انتخاب شده
    success_count = 0
    failed_count = 0
    
    for customer in selected_customers:
        if not customer.sms_preference:
            continue  # رد شدن از مشتریانی که تمایل به دریافت پیامک ندارند
        
        # آماده‌سازی داده‌های جایگزین برای قالب
        context = {
            'customer_name': customer.name,
            'sales_agent_name': sales_agent.name,
            'sales_agent_phone': sales_agent.phone_number,
            'product_info': product_info,
        }
        
        # اگر اطلاعات محصول وارد شده، سعی کنیم اطلاعات کارگو متناظر را پیدا کنیم
        if product_info and ':' in product_info:
            try:
                # اگر فرمت product_info مثل "cottage:12345678" باشد
                cottage_match = re.match(r'cottage:(\d+)', product_info.lower())
                if cottage_match:
                    cottage = cottage_match.group(1)
                    from core.CargoProductModel import CargoProduct
                    cargo = CargoProduct.objects.filter(cottage=cottage, status=True).first()
                    if cargo:
                        context.update({
                            'cargo': cargo,
                            'cottage': cargo.cottage,
                            'cargo_type': cargo.get_product_type_display(),
                            'cargo_country': cargo.get_country_display(),
                            'customer_price': cargo.customer_price,
                            'port': cargo.port,
                            'loading_time': cargo.loading_time,
                        })
            except Exception as e:
                print(f"خطا در یافتن اطلاعات محصول: {e}")
        
        # رندر کردن قالب با داده‌های مشتری و استفاده از شناسه قالب
        message = render_template(template.status, context)
        
        # اگر رندر کردن قالب موفق نبود، از متن قالب استفاده کنیم
        if not message:
            message = template.content
            # جایگزینی ساده متغیرها
            message = message.replace('{{customer_name}}', customer.name)
            message = message.replace('{{sales_agent_name}}', sales_agent.name)
            message = message.replace('{{sales_agent_phone}}', sales_agent.phone_number)
            message = message.replace('{{product_info}}', product_info)
        
        # کوتاه کردن متن پیام به 255 کاراکتر
        if len(message) > 255:
            message = message[:252] + '...'
        
        phone_numbers = customer.get_all_phone_numbers()
        for phone in phone_numbers:
            try:
                queue_sms(phone, message, notification_type='custom')
                success_count += 1
            except Exception as e:
                failed_count += 1
    
    return JsonResponse({
        'success': True,
        'success_count': success_count,
        'failed_count': failed_count,
        'message': f'پیامک با موفقیت به صف ارسال برای {success_count} شماره اضافه شد. {failed_count} مورد ناموفق.'
    })

@role_required('sales_agent', 'admin')
@login_required
def get_active_products(request):
    """API endpoint for retrieving active cargo products"""
    from core.CargoProductModel import CargoProduct
    
    # Get all active products
    products = CargoProduct.get_active_products()
    
    # Convert to serializable format
    products_list = []
    for product in products:
        products_list.append({
            'id': product.id,
            'cottage': product.cottage,
            'product_type': product.type_of_product,
            'product_type_display': product.get_product_type_display(),
            'country': product.country,
            'country_display': product.get_country_display(),
            'customer_price': product.customer_price,
            'company_price': product.company_price,
            'weight': product.weight,
            'port': product.port,
            'loading_time': product.loading_time,
            'description': product.description,
        })
    
    return JsonResponse({
        'products': products_list,
        'count': len(products_list)
    })

@role_required('sales_agent', 'admin')
@login_required
@require_POST
def create_support_task_from_customer(request):
    """ایجاد تسک کارشناس پشتیبانی از صفحه مشتری"""
    try:
        customer_id = request.POST.get('customer_id')
        support_agent_id = request.POST.get('support_agent_id')
        description = request.POST.get('description', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        send_sms = request.POST.get('send_sms', 'false') == 'true'
        
        if not customer_id:
            return JsonResponse({
                'status': 'error',
                'message': 'شناسه مشتری الزامی است'
            }, status=400)
        
        if not support_agent_id:
            return JsonResponse({
                'status': 'error',
                'message': 'کارشناس پشتیبانی الزامی است'
            }, status=400)
        
        if not description:
            return JsonResponse({
                'status': 'error',
                'message': 'توضیحات الزامی است'
            }, status=400)
        
        # دریافت مشتری
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'مشتری یافت نشد'
            }, status=404)
        
        # دریافت کارشناس پشتیبانی
        try:
            from core.SupportAgentModel import SupportAgent
            support_agent = SupportAgent.objects.get(id=support_agent_id, user__is_active=True)
        except SupportAgent.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'کارشناس پشتیبانی یافت نشد'
            }, status=404)
        
        # ایجاد تسک کارشناس پشتیبانی
        from core.SupportAgentTask import SupportAgentTask
        
        task = SupportAgentTask.objects.create(
            support_agent=support_agent,
            customer=customer,
            description=description,
            phone_number=phone_number or customer.get_primary_phone(),
            urgency_level=9,  # اولویت بالا
        )
        
        # ارسال پیامک در صورت درخواست
        if send_sms and phone_number:
            try:
                from sms_api.apis import queue_sms
                message = f"مشتری {customer.name} برای شما ارجاع داده شده است. لطفاً در اسرع وقت پیگیری کنید. شماره تماس: {phone_number}"
                queue_sms(phone_number, message, notification_type='support_task')
            except Exception as e:
                print(f"خطا در ارسال پیامک: {e}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'تسک کارشناس پشتیبانی با موفقیت ایجاد شد',
            'task_id': task.id
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در ایجاد تسک: {str(e)}'
        }, status=500) 

@role_required('sales_agent', 'admin')
@login_required
@require_POST
def apply_customer_filter(request):
    """
    API برای اعمال فیلتر سمت سرور به مشتریان
    """
    logger.warning(f"درخواست فیلتر مشتری توسط {request.user.username} انجام شده.")
    try:
        # بررسی دسترسی کارشناس فروش
        if not hasattr(request.user, 'sales_agent'):
            return JsonResponse({'success': False, 'error': 'شما مجاز به مشاهده این بخش نیستید'}, status=403)

        sales_agent = request.user.sales_agent
        
        # دریافت پارامترهای فیلتر
        filters = json.loads(request.POST.get('filters', '{}'))
        sort_config = json.loads(request.POST.get('sort', '{}'))
        # دریافت پارامترهای pagination
        page_param = request.POST.get('page', '1')
        per_page_param = request.POST.get('per_page', '25')
        # دریافت پارامتر جستجوی سریع
        global_search = request.POST.get('global_search', '').strip()
        
        logger.info(f"🔍 Global search received: '{global_search}'")
        
        try:
            page = int(page_param)
            per_page = int(per_page_param)
        except (ValueError, TypeError):
            logger.error(f"❌ مقادیر pagination نامعتبر: page={page_param}, per_page={per_page_param}")
            page = 1
            per_page = 25
        
        # ایجاد QuerySet پایه
        base_queryset = sales_agent.get_all_customers().prefetch_related(
            'field_of_activity',
            'purchase_preferences', 
            'product_preferences',
            'purchases_made',
            'phone_numbers'
        )
        
        # اعمال فیلترها - فقط اگر فیلتر وجود داشته باشد
        if filters:
            filter_conditions = Q()
            
            for column_id, filter_data in filters.items():
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if column_id == 'name':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(name__in=values)
                        else:
                            filter_conditions &= ~Q(name__in=values)
                        
                elif column_id == 'phone_number':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # تمیز کردن شماره تلفن از کاراکترهای غیرعددی
                        clean_values = []
                        for v in values:
                            clean_v = ''.join(c for c in v if c.isdigit())
                            if clean_v:
                                clean_values.append(clean_v)
                        
                        if clean_values:
                            phone_conditions = Q()
                            for clean_v in clean_values:
                                phone_conditions |= Q(phone_number__icontains=clean_v) | Q(phone_numbers__number__icontains=clean_v)
                            
                            if filter_type == 'include':
                                filter_conditions &= phone_conditions
                            else:
                                filter_conditions &= ~phone_conditions
                        
                elif column_id == 'city':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(city__in=values)
                        else:
                            filter_conditions &= ~Q(city__in=values)
                        
                elif column_id == 'field_of_activity':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # برای ManyToMany field، باید از ActivityField objects استفاده کنیم
                        from core.CustomerModel import ActivityField
                        activity_objects = []
                        for value in values:
                            # پیدا کردن ActivityField که __str__() آن معادل value است
                            for activity in ActivityField.objects.all():
                                if str(activity) == value:
                                    activity_objects.append(activity)
                                    break
                        
                        if activity_objects:
                            if filter_type == 'include':
                                filter_conditions &= Q(field_of_activity__in=activity_objects)
                            else:
                                filter_conditions &= ~Q(field_of_activity__in=activity_objects)
                        
                elif column_id == 'purchase_preferences':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # برای ManyToMany field، باید از PaymentPreference objects استفاده کنیم
                        from core.CustomerModel import PaymentPreference
                        payment_objects = []
                        for value in values:
                            for payment in PaymentPreference.objects.all():
                                if str(payment) == value:
                                    payment_objects.append(payment)
                                    break
                        
                        if payment_objects:
                            if filter_type == 'include':
                                filter_conditions &= Q(purchase_preferences__in=payment_objects)
                            else:
                                filter_conditions &= ~Q(purchase_preferences__in=payment_objects)
                        
                elif column_id == 'product_preferences':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        # برای ManyToMany field، باید از ProductPreference objects استفاده کنیم
                        from core.CustomerModel import ProductPreference
                        product_objects = []
                        for value in values:
                            for product in ProductPreference.objects.all():
                                if str(product) == value:
                                    product_objects.append(product)
                                    break
                        
                        if product_objects:
                            if filter_type == 'include':
                                filter_conditions &= Q(product_preferences__in=product_objects)
                            else:
                                filter_conditions &= ~Q(product_preferences__in=product_objects)
                        
                elif column_id in ['is_favorite', 'is_active', 'sms_preference', 'whatsapp_preference']:
                    bool_values = []
                    for v in values:
                        if v.lower() in ['بله', 'true', '1', 'yes']:
                            bool_values.append(True)
                        elif v.lower() in ['خیر', 'false', '0', 'no']:
                            bool_values.append(False)
                    
                    if bool_values:
                        if filter_type == 'include':
                            filter_conditions &= Q(**{f'{column_id}__in': bool_values})
                        else:
                            filter_conditions &= ~Q(**{f'{column_id}__in': bool_values})
                
                elif column_id == 'purchase_count':
                    # فیلتر عددی برای تعداد خریدها
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(int(cleaned_value))
                        
                        if numeric_values:
                            # ابتدا annotate کنیم
                            base_queryset = base_queryset.annotate(
                                purchase_count_annotation=Count('purchases_made')
                            )
                            if filter_type == 'include':
                                filter_conditions &= Q(purchase_count_annotation__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(purchase_count_annotation__in=numeric_values)
                                
                    except (ValueError, TypeError):
                        continue
                
                elif column_id == 'total_purchase_weight':
                    # فیلتر عددی برای وزن کل خریدها
                    try:
                        numeric_values = []
                        for v in values:
                            if v and str(v).strip():
                                cleaned_value = str(v).replace(',', '').replace('٬', '').strip()
                                if cleaned_value.replace('.', '').isdigit():
                                    numeric_values.append(float(cleaned_value))
                        
                        if numeric_values:
                            # ابتدا annotate کنیم
                            base_queryset = base_queryset.annotate(
                                total_weight_annotation=Sum('purchases_made__order_weight', default=0)
                            )
                            if filter_type == 'include':
                                filter_conditions &= Q(total_weight_annotation__in=numeric_values)
                            else:
                                filter_conditions &= ~Q(total_weight_annotation__in=numeric_values)
                                
                    except (ValueError, TypeError):
                        continue
                
                elif column_id in ['description']:
                    # فقط description (added_description) موجود است
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(added_description__in=values)
                        else:
                            filter_conditions &= ~Q(added_description__in=values)
                
                elif column_id == 'created_at':
                    # فیلتر تاریخی
                    try:
                        date_conditions = Q()
                        for date_str in values:
                            if date_str and date_str.strip():
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts) == 3:
                                        year, month, day = parts
                                        date_obj = datetime(int(year), int(month), int(day)).date()
                                        date_conditions |= Q(created_at__date=date_obj)
                        
                        if date_conditions:
                            if filter_type == 'include':
                                filter_conditions &= date_conditions
                            else:
                                filter_conditions &= ~date_conditions
                                
                    except (ValueError, TypeError):
                        continue
                
                elif column_id == 'last_purchase_date':
                    # فیلتر بر اساس تاریخ آخرین خرید
                    try:
                        # برای این فیلتر باید customer هایی را پیدا کنیم که آخرین خریدشان در تاریخ‌های مشخص شده است
                        customer_ids_with_last_purchase = []
                        
                        for date_str in values:
                            if date_str and date_str.strip():
                                if '/' in date_str:
                                    parts = date_str.split('/')
                                    if len(parts) == 3:
                                        year, month, day = parts
                                        date_obj = datetime(int(year), int(month), int(day)).date()
                                        
                                        # پیدا کردن مشتریانی که آخرین خریدشان در این تاریخ است
                                        from core.PurchaseModel import Purchase
                                        customers_with_purchase_on_date = base_queryset.filter(
                                            purchases_made__created_at__date=date_obj
                                        ).distinct()
                                        
                                        for customer in customers_with_purchase_on_date:
                                            last_purchase = customer.purchases_made.first()
                                            if last_purchase and last_purchase.created_at.date() == date_obj:
                                                customer_ids_with_last_purchase.append(customer.id)
                        
                        if customer_ids_with_last_purchase:
                            if filter_type == 'include':
                                filter_conditions &= Q(id__in=customer_ids_with_last_purchase)
                            else:
                                filter_conditions &= ~Q(id__in=customer_ids_with_last_purchase)
                                
                    except (ValueError, TypeError):
                        continue
            
            # اعمال فیلترها
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع
        if global_search and global_search.strip():
            logger.info(f"🔍 Applying global search for: '{global_search}'")
            
            # تمیز کردن جستجو برای شماره تلفن (فقط اعداد)
            clean_search_for_phone = ''.join(c for c in global_search if c.isdigit())
            
            # ساخت شرایط جستجو
            search_conditions = Q(name__icontains=global_search)  # جستجو در نام
            
            # اگر جستجو شامل اعداد است، در شماره‌های تلفن نیز جستجو کن
            if clean_search_for_phone:
                search_conditions |= Q(phone_number__icontains=clean_search_for_phone)
                search_conditions |= Q(phone_numbers__number__icontains=clean_search_for_phone)
            
            # جستجو در شهر و توضیحات
            search_conditions |= Q(city__icontains=global_search)
            search_conditions |= Q(added_description__icontains=global_search)
            
            # اگر جستجو فقط حروف باشد، امکان جستجو در فیلدهای مرتبط دیگر
            if global_search.isalpha():
                # جستجو در حوزه فعالیت
                from core.CustomerModel import ActivityField
                matching_activities = ActivityField.objects.filter(code__icontains=global_search)
                if matching_activities.exists():
                    search_conditions |= Q(field_of_activity__in=matching_activities)
            
            base_queryset = base_queryset.filter(search_conditions).distinct()
            logger.info(f"🔍 Global search applied, queryset count: {base_queryset.count()}")
        else:
            logger.info("🔍 No global search applied")
        
        # اعمال مرتب‌سازی
        if sort_config and sort_config.get('column'):
            sort_column = sort_config['column']
            sort_direction = sort_config.get('direction', 'asc')
            
            # تعیین نام فیلد برای مرتب‌سازی
            sort_field_mapping = {
                'name': 'name',
                'phone_number': 'phone_number',
                'city': 'city',
                'field_of_activity': 'field_of_activity__name',
                'is_favorite': 'is_favorite',
                'is_active': 'is_active',
                'is_blocked': 'is_blocked',
                'sms_preference': 'sms_preference',
                'whatsapp_preference': 'whatsapp_preference',
                'created_at': 'created_at',
                'updated_at': 'updated_at',
                'purchase_count': 'purchase_count_annotation',
                'total_purchase_weight': 'total_weight_annotation',
                'last_purchase_date': 'last_purchase_annotation',
            }
            
            # دریافت فیلد مرتب‌سازی
            sort_field = sort_field_mapping.get(sort_column, sort_column)
            
            # اگر مرتب‌سازی بر اساس فیلدهای محاسبه شده است، annotate کنیم
            if sort_column == 'purchase_count':
                try:
                    if not hasattr(base_queryset.query, 'annotations') or 'purchase_count_annotation' not in base_queryset.query.annotations:
                        base_queryset = base_queryset.annotate(
                            purchase_count_annotation=Count('purchases_made')
                        )
                except:
                    base_queryset = base_queryset.annotate(
                        purchase_count_annotation=Count('purchases_made')
                    )
            elif sort_column == 'total_purchase_weight':
                try:
                    if not hasattr(base_queryset.query, 'annotations') or 'total_weight_annotation' not in base_queryset.query.annotations:
                        base_queryset = base_queryset.annotate(
                            total_weight_annotation=Sum('purchases_made__order_weight', default=0)
                        )
                except:
                    base_queryset = base_queryset.annotate(
                        total_weight_annotation=Sum('purchases_made__order_weight', default=0)
                    )
            elif sort_column == 'last_purchase_date':
                try:
                    if not hasattr(base_queryset.query, 'annotations') or 'last_purchase_annotation' not in base_queryset.query.annotations:
                        base_queryset = base_queryset.annotate(
                            last_purchase_annotation=Max('purchases_made__created_at')
                        )
                except:
                    base_queryset = base_queryset.annotate(
                        last_purchase_annotation=Max('purchases_made__created_at')
                    )
            
            if sort_direction == 'desc':
                sort_field = f'-{sort_field}'
                
            try:
                base_queryset = base_queryset.order_by(sort_field)
                logger.info(f"مرتب‌سازی اعمال شد: {sort_field}")
            except Exception as e:
                logger.warning(f"خطا در مرتب‌سازی: {e}")
                base_queryset = base_queryset.order_by('name')
        else:
            # مرتب‌سازی پیش‌فرض
            base_queryset = base_queryset.order_by('name')
        
        # محاسبه تعداد کل قبل از pagination
        total_count = base_queryset.count()
        
        # اعمال pagination
        if per_page == 999999:  # نمایش همه
            page_obj = base_queryset
            paginator = None
        else:
            from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
            paginator = Paginator(base_queryset, per_page)
            try:
                page_obj = paginator.page(page)
            except (EmptyPage, PageNotAnInteger):
                page_obj = paginator.page(1)
                page = 1
        
        # فرمت نتایج برای JSON response
        results = []
        for customer in page_obj:
            # محاسبه اطلاعات اضافی
            purchase_count = customer.purchases_made.count()
            total_weight = sum(p.order_weight or 0 for p in customer.purchases_made.all())
            last_purchase = customer.purchases_made.first()
            
            # دریافت شماره تلفن اصلی
            primary_phone = customer.get_primary_phone() if hasattr(customer, 'get_primary_phone') else customer.phone_number
            
            # Debug logging
            logger.info(f"Customer {customer.id}: name={customer.name}, city={customer.city}")
            logger.info(f"  field_of_activity count: {customer.field_of_activity.count()}")
            logger.info(f"  purchase_preferences count: {customer.purchase_preferences.count()}")
            logger.info(f"  product_preferences count: {customer.product_preferences.count()}")
            
            result = {
                'id': customer.id,
                'name': customer.name or "",
                'phone_number': primary_phone or "",
                'city': customer.city or "",
                'field_of_activity': ", ".join([str(f) for f in customer.field_of_activity.all()]) or "",
                'purchase_preferences': ", ".join([str(p) for p in customer.purchase_preferences.all()]) or "",
                'product_preferences': ", ".join([str(p) for p in customer.product_preferences.all()]) or "",
                'is_favorite': customer.is_favorite,
                'is_active': customer.is_active,
                'sms_preference': customer.sms_preference,
                'whatsapp_preference': customer.whatsapp_preference,
                'purchase_count': purchase_count,
                'total_purchase_weight': total_weight,
                'last_purchase_date': last_purchase.created_at.strftime("%Y/%m/%d") if last_purchase else "",
                'created_at': customer.created_at.strftime("%Y/%m/%d") if customer.created_at else "",
                'updated_at': customer.updated_at.strftime("%Y/%m/%d") if customer.updated_at else "",
                'address': "",  # فیلد address در مدل وجود ندارد
                'description': customer.added_description or "",
                'national_code': "",  # فیلد national_code در مدل وجود ندارد
            }
            
            # Debug logging برای نتیجه نهایی
            logger.info(f"Final result for customer {customer.id}: {result}")
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
        logger.error(f"خطا در اعمال فیلتر به مشتریان: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در اعمال فیلتر: {str(e)}'
        }, status=500)

@role_required('sales_agent', 'admin')
@login_required
@require_POST
def get_customer_column_values(request):
    """
    API برای دریافت مقادیر منحصر به فرد یک ستون برای فیلتر
    """
    logger.warning(f"API برای دریافت مقادیر منحصر به فرد ستون مشتری توسط {request.user.username}.")
    try:
        # بررسی دسترسی کارشناس فروش
        if not hasattr(request.user, 'sales_agent'):
            return JsonResponse({'success': False, 'error': 'شما مجاز به مشاهده این بخش نیستید'}, status=403)

        sales_agent = request.user.sales_agent
        column_id = request.POST.get('column_id')
        search_term = request.POST.get('search', '')
        # دریافت فیلترهای فعلی
        current_filters = request.POST.get('current_filters', '{}')
        # دریافت جستجوی سریع
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
        base_queryset = sales_agent.get_all_customers().prefetch_related(
            'field_of_activity',
            'purchase_preferences',
            'product_preferences',
            'purchases_made',
            'phone_numbers'
        )
        
        # اعمال فیلترهای فعلی (بجز فیلتر ستون فعلی)
        if current_filters:
            filter_conditions = Q()
            
            for filter_column_id, filter_data in current_filters.items():
                # رد کردن فیلتر ستون فعلی
                if filter_column_id == column_id:
                    continue
                    
                if not filter_data.get('values'):
                    continue
                    
                values = filter_data['values']
                filter_type = filter_data.get('type', 'include')
                
                if filter_column_id == 'name':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(name__in=values)
                        else:
                            filter_conditions &= ~Q(name__in=values)
                        
                elif filter_column_id == 'city':
                    values = [v for v in values if v and v.strip()]
                    if values:
                        if filter_type == 'include':
                            filter_conditions &= Q(city__in=values)
                        else:
                            filter_conditions &= ~Q(city__in=values)
                        
                # اضافه کردن فیلترهای بیشتر در صورت نیاز
            
            # اعمال فیلترها
            if filter_conditions:
                base_queryset = base_queryset.filter(filter_conditions)
        
        # اعمال جستجوی سریع
        if global_search and global_search.strip():
            logger.info(f"🔍 Applying global search in column values for: '{global_search}'")
            
            # تمیز کردن جستجو برای شماره تلفن (فقط اعداد)
            clean_search_for_phone = ''.join(c for c in global_search if c.isdigit())
            
            # ساخت شرایط جستجو
            search_conditions = Q(name__icontains=global_search)  # جستجو در نام
            
            # اگر جستجو شامل اعداد است، در شماره‌های تلفن نیز جستجو کن
            if clean_search_for_phone:
                search_conditions |= Q(phone_number__icontains=clean_search_for_phone)
                search_conditions |= Q(phone_numbers__number__icontains=clean_search_for_phone)
            
            # جستجو در شهر
            search_conditions |= Q(city__icontains=global_search)
            
            base_queryset = base_queryset.filter(search_conditions).distinct()
        
        # دریافت مقادیر بر اساس نوع ستون
        values = []
        
        if column_id == 'name':
            values_qs = base_queryset.values_list('name', flat=True).distinct().exclude(name__isnull=True).exclude(name='')
            values = list(values_qs)
            
        elif column_id == 'phone_number':
            # شامل تمام شماره‌های تلفن
            phone_values = set()
            for customer in base_queryset:
                if customer.phone_number:
                    phone_values.add(customer.phone_number)
                for phone in customer.phone_numbers.all():
                    if phone.number:
                        phone_values.add(phone.number)
            values = list(phone_values)
            
        elif column_id == 'city':
            values_qs = base_queryset.values_list('city', flat=True).distinct().exclude(city__isnull=True).exclude(city='')
            values = list(values_qs)
            
        elif column_id == 'field_of_activity':
            # برای ManyToMany field، باید همه ActivityField objects را دریافت کنیم که در customers موجود استاس
            from core.CustomerModel import ActivityField
            activity_values = set()
            for customer in base_queryset.prefetch_related('field_of_activity'):
                for activity in customer.field_of_activity.all():
                    activity_values.add(str(activity))
            values = list(activity_values)
            
        elif column_id == 'purchase_preferences':
            # برای ManyToMany field، باید همه PaymentPreference objects را دریافت کنیم
            from core.CustomerModel import PaymentPreference
            pref_values = set()
            for customer in base_queryset.prefetch_related('purchase_preferences'):
                for pref in customer.purchase_preferences.all():
                    pref_values.add(str(pref))
            values = list(pref_values)
            
        elif column_id == 'product_preferences':
            # برای ManyToMany field، باید همه ProductPreference objects را دریافت کنیم
            from core.CustomerModel import ProductPreference
            pref_values = set()
            for customer in base_queryset.prefetch_related('product_preferences'):
                for pref in customer.product_preferences.all():
                    pref_values.add(str(pref))
            values = list(pref_values)
            
        elif column_id in ['is_favorite', 'is_active', 'sms_preference', 'whatsapp_preference']:
            # مقادیر boolean
            bool_values = base_queryset.values_list(column_id, flat=True).distinct()
            values = ['بله' if v else 'خیر' for v in bool_values]
            
        elif column_id == 'purchase_count':
            # محاسبه تعداد خریدها
            count_values = set()
            for customer in base_queryset:
                count = customer.purchases_made.count()
                count_values.add(count)
            values = sorted(list(count_values))
            
        elif column_id == 'total_purchase_weight':
            # محاسبه وزن کل خریدها
            weight_values = set()
            for customer in base_queryset:
                total_weight = sum(p.order_weight or 0 for p in customer.purchases_made.all())
                if total_weight > 0:
                    weight_values.add(total_weight)
            values = sorted(list(weight_values))
            
        elif column_id == 'description':
            # فقط added_description موجود است
            values_qs = base_queryset.values_list('added_description', flat=True).distinct().exclude(added_description__isnull=True).exclude(added_description='')
            values = list(values_qs)
            
        elif column_id in ['created_at', 'updated_at']:
            # تاریخ‌ها
            date_values = set()
            for customer in base_queryset:
                date_val = getattr(customer, column_id, None)
                if date_val:
                    date_values.add(date_val.strftime("%Y/%m/%d"))
            values = sorted(list(date_values))
            
        elif column_id == 'last_purchase_date':
            # تاریخ آخرین خرید
            date_values = set()
            for customer in base_queryset:
                last_purchase = customer.purchases_made.first()  # فرض بر این است که قبلاً مرتب شده‌اند
                if last_purchase:
                    date_values.add(last_purchase.created_at.strftime("%Y/%m/%d"))
            values = sorted(list(date_values), reverse=True)  # جدیدترین‌ها اول
        
        # فیلتر کردن بر اساس search_term
        if search_term:
            values = [v for v in values if search_term.lower() in str(v).lower()]
        
        # محدود کردن تعداد نتایج
        values = values[:100]
        
        return JsonResponse({
            'status': 'success',
            'values': values,
            'count': len(values)
        })
        
    except Exception as e:
        logger.error(f"خطا در دریافت مقادیر ستون مشتری: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در دریافت مقادیر: {str(e)}'
        }, status=500)