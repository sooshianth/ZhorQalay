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
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

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
            ).order_by('-created_at')
            
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
                    'customer_name': purchase.customer.name if purchase.customer else None,
                    'bazaargah_customer_name': purchase.bazaargah_customer.name if purchase.bazaargah_customer else None,
                    'access_types': access_types,  # نشان می‌دهد از کدام مسیر دسترسی پیدا شده
                })
            
            # تهیه اطلاعات خلاصه مشتریان
            customers_summary = []
            for customer_info in customers_found:
                customer = customer_info['customer']
                customers_summary.append({
                    'name': customer.name,
                    'city': customer.city,
                    'phone_number': customer.get_primary_phone(),
                    'access_type': customer_info['access_type']
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
                        'access_type': 'CRM Access'
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
                            'access_type': 'Customer Phone'
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
                            'access_type': 'Legacy Phone'
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
            
            return JsonResponse({
                'success': True,
                'status': 'healthy',
                'message': 'سرویس CRM API به درستی کار می‌کند',
                'statistics': {
                    'customers_count': customers_count,
                    'purchases_count': purchases_count,
                    'crm_access_count': crm_access_count,
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