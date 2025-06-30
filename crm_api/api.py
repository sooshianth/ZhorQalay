from django.shortcuts import render
from core.PurchaseModel import Purchase, ShenaseTakhsis
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

logger = logging.getLogger(__name__)

def clean_phone_number(phone):
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
        crm_access = CrmAccessNumbers.objects.filter(
            phone_number=clean_phone,
            customer__isnull=False
        ).first()
        
        if crm_access:
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
            
            # تهیه اطلاعات خرید
            purchase_data = {
                'purchase_number': purchase.purchase_number,
                'invoice_id': purchase.invoice_id,
                'state': purchase.state,
                'state_display': purchase.get_state_display(),
                'order_weight': purchase.order_weight,
                'delivered_weight': purchase.delivered_weight,
                'customer_price': purchase.customer_price,
                'amount_paid': purchase.amount_paid,
                'payment_method': purchase.payment_method,
                'buyer_name': purchase.buyer_name,
                'address': purchase.address,
                'tracking_number': purchase.tracking_number,
                'created_at': purchase.created_at.isoformat() if purchase.created_at else None,
                'bazaargah_phone_number': purchase.bazaargah_phone_number,
                'tahvil_phone_number': purchase.tahvil_phone_number,
                'code_melli_tahvil': purchase.code_melli_tahvil,
                'extelaf_type': purchase.extelaf_type,
                'extelaf_weight': purchase.extelaf_weight,
                'extelaf_amount': purchase.extelaf_amount,
                'is_fully_tasvied': purchase.is_fully_tasvied,
                'is_factored': purchase.is_factored,
            }
            
            # اطلاعات محصول
            if purchase.cargo:
                purchase_data['cargo'] = {
                    'cottage': purchase.cargo.cottage,
                    'product_type': purchase.cargo.product_type,
                    'product_type_display': purchase.cargo.get_product_type_display(),
                    'country': purchase.cargo.country,
                    'country_display': purchase.cargo.get_country_display(),
                }
            
            # اطلاعات مشتری
            customer_data = {
                'name': customer.name,
                'city': customer.city,
                'phone_number': customer.get_primary_phone(),
                'field_of_activity': customer.get_field_of_activity_display(),
            }
            
            # اطلاعات بارنامه‌ها
            barnameh_data = []
            barnamehs = Barnameh.objects.filter(purchase_number=purchase_number)
            for barnameh in barnamehs:
                barnameh_data.append({
                    'number': barnameh.number,
                    'serial': barnameh.serial,
                    'shenase_takhsis_code': barnameh.shenase_takhsis_code,
                    'barnameh_date': barnameh.barnameh_date.isoformat() if barnameh.barnameh_date else None,
                    'is_sent_to_bki': barnameh.is_sent_to_bki,
                    'is_sent_to_bki_at': barnameh.is_sent_to_bki_at.isoformat() if barnameh.is_sent_to_bki_at else None,
                })
            
            # شناسه‌های تخصیص
            allocation_data = []
            for allocation in purchase.shenase_takhsis_set.all():
                allocation_data.append({
                    'code': allocation.code,
                    'weight': allocation.weight,
                })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'purchase': purchase_data,
                    'customer': customer_data,
                    'barnamehs': barnameh_data,
                    'allocations': allocation_data,
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

@method_decorator(csrf_exempt, name='dispatch')
class CustomerPurchasesAPI(View):
    """API برای دریافت لیست خریدهای یک مشتری"""
    
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
            
            # جستجو برای مشتری با روش‌های مختلف
            customer = None
            
            # راه اول: جستجو در CrmAccessNumbers
            crm_access = CrmAccessNumbers.objects.filter(
                phone_number=clean_phone,
                customer__isnull=False
            ).first()
            
            if crm_access:
                customer = crm_access.customer
            else:
                # راه دوم: جستجو مستقیم در PhoneNumber
                phone_record = PhoneNumber.objects.filter(number=clean_phone).first()
                if phone_record:
                    customer = phone_record.customer
                else:
                    # راه سوم: جستجو در فیلد phone_number قدیمی Customer
                    customer = Customer.objects.filter(phone_number=clean_phone).first()
            
            if not customer:
                return JsonResponse({
                    'success': False,
                    'error': 'شماره تلفن در سیستم یافت نشد'
                }, status=403)
            
            # دریافت خریدهای مشتری
            purchases = Purchase.objects.filter(
                models.Q(customer=customer) | models.Q(bazaargah_customer=customer)
            ).order_by('-created_at')
            
            purchases_data = []
            for purchase in purchases:
                purchases_data.append({
                    'purchase_number': purchase.purchase_number,
                    'invoice_id': purchase.invoice_id,
                    'state': purchase.state,
                    'state_display': purchase.get_state_display(),
                    'order_weight': purchase.order_weight,
                    'delivered_weight': purchase.delivered_weight,
                    'amount_paid': purchase.amount_paid,
                    'created_at': purchase.created_at.isoformat() if purchase.created_at else None,
                    'cargo_cottage': purchase.cargo.cottage if purchase.cargo else None,
                })
            
            return JsonResponse({
                'success': True,
                'data': {
                    'customer': {
                        'name': customer.name,
                        'city': customer.city,
                        'phone_number': customer.get_primary_phone(),
                    },
                    'purchases': purchases_data,
                    'total_purchases': len(purchases_data)
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