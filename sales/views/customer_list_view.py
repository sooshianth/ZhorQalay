from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum, F
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

@role_required('sales_agent', 'admin')
@login_required
def enhanced_customer_list_view(request):
    if not hasattr(request.user, 'sales_agent'):
        messages.error(request, "شما مجاز به مشاهده این بخش نیستید.")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent
    customers = sales_agent.get_all_customers()
    
    # فیلتر جستجو
    search_query = request.GET.get('search', '')
    if search_query:
        # تمیز کردن شماره تلفن از کاراکترهای غیرعددی برای جستجوی بهتر
        clean_search = ''.join(c for c in search_query if c.isdigit())
        
        customers = customers.filter(
            Q(name__icontains=search_query) |
            Q(phone_number__icontains=clean_search) |
            Q(phone_numbers__number__icontains=clean_search)
        ).distinct()

    # فیلتر مورد علاقه
    favorites_only = request.GET.get('favorites_only', '') == 'true'
    if favorites_only:
        customers = customers.filter(is_favorite=True)

    # فیلتر شهرها (حالت چند انتخابی)
    city_filter = request.GET.getlist('city', [])
    if city_filter:
        customers = customers.filter(city__in=city_filter)

    # فیلتر حوزه فعالیت (حالت چند انتخابی)
    activity_filter = request.GET.getlist('activity', [])
    if activity_filter:
        customers = customers.filter(field_of_activity__code__in=activity_filter)

    # فیلتر ترجیحات پرداخت
    payment_filter = request.GET.getlist('payment', [])
    if payment_filter:
        customers = customers.filter(purchase_preferences__code__in=payment_filter)

    # فیلتر ترجیحات محصول
    product_filter = request.GET.getlist('product', [])
    if product_filter:
        customers = customers.filter(product_preferences__code__in=product_filter)

    # فیلتر وضعیت فعال/غیرفعال
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        customers = customers.filter(is_active=True)
    elif status_filter == 'inactive':
        customers = customers.filter(is_active=False)
    elif status_filter == 'blocked':
        customers = customers.filter(is_blocked=True)

    # فیلتر حداقل تعداد خریدها
    min_purchases = request.GET.get('min_purchases', '')
    if min_purchases and min_purchases.isdigit():
        customers = customers.annotate(
            purchase_count=Count('purchases_made')
        ).filter(purchase_count__gte=int(min_purchases))

    # فیلتر آخرین خرید در X روز گذشته
    last_purchase_days = request.GET.get('last_purchase_days', '')
    if last_purchase_days and last_purchase_days.isdigit():
        date_threshold = timezone.now() - timedelta(days=int(last_purchase_days))
        customers = customers.filter(
            purchases_made__created_at__gte=date_threshold
        ).distinct()

    # فیلتر ترجیح واتساپ یا پیامک
    sms_preference = request.GET.get('sms_preference', '')
    if sms_preference == 'yes':
        customers = customers.filter(sms_preference=True)
    elif sms_preference == 'no':
        customers = customers.filter(sms_preference=False)

    whatsapp_preference = request.GET.get('whatsapp_preference', '')
    if whatsapp_preference == 'yes':
        customers = customers.filter(whatsapp_preference=True)
    elif whatsapp_preference == 'no':
        customers = customers.filter(whatsapp_preference=False)

    # محاسبه حجم کل خرید برای هر مشتری
    customers = customers.annotate(
        total_purchase_weight=Sum('purchases_made__order_weight', default=0)
    )

    # مرتب‌سازی
    SORT_OPTIONS = {
        'name_asc': 'name',
        'name_desc': '-name',
        'city_asc': 'city',
        'city_desc': '-city',
        'purchase_asc': 'purchase_count',
        'purchase_desc': '-purchase_count',
        'updated_asc': 'updated_at',
        'updated_desc': '-updated_at',
        'amount_asc': 'total_purchase_weight',
        'amount_desc': '-total_purchase_weight',
        'favorite_asc': 'is_favorite',
        'favorite_desc': '-is_favorite',
        'phone_asc': 'phone_number',
        'phone_desc': '-phone_number',
    }
    
    sort_key = request.GET.get('sort', 'name_asc')
    sort_field = SORT_OPTIONS.get(sort_key, 'name')
    
    # اگر مرتب‌سازی بر اساس خریدهاست و هنوز annotate نشده
    if sort_field in ['purchase_count', '-purchase_count'] and 'purchase_count' not in [f.name for f in customers.query.annotations]:
        customers = customers.annotate(purchase_count=Count('purchases_made'))
    
    customers = customers.order_by(sort_field)

    # بررسی درخواست AJAX برای جستجوی real-time
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # برای درخواست‌های AJAX، فقط نتایج محدودتری برمی‌گردانیم
        customers_data = []
        limited_customers = customers
        
        for customer in limited_customers:
            customers_data.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.get_primary_phone(),
                'city': customer.city or '',
                'purchase_count': customer.purchases_made.count(),
                'total_weight': float(customer.total_purchase_weight or 0),
                'is_favorite': customer.is_favorite,
                'field_of_activity': customer.get_field_of_activity_display()
            })
        
        return JsonResponse({
            'customers': customers_data,
            'total_count': customers.count()
        })



    # دریافت لیست‌های مورد نیاز برای فیلترها
    all_cities = Customer.objects.values_list('city', flat=True).distinct().exclude(city__isnull=True).exclude(city='').order_by('city')
    all_activities = ActivityField.objects.all().order_by('code')
    all_payment_preferences = PaymentPreference.objects.all().order_by('code')
    all_product_preferences = ProductPreference.objects.all().order_by('code')

    # محاسبه سهمیه پیامک
    sms_quota = getattr(settings, 'SALES_AGENT_SMS_QOUTA', 0)
    
    # اضافه کردن اطلاعات بیشتر برای هر مشتری با prefetch_related برای بهینه‌سازی
    customers_with_preferences = customers.prefetch_related(
        'purchase_preferences',
        'product_preferences',
        'purchases_made'
    )
    
    # صفحه‌بندی
    paginator = Paginator(customers_with_preferences, 25)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    # اضافه کردن اطلاعات بیشتر برای هر مشتری
    for customer in page_obj:
        # محاسبه آخرین خرید
        if customer.purchases_made.exists():
            customer.last_purchase_date = customer.purchases_made.first().created_at
        else:
            customer.last_purchase_date = None
            
        # محاسبه وزن کل خریدها
        total_weight = 0
        for purchase in customer.purchases_made.all():
            if purchase.order_weight:
                total_weight += purchase.order_weight
        customer.total_purchase_weight = total_weight

    # آماده‌سازی context
    context = {
        'customers': page_obj,
        'search_query': search_query,
        'favorites_only': favorites_only,
        'city_filter': city_filter,
        'activity_filter': activity_filter,
        'payment_filter': payment_filter,
        'product_filter': product_filter,
        'status_filter': status_filter,
        'min_purchases': min_purchases,
        'last_purchase_days': last_purchase_days,
        'sms_preference': sms_preference,
        'whatsapp_preference': whatsapp_preference,
        'sort_key': sort_key,
        'all_cities': all_cities,
        'all_activities': all_activities,
        'all_payment_preferences': all_payment_preferences,
        'all_product_preferences': all_product_preferences,
        'sms_quota': sms_quota,
        'total_customers': customers.count(),
        'has_filters': any([
            search_query, favorites_only, city_filter, activity_filter,
            payment_filter, product_filter, status_filter, min_purchases,
            last_purchase_days, sms_preference, whatsapp_preference
        ])
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
            'product_type': product.type,
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