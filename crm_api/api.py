from django.shortcuts import render
from core.PurchaseModel import Purchase, ShenaseTakhsis, PurchaseStateChange
from core.CargoProductModel import CargoProduct
from bki_barnameh.models.BarnamehModel import Barnameh
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
import json
from core.CustomerModel import Customer, CrmAccessNumbers, PhoneNumber
from django.core.exceptions import ValidationError
import logging
from django.db import models
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger("crm_api_api")

def clean_phone_number(phone: str) -> str:
    """تمیز کردن شماره تلفن"""
    if not phone:
        return None
    
    # حذف کاراکترهای غیرضروری
    phone = ''.join(filter(str.isdigit, str(phone)))
    
    # اگر با 0 شروع می‌شود، آن را حذف کن
    if phone.startswith('0'):
        phone = phone[1:]
    
    # اگر با 98 شروع می‌شود، آن را حذف کن
    if phone.startswith('98'):
        phone = phone[2:]
    
    return phone

def validate_access(phone_number, purchase_number):
    """
    اعتبارسنجی دسترسی بر اساس شماره تلفن و شماره خرید
    
    Args:
        phone_number (str): شماره تلفن
        purchase_number (str): شماره خرید
        
    Returns:
        tuple: (customer, purchase, error_message)
    """
    try:
        # تمیز کردن شماره تلفن
        clean_phone = clean_phone_number(phone_number)
        if not clean_phone:
            return None, None, "شماره تلفن نامعتبر است"
        
        # یافتن خرید
        try:
            purchase = Purchase.objects.get(purchase_number=purchase_number)
        except Purchase.DoesNotExist:
            return None, None, "شماره خرید یافت نشد"
        
        # راه اول: جستجو در CrmAccessNumbers
        # ایجاد variations مختلف شماره برای جستجو
        phone_variations = [
            clean_phone,
            f"0{clean_phone}",
            f"98{clean_phone}"
        ]
        
        crm_access_query = Q()
        for phone_var in phone_variations:
            crm_access_query |= Q(phone_number=phone_var)
        
        crm_accesses = CrmAccessNumbers.objects.filter(crm_access_query)
        
        for crm_access in crm_accesses:
            customer = crm_access.customer
            # بررسی اینکه آیا این مشتری مالک این خرید است یا نه
            if purchase.customer == customer or purchase.bazaargah_customer == customer:
                return customer, purchase, None
        
        # راه دوم: جستجو مستقیم در PhoneNumber
        phone_record = PhoneNumber.objects.filter(number=clean_phone).first()
        if phone_record:
            customer = phone_record.customer
            # بررسی اینکه آیا این مشتری مالک این خرید است یا نه
            if purchase.customer == customer or purchase.bazaargah_customer == customer:
                return customer, purchase, None
        
        # راه سوم: جستجو در فیلد phone_number قدیمی Customer
        customer = Customer.objects.filter(phone_number=clean_phone).first()
        if customer:
            # بررسی اینکه آیا این مشتری مالک این خرید است یا نه
            if purchase.customer == customer or purchase.bazaargah_customer == customer:
                return customer, purchase, None
        
        # راه چهارم: جستجو در شماره‌های خرید (bazaargah_phone_number, tahvil_phone_number)
        # این برای مواردی است که شماره در خود خرید ذخیره شده
        if (purchase.bazaargah_phone_number and clean_phone_number(purchase.bazaargah_phone_number) == clean_phone) or \
           (purchase.tahvil_phone_number and clean_phone_number(purchase.tahvil_phone_number) == clean_phone):
            # اگر شماره در خرید موجود است، مشتری بازارگاه را برگردان
            if purchase.bazaargah_customer:
                return purchase.bazaargah_customer, purchase, None
            elif purchase.customer:
                return purchase.customer, purchase, None
        
        return None, None, "شماره تلفن برای این خرید مجاز نیست"
        
    except Exception as e:
        logger.error(f"خطا در اعتبارسنجی دسترسی: {str(e)}")
        return None, None, f"خطای سیستمی: {str(e)}"

@method_decorator(csrf_exempt, name='dispatch')
class PurchaseInfoAPI(View):
    """API برای دریافت اطلاعات خرید"""
    
    def post(self, request):
        try:
            # پارس کردن JSON data
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
            purchase_number = data.get('purchase_number')
            
            if not phone_number or not purchase_number:
                return JsonResponse({
                    'success': False,
                    'error': 'شماره تلفن و شماره خرید الزامی است'
                }, status=400)
            
            # اعتبارسنجی دسترسی
            customer, purchase, error = validate_access(phone_number, purchase_number)
            
            if error:
                return JsonResponse({
                    'success': False,
                    'error': error
                }, status=403)
            
            # تهیه اطلاعات خرید - بهبود یافته
            purchase_data = {
                # اطلاعات اصلی خرید
                'purchase_number': purchase.purchase_number,
                'invoice_id': purchase.invoice_id,
                'tracking_number': purchase.tracking_number,
                'shenase_takhsis': purchase.shenase_takhsis,
                
                # وضعیت خرید
                'state': purchase.state,
                'state_display': purchase.get_state_display(),
                'priority': purchase.priority,
                'priority_display': purchase.get_priority_display(),
                'priority_reason': purchase.priority_reason,
                'is_urgent': purchase.is_urgent,
                'is_canceled': purchase.is_canceled,
                'is_archived': purchase.is_archived,
                
                # اطلاعات وزن و مقدار
                'order_weight': purchase.order_weight,
                'delivered_weight': purchase.delivered_weight,
                'total_weight': purchase.total_weight,
                
                # اطلاعات مالی (بدون اطلاعات محرمانه)
                'customer_price': purchase.customer_price,
                'amount_paid': purchase.amount_paid,
                'payment_method': purchase.payment_method,
                'mabna_profit': purchase.mabna_profit,
                'ready_for_invoice': purchase.ready_for_invoice,
                'is_fully_tasvied': purchase.is_fully_tasvied,
                'is_factored': purchase.is_factored,
                'factor_status': purchase.factor_status,
                'factor_status_display': purchase.get_factor_status_display(),
                
                # اطلاعات خریدار
                'buyer_name': purchase.buyer_name,
                'buyer_national_id': purchase.buyer_national_id,
                'buyer_user_type': purchase.buyer_user_type,
                'buyer_user_type_display': purchase.get_buyer_user_type_display() if purchase.buyer_user_type else None,
                'code_melli_tahvil': purchase.code_melli_tahvil,
                'bazaargah_phone_number': purchase.bazaargah_phone_number,
                'tahvil_phone_number': purchase.tahvil_phone_number,
                
                # اطلاعات آدرس و تحویل
                'address': purchase.address,
                'delivery_address': purchase.delivery_address,
                'delivery_postal_code': purchase.delivery_postal_code,
                'delivery_receiver_name': purchase.delivery_receiver_name,
                'unique_delivery_id': purchase.unique_delivery_id,
                'vehicle_type': purchase.vehicle_type,
                'vehicle_type_display': purchase.get_vehicle_type_display() if purchase.vehicle_type else None,
                'is_address_sent': purchase.is_address_sent,
                
                # اطلاعات محصول کوتاه
                'cargo_product_type': purchase.cargo.get_product_type_display() if purchase.cargo else 'نامشخص',
                'cargo_country': purchase.cargo.get_country_display() if purchase.cargo else 'نامشخص',
                'cargo_cottage': purchase.cargo.cottage if purchase.cargo else 'نامشخص',
                
                # اطلاعات اختلاف
                'extelaf_type': purchase.extelaf_type,
                'extelaf_weight': purchase.extelaf_weight,
                'extelaf_amount': purchase.extelaf_amount,
                
                # اطلاعات باربری - کامل
                'barbary_confidential_number': purchase.barbary_confidential_number,
                'barbary_customer_number': purchase.barbary_customer_number,
                
                # اطلاعات تاریخ
                'created_at': purchase.created_at.isoformat() if purchase.created_at else None,
                'updated_at': purchase.updated_at.isoformat() if purchase.updated_at else None,
                'type': purchase.type,
                'description': purchase.description,
                'send_cottage_sms': purchase.send_cottage_sms,
                'wallet_index': purchase.wallet_index,
            }
            
            # اطلاعات محصول - بهبود یافته
            if purchase.cargo:
                purchase_data['cargo'] = {
                    # اطلاعات اصلی محصول
                    'cottage': purchase.cargo.cottage,
                    'product_type': purchase.cargo.product_type,
                    'product_type_display': purchase.cargo.get_product_type_display(),
                    'country': purchase.cargo.country,
                    'country_display': purchase.cargo.get_country_display(),
                    'type': purchase.cargo.type,
                    
                    # اطلاعات تکمیلی محصول
                    'port': purchase.cargo.port,
                    'loading_time': purchase.cargo.loading_time,
                    'description': purchase.cargo.description,
                    'weight': purchase.cargo.weight,
                    'status': purchase.cargo.status,
                    'created_at': purchase.cargo.created_at.isoformat() if purchase.cargo.created_at else None,
                    'last_modified': purchase.cargo.last_modified.isoformat() if purchase.cargo.last_modified else None,
                    'customer_price': purchase.cargo.customer_price,
                    
                    # اطلاعات باربری - کامل
                    'barbary_info': {
                        'name': purchase.cargo.barbary.name if purchase.cargo.barbary else None,
                        'phone_number': purchase.cargo.barbary.phone_number if purchase.cargo.barbary else None,
                        'email': purchase.cargo.barbary.email if purchase.cargo.barbary else None,
                        'description': purchase.cargo.barbary.description if purchase.cargo.barbary else None,
                    } if purchase.cargo.barbary else None,
                    
                    # اطلاعات واردکننده - فقط اسم
                    'vared_konandeh_name': purchase.cargo.vared_konandeh.name if purchase.cargo.vared_konandeh else None,
                }
            
            # اطلاعات مشتری - بهبود یافته
            customer_data = {
                # اطلاعات اصلی مشتری
                'name': customer.name,
                'city': customer.city,
                'phone_number': customer.get_primary_phone(),
                'all_phone_numbers': customer.get_all_phone_numbers(purchase, True),
                
                # اطلاعات تکمیلی
                'field_of_activity': customer.get_field_of_activity_display(),
                'field_of_activity_list': customer.get_field_of_activity_list(),
                'purchase_preferences_list': customer.get_purchase_preferences_list(),
                'product_preferences_list': customer.get_product_preferences_list(),
                'whatsapp_preference': customer.whatsapp_preference,
                'sms_preference': customer.sms_preference,
                'social_media': customer.social_media,
                'added_description': customer.added_description,
                'contact_start_time': customer.contact_start_time.isoformat() if customer.contact_start_time else None,
                'contact_end_time': customer.contact_end_time.isoformat() if customer.contact_end_time else None,
                'day_of_week': customer.day_of_week,
                'quota': customer.quota,
                'is_bazaargah_enjoyer': customer.is_bazaargah_enjoyer,
                'is_favorite': customer.is_favorite,
                'is_active': customer.is_active,
                'is_blocked': customer.is_blocked,
                'created_at': customer.created_at.isoformat() if customer.created_at else None,
                'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
            }
            
            # اطلاعات بارنامه‌ها - بهبود یافته
            barnameh_data = []
            barnamehs = Barnameh.objects.filter(purchase_number=purchase_number)
            for barnameh in barnamehs:
                barnameh_info = {
                    # اطلاعات اصلی بارنامه
                    'id': barnameh.id,
                    'number': barnameh.number,
                    'serial': barnameh.serial,
                    'tonnage': float(barnameh.tonnage) if barnameh.tonnage else None,
                    'status': barnameh.status,
                    'status_display': barnameh.get_status_display(),
                    
                    # اطلاعات تخصیص
                    'shenase_takhsis_code': barnameh.shenase_takhsis_code,
                    'purchase_number': barnameh.purchase_number,
                    'haml_id': barnameh.haml_id,
                    
                    # اطلاعات راننده و حمل - کامل
                    'driver_name': barnameh.driver_name,
                    'driver_phone': barnameh.driver_phone,
                    'vehicle_plate': barnameh.vehicle_plate,
                    'receiver_name': barnameh.receiver_name,
                    'destination': barnameh.destination,
                    'transport_date': barnameh.transport_date.isoformat() if barnameh.transport_date else None,
                    
                    # اطلاعات اضافی
                    'buyer_postal_code': barnameh.buyer_postal_code,
                    'factor_sodoor_season': barnameh.factor_sodoor_season,
                    'is_factored': barnameh.is_factored,
                    'is_created_by_excel': barnameh.is_created_by_excel,
                    
                    # اطلاعات ارسال به بازارگاه
                    'is_sent_to_bki': barnameh.is_sent_to_bki,
                    'is_sent_to_bki_at': barnameh.is_sent_to_bki_at.isoformat() if barnameh.is_sent_to_bki_at else None,
                    
                    # اطلاعات تاریخ
                    'barnameh_date': barnameh.barnameh_date.isoformat() if barnameh.barnameh_date else None,
                    'barnameh_created_at': barnameh.barnameh_created_at.isoformat() if barnameh.barnameh_created_at else None,
                    'barnameh_updated_at': barnameh.barnameh_updated_at.isoformat() if barnameh.barnameh_updated_at else None,
                    
                    # اطلاعات محاسبه شده از خرید
                    'calculated_info': {
                        'total_sales_amount': barnameh.get_total_sales_amount(),
                        'buyer_national_code': barnameh.get_buyer_national_code(),
                        'buyer_address': barnameh.get_buyer_address(),
                        'demand_amount': barnameh.get_demand_amount(),
                        'product_type': barnameh.get_product_type(),
                        'successful_send_date': barnameh.get_successful_send_date().isoformat() if barnameh.get_successful_send_date() else None,
                    },
                    
                    # اطلاعات BKI Response (اگر موجود باشد)
                    'bki_response_data': barnameh.bki_response_data,
                }
                
                barnameh_data.append(barnameh_info)
            
            # شناسه‌های تخصیص - بهبود یافته
            allocation_data = []
            for allocation in purchase.shenase_takhsis_set.all():
                allocation_data.append({
                    'code': allocation.code,
                    'weight': allocation.weight,
                    'barnameh_weight': getattr(allocation, 'barnameh_weight', None),
                    'delivery_receiver_name': allocation.delivery_receiver_name or purchase.delivery_receiver_name or purchase.buyer_name,
                    'delivery_phone': allocation.tahvil_phone_number or purchase.tahvil_phone_number,
                    'delivery_national_id': allocation.code_melli_tahvil or purchase.code_melli_tahvil or purchase.buyer_national_id,
                    'delivery_address': allocation.delivery_address or purchase.delivery_address or purchase.address,
                    'delivery_postal_code': allocation.delivery_postal_code or purchase.delivery_postal_code,
                    'created_at': allocation.created_at.isoformat() if allocation.created_at else None,
                })
            
            # تاریخچه تغییرات وضعیت - جدید
            state_history = []
            state_changes = PurchaseStateChange.objects.filter(
                purchase=purchase
            ).order_by('-changed_at')
            
            for change in state_changes:
                state_history.append({
                    'previous_state': change.previous_state,
                    'previous_state_display': change.get_previous_state_display(),
                    'new_state': change.new_state,
                    'new_state_display': change.get_new_state_display(),
                    'changed_by': change.changed_by.get_full_name() if change.changed_by else None,
                    'changed_at': change.changed_at.isoformat() if change.changed_at else None,
                    'notes': change.notes,
                    'sms_sent': change.sms_sent,
                    'sms_sent_at': change.sms_sent_at.isoformat() if change.sms_sent_at else None,
                })
            
            # اطلاعات کارشناسان فروش - جدید
            sales_agents_data = []
            for agent in purchase.sales_agent.all():
                sales_agents_data.append({
                    'name': agent.name,
                    'phone_number': agent.phone_number,
                    'factor_code': agent.factor_code,
                })
            
            # اطلاعات کارشناس فروش منحصر به فرد
            unique_sales_agent_data = None
            if purchase.unique_sales_agent:
                unique_sales_agent_data = {
                    'name': purchase.unique_sales_agent.name,
                    'phone_number': purchase.unique_sales_agent.phone_number,
                    'factor_code': purchase.unique_sales_agent.factor_code,
                }
            
            return JsonResponse({
                'success': True,
                'data': {
                    'purchase': purchase_data,
                    'customer': customer_data,
                    'barnamehs': barnameh_data,
                    'allocations': allocation_data,
                    'state_history': state_history,
                    'sales_agents': sales_agents_data,
                    'unique_sales_agent': unique_sales_agent_data,
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'فرمت JSON نامعتبر است'
            }, status=400)
            
        except Exception as e:
            logger.error(f"خطا در API اطلاعات خرید: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'خطای داخلی سرور'
            }, status=500)


class CargoProductsAPI(View):
    """API برای دریافت لیست محصولات فعال CargoProduct با جزئیات کامل"""

    def get(self, request):
        try:
            product_type = request.GET.get('type')  # اختیاری: فیلتر بر اساس نوع خرید

            queryset = CargoProduct.objects.filter(status=True)
            if product_type:
                queryset = queryset.filter(type=product_type)

            # برای بهینه‌سازی، روابط را پیش‌بارگذاری می‌کنیم
            queryset = queryset.select_related('vared_konandeh', 'barbary')

            products = []
            for cargo in queryset:
                products.append({
                    # فیلدهای اصلی
                    'id': cargo.id,
                    'type': cargo.type,
                    'cottage': cargo.cottage,
                    'product_type': cargo.product_type,
                    'product_type_display': cargo.get_product_type_display(),
                    'country': cargo.country,
                    'country_display': cargo.get_country_display(),
                    'port': cargo.port,
                    'loading_time': cargo.loading_time,
                    'description': cargo.description,
                    'status': cargo.status,
                    'weight': cargo.weight,
                    'customer_price': cargo.customer_price,
                    'company_price': cargo.company_price,
                    'created_at': cargo.created_at.isoformat() if cargo.created_at else None,
                    'last_modified': cargo.last_modified.isoformat() if cargo.last_modified else None,

                    # اطلاعات باربری
                    'barbary': {
                        'id': cargo.barbary.id if cargo.barbary else None,
                        'name': cargo.barbary.name if cargo.barbary else None,
                        'phone_number': cargo.barbary.phone_number if cargo.barbary else None,
                        'email': cargo.barbary.email if cargo.barbary else None,
                        'description': cargo.barbary.description if cargo.barbary else None,
                    } if cargo.barbary else None,

                    # اطلاعات واردکننده
                    'vared_konandeh': {
                        'id': cargo.vared_konandeh.id if cargo.vared_konandeh else None,
                        'name': cargo.vared_konandeh.name if cargo.vared_konandeh else None,
                        'phone_number': cargo.vared_konandeh.phone_number if cargo.vared_konandeh else None,
                        'email': cargo.vared_konandeh.email if cargo.vared_konandeh else None,
                        'website': cargo.vared_konandeh.website if cargo.vared_konandeh else None,
                    } if cargo.vared_konandeh else None,
                })

            return JsonResponse({
                'success': True,
                'count': len(products),
                'products': products
            })

        except Exception as e:
            logger.error(f"خطا در API لیست محصولات: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'خطای داخلی سرور'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class CustomerPurchasesAPI(View):
    """API برای دریافت لیست خریدهای یک مشتری بر اساس شماره تلفن"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
            
            if not phone_number:
                return JsonResponse({
                    'success': False,
                    'error': 'شماره تلفن الزامی است'
                }, status=400)
            
            # تمیز کردن شماره تلفن
            clean_phone = clean_phone_number(phone_number)
            if not clean_phone:
                return JsonResponse({
                    'success': False,
                    'error': 'شماره تلفن نامعتبر است'
                }, status=400)
            
            # مجموعه‌ای برای نگهداری ID های خریدهای یکتا
            purchase_ids = set()
            customers_found = []
            
            # 1. جستجو در CrmAccessNumbers - همه مشتریانی که این شماره دسترسی دارند
            # ایجاد variations مختلف شماره برای جستجو
            phone_variations = [
                clean_phone,
                f"0{clean_phone}",
                f"98{clean_phone}"
            ]
            
            crm_access_query = Q(customer__isnull=False)
            phone_query = Q()
            for phone_var in phone_variations:
                phone_query |= Q(phone_number=phone_var)
            
            crm_accesses = CrmAccessNumbers.objects.filter(crm_access_query & phone_query)
            
            for crm_access in crm_accesses:
                customer = crm_access.customer
                customers_found.append({
                    'customer': customer,
                    'access_type': 'CRM Access'
                })
                
                # همه خریدهای این مشتری (هم customer و هم bazaargah_customer)
                customer_purchases = Purchase.objects.filter(
                    models.Q(customer=customer) | models.Q(bazaargah_customer=customer)
                )
                
                for purchase in customer_purchases:
                    purchase_ids.add(purchase.id)
            
            # 2. جستجو در bazaargah_phone_number با فرمت‌های مختلف
            
            # جستجو در bazaargah_phone_number
            bazaargah_query = Q()
            for phone_var in phone_variations:
                bazaargah_query |= Q(bazaargah_phone_number=phone_var)
            
            bazaargah_purchases = Purchase.objects.filter(bazaargah_query)
            for purchase in bazaargah_purchases:
                purchase_ids.add(purchase.id)
                # اضافه کردن اطلاعات مشتری اگر قبلاً نیافته
                if purchase.customer and not any(cf['customer'].id == purchase.customer.id for cf in customers_found):
                    customers_found.append({
                        'customer': purchase.customer,
                        'access_type': 'Bazaargah Phone'
                    })
                if purchase.bazaargah_customer and not any(cf['customer'].id == purchase.bazaargah_customer.id for cf in customers_found):
                    customers_found.append({
                        'customer': purchase.bazaargah_customer,
                        'access_type': 'Bazaargah Phone'
                    })
            
            # 3. جستجو در tahvil_phone_number
            tahvil_query = Q()
            for phone_var in phone_variations:
                tahvil_query |= Q(tahvil_phone_number=phone_var)
                
            tahvil_purchases = Purchase.objects.filter(tahvil_query)
            for purchase in tahvil_purchases:
                purchase_ids.add(purchase.id)
                # اضافه کردن اطلاعات مشتری اگر قبلاً نیافته
                if purchase.customer and not any(cf['customer'].id == purchase.customer.id for cf in customers_found):
                    customers_found.append({
                        'customer': purchase.customer,
                        'access_type': 'Tahvil Phone'
                    })
                if purchase.bazaargah_customer and not any(cf['customer'].id == purchase.bazaargah_customer.id for cf in customers_found):
                    customers_found.append({
                        'customer': purchase.bazaargah_customer,
                        'access_type': 'Tahvil Phone'
                    })
            
            # اگر هیچ خریدی یافت نشد
            if not purchase_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'هیچ خریدی برای این شماره تلفن یافت نشد'
                }, status=404)
            
            # دریافت خریدهای یکتا
            purchases = Purchase.objects.filter(
                id__in=purchase_ids
            ).select_related('cargo', 'customer', 'bazaargah_customer', 'unique_sales_agent').order_by('-created_at')
            
            purchases_data = []
            for purchase in purchases:
                # تشخیص نوع دسترسی برای این خرید
                access_types = []
                
                # بررسی آیا از طریق CrmAccessNumbers دسترسی دارد
                if any(crm.customer and (purchase.customer == crm.customer or purchase.bazaargah_customer == crm.customer) 
                       for crm in crm_accesses):
                    access_types.append('CRM Access')
                
                # بررسی آیا از طریق bazaargah_phone_number دسترسی دارد
                if purchase.bazaargah_phone_number and clean_phone_number(purchase.bazaargah_phone_number) == clean_phone:
                    access_types.append('Bazaargah Phone')
                
                # بررسی آیا از طریق tahvil_phone_number دسترسی دارد
                if purchase.tahvil_phone_number and clean_phone_number(purchase.tahvil_phone_number) == clean_phone:
                    access_types.append('Tahvil Phone')
                
                # اطلاعات خرید - بهبود یافته
                purchase_info = {
                    'purchase_number': purchase.purchase_number,
                    'invoice_id': purchase.invoice_id,
                    'tracking_number': purchase.tracking_number,
                    'shenase_takhsis': purchase.shenase_takhsis,
                    'state': purchase.state,
                    'state_display': purchase.get_state_display(),
                    'priority': purchase.priority,
                    'priority_display': purchase.get_priority_display(),
                    'is_urgent': purchase.is_urgent,
                    'is_canceled': purchase.is_canceled,
                    'is_archived': purchase.is_archived,
                    'order_weight': purchase.order_weight,
                    'delivered_weight': purchase.delivered_weight,
                    'total_weight': purchase.total_weight,
                    'customer_price': purchase.customer_price,
                    'amount_paid': purchase.amount_paid,
                    'payment_method': purchase.payment_method,
                    'is_fully_tasvied': purchase.is_fully_tasvied,
                    'is_factored': purchase.is_factored,
                    'factor_status': purchase.factor_status,
                    'buyer_name': purchase.buyer_name,
                    'address': purchase.address,
                    'delivery_address': purchase.delivery_address,
                    'barbary_confidential_number': purchase.barbary_confidential_number,
                    'barbary_customer_number': purchase.barbary_customer_number,
                    'created_at': purchase.created_at.isoformat() if purchase.created_at else None,
                    'updated_at': purchase.updated_at.isoformat() if purchase.updated_at else None,
                    'type': purchase.type,
                    'access_types': access_types,
                    
                    # اطلاعات اختلاف
                    'extelaf_type': purchase.extelaf_type,
                    'extelaf_weight': purchase.extelaf_weight,
                    'extelaf_amount': purchase.extelaf_amount,
                    
                    # اطلاعات محصول
                    'cargo_cottage': purchase.cargo.cottage if purchase.cargo else None,
                    'cargo_product_type': purchase.cargo.get_product_type_display() if purchase.cargo else None,
                    'cargo_country': purchase.cargo.get_country_display() if purchase.cargo else None,
                    'cargo_port': purchase.cargo.port if purchase.cargo else None,
                    'cargo_barbary_name': purchase.cargo.barbary.name if (purchase.cargo and purchase.cargo.barbary) else None,
                    'cargo_vared_konandeh_name': purchase.cargo.vared_konandeh.name if (purchase.cargo and purchase.cargo.vared_konandeh) else None,
                    
                    # اطلاعات مشتری
                    'customer_name': purchase.customer.name if purchase.customer else None,
                    'customer_city': purchase.customer.city if purchase.customer else None,
                    'bazaargah_customer_name': purchase.bazaargah_customer.name if purchase.bazaargah_customer else None,
                    'bazaargah_customer_city': purchase.bazaargah_customer.city if purchase.bazaargah_customer else None,
                    
                    # اطلاعات کارشناس فروش
                    'unique_sales_agent_name': purchase.unique_sales_agent.name if purchase.unique_sales_agent else None,
                    'unique_sales_agent_phone': purchase.unique_sales_agent.phone_number if purchase.unique_sales_agent else None,
                    
                    # تعداد بارنامه‌ها
                    'barnamehs_count': Barnameh.objects.filter(purchase_number=purchase.purchase_number).count(),
                    
                    # شناسه‌های تخصیص
                    'allocation_codes': [allocation.code for allocation in purchase.shenase_takhsis_set.all()],
                }
                
                purchases_data.append(purchase_info)
            
            # تهیه اطلاعات خلاصه مشتریان - بهبود یافته
            customers_summary = []
            for customer_info in customers_found:
                customer = customer_info['customer']
                customers_summary.append({
                    'id': customer.id,
                    'name': customer.name,
                    'city': customer.city,
                    'phone_number': customer.get_primary_phone(),
                    'all_phone_numbers': customer.get_all_phone_numbers(purchase, True),
                    'field_of_activity': customer.get_field_of_activity_display(),
                    'whatsapp_preference': customer.whatsapp_preference,
                    'sms_preference': customer.sms_preference,
                    'is_active': customer.is_active,
                    'is_blocked': customer.is_blocked,
                    'is_favorite': customer.is_favorite,
                    'access_type': customer_info['access_type'],
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'phone_number': clean_phone,
                    'customers': customers_summary,
                    'purchases': purchases_data,
                    'total_purchases': len(purchases_data),
                    'summary': {
                        'total_customers_found': len(customers_found),
                        'crm_access_count': len(crm_accesses),
                        'bazaargah_phone_count': len(bazaargah_purchases),
                        'tahvil_phone_count': len(tahvil_purchases),
                    }
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'فرمت JSON نامعتبر است'
            }, status=400)
            
        except Exception as e:
            logger.error(f"خطا در API لیست خریدها: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'خطای داخلی سرور'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class PhoneValidationAPI(View):
    """API برای احراز هویت شماره تلفن و بررسی اجازه دسترسی به CRM"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number')
            
            if not phone_number:
                return JsonResponse({
                    'success': False,
                    'error': 'شماره تلفن الزامی است'
                }, status=400)
            
            # تمیز کردن شماره تلفن
            clean_phone = clean_phone_number(phone_number)
            if not clean_phone:
                return JsonResponse({
                    'success': False,
                    'error': 'شماره تلفن نامعتبر است'
                }, status=400)
            
            has_access = False
            access_methods = []
            customers_info = []
            
            # 1. بررسی دسترسی از طریق CrmAccessNumbers
            # ایجاد variations مختلف شماره برای جستجو
            phone_variations = [
                clean_phone,
                f"0{clean_phone}",
                f"98{clean_phone}"
            ]
            
            crm_access_query = Q()
            for phone_var in phone_variations:
                crm_access_query |= Q(phone_number=phone_var)
            
            crm_accesses = CrmAccessNumbers.objects.filter(crm_access_query)
            
            if crm_accesses.exists():
                has_access = True
                access_methods.append('CRM Access')
                for crm_access in crm_accesses:
                    customer = crm_access.customer
                    customers_info.append({
                        'id': customer.id,
                        'name': customer.name,
                        'city': customer.city,
                        'phone_number': customer.get_primary_phone(),
                        'all_phone_numbers': customer.get_all_phone_numbers(),
                        'field_of_activity': customer.get_field_of_activity_display(),
                        'whatsapp_preference': customer.whatsapp_preference,
                        'sms_preference': customer.sms_preference,
                        'is_active': customer.is_active,
                        'is_blocked': customer.is_blocked,
                        'is_favorite': customer.is_favorite,
                        'access_type': 'CRM Access',
                        'created_at': customer.created_at.isoformat() if customer.created_at else None,
                    })
            
            # 2. بررسی وجود خرید با bazaargah_phone_number
            
            bazaargah_query = Q()
            for phone_var in phone_variations:
                bazaargah_query |= Q(bazaargah_phone_number=phone_var)
                
            bazaargah_purchases_count = Purchase.objects.filter(bazaargah_query).count()
            
            if bazaargah_purchases_count > 0:
                has_access = True
                access_methods.append('Bazaargah Phone')
            
            # 3. بررسی وجود خرید با tahvil_phone_number
            tahvil_query = Q()
            for phone_var in phone_variations:
                tahvil_query |= Q(tahvil_phone_number=phone_var)
                
            tahvil_purchases_count = Purchase.objects.filter(tahvil_query).count()
            
            if tahvil_purchases_count > 0:
                has_access = True
                access_methods.append('Tahvil Phone')
            
            # 4. بررسی در PhoneNumber model (برای مشتریان که شماره‌شان در سیستم ثبت است)
            phone_records = PhoneNumber.objects.filter(number=clean_phone)
            if phone_records.exists():
                has_access = True
                access_methods.append('Customer Phone')
                for phone_record in phone_records:
                    customer = phone_record.customer
                    if not any(c['id'] == customer.id for c in customers_info):
                        customers_info.append({
                            'id': customer.id,
                            'name': customer.name,
                            'city': customer.city,
                            'phone_number': customer.get_primary_phone(),
                            'all_phone_numbers': customer.get_all_phone_numbers(),
                            'field_of_activity': customer.get_field_of_activity_display(),
                            'whatsapp_preference': customer.whatsapp_preference,
                            'sms_preference': customer.sms_preference,
                            'is_active': customer.is_active,
                            'is_blocked': customer.is_blocked,
                            'is_favorite': customer.is_favorite,
                            'access_type': 'Customer Phone',
                            'created_at': customer.created_at.isoformat() if customer.created_at else None,
                        })
            
            # 5. بررسی در فیلد phone_number قدیمی Customer
            customers_old_phone = Customer.objects.filter(phone_number=clean_phone)
            if customers_old_phone.exists():
                has_access = True
                access_methods.append('Legacy Phone')
                for customer in customers_old_phone:
                    if not any(c['id'] == customer.id for c in customers_info):
                        customers_info.append({
                            'id': customer.id,
                            'name': customer.name,
                            'city': customer.city,
                            'phone_number': customer.get_primary_phone(),
                            'all_phone_numbers': customer.get_all_phone_numbers(),
                            'field_of_activity': customer.get_field_of_activity_display(),
                            'whatsapp_preference': customer.whatsapp_preference,
                            'sms_preference': customer.sms_preference,
                            'is_active': customer.is_active,
                            'is_blocked': customer.is_blocked,
                            'is_favorite': customer.is_favorite,
                            'access_type': 'Legacy Phone',
                            'created_at': customer.created_at.isoformat() if customer.created_at else None,
                        })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'phone_number': clean_phone,
                    'has_access': has_access,
                    'access_methods': access_methods,
                    'customers': customers_info,
                    'statistics': {
                        'crm_access_count': len(crm_accesses),
                        'bazaargah_purchases_count': bazaargah_purchases_count,
                        'tahvil_purchases_count': tahvil_purchases_count,
                        'phone_records_count': len(phone_records),
                        'legacy_customers_count': len(customers_old_phone),
                    }
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'فرمت JSON نامعتبر است'
            }, status=400)
            
        except Exception as e:
            logger.error(f"خطا در API احراز هویت: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'خطای داخلی سرور'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class HealthCheckAPI(View):
    """API برای بررسی وضعیت سلامت سرویس"""
    
    def get(self, request):
        try:
            # بررسی اتصال به دیتابیس
            customers_count = Customer.objects.count()
            purchases_count = Purchase.objects.count()
            crm_access_count = CrmAccessNumbers.objects.count()
            barnamehs_count = Barnameh.objects.count()
            
            return JsonResponse({
                'success': True,
                'status': 'healthy',
                'message': 'سرویس CRM API به درستی کار می‌کند',
                'statistics': {
                    'customers_count': customers_count,
                    'purchases_count': purchases_count,
                    'crm_access_count': crm_access_count,
                    'barnamehs_count': barnamehs_count,
                },
                'version': '2.0',
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"خطا در بررسی سلامت سرویس: {str(e)}")
            return JsonResponse({
                'success': False,
                'status': 'unhealthy',
                'error': 'خطا در اتصال به دیتابیس',
                'timestamp': timezone.now().isoformat()
            }, status=500)
    
    def post(self, request):
        # همان response برای POST requests
        return self.get(request)