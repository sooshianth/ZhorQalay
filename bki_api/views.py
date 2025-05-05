import os
import requests
import json
import xmltodict
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from dotenv import load_dotenv
from .models import BKILog
from django.conf import settings
from core.PurchaseModel import Purchase
from datetime import datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from core.decorators.decorators import role_required
from .bki_api_utils import bulk_update_purchase_info, get_purchase_info

@role_required('admin')
def update_env_file(key, value):
    """Update a specific key in the .env file."""
    env_path = os.path.join(settings.BASE_DIR, '.env')
    
    # Read the existing .env file
    with open(env_path, 'r') as file:
        lines = file.readlines()
    
    # Update the specified key
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break
    
    # If the key doesn't exist, add it
    if not updated:
        lines.append(f"{key}={value}\n")
    
    # Write the updated content back to the .env file
    with open(env_path, 'w') as file:
        file.writelines(lines)
    
    # Reload environment variables
    load_dotenv()

@role_required('admin')
def credentials_view(request):
    """View for managing BKI API credentials."""
    # Get current credentials from environment variables
    current_username = os.environ.get('BKI_USERNAME', '')
    current_password = os.environ.get('BKI_PASSWORD', '')
    
    context = {
        'current_username': current_username,
        'current_password': current_password,
    }
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Update .env file with new credentials
        if username:
            update_env_file('BKI_USERNAME', username)
        if password:
            update_env_file('BKI_PASSWORD', password)
        
        messages.success(request, 'تنظیمات BKI با موفقیت به‌روزرسانی شد.')
        return redirect('bki_api:credentials')
    
    return render(request, 'bki_api/credentials_form.html', context)

@role_required('admin')
def test_kharid_info(request):
    """View for testing getKharidInfo API."""
    if request.method != 'POST':
        return redirect('bki_api:credentials')
    
    kharid_id = request.POST.get('kharid_id')
    if not kharid_id:
        messages.error(request, 'لطفاً شناسه خرید را وارد کنید.')
        return redirect('bki_api:credentials')
    
    # Get credentials from environment variables
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است.')
        return redirect('bki_api:credentials')
    
    # Call the utility function to get purchase info
    purchase, created, error = get_purchase_info(kharid_id, create_if_not_exists=False)
    
    context = {
        'kharid_id': kharid_id,
        'success': purchase is not None,
        'error_message': error,
        'purchase': purchase,
        'created': created
    }
    
    return render(request, 'bki_api/test_result.html', context)


@role_required('admin')
@csrf_exempt
def update_purchase_info(request):
    """
    تابع برای دریافت اطلاعات خرید از سرویس BKI و به‌روزرسانی دیتابیس محلی
    """
    # دریافت شناسه خرید و اطلاعات معتبرسازی
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        return JsonResponse({'error': 'اطلاعات کاربری BKI تنظیم نشده است.'}, status=400)
    
    if request.method == 'POST':
        try:
            # دریافت شناسه خرید از درخواست
            data = json.loads(request.body)
            kharid_id = data.get('kharid_id')
            
            if not kharid_id:
                return JsonResponse({'error': 'شناسه خرید الزامی است.'}, status=400)
        except json.JSONDecodeError:
            # اگر JSON نبود، ممکن است فرم POST باشد
            kharid_id = request.POST.get('kharid_id')
            if not kharid_id:
                return JsonResponse({'error': 'شناسه خرید الزامی است.'}, status=400)
    else:
        # درخواست GET را هم پشتیبانی می‌کنیم
        kharid_id = request.GET.get('kharid_id')
        if not kharid_id:
            return JsonResponse({'error': 'شناسه خرید الزامی است.'}, status=400)
    
    # آماده‌سازی درخواست SOAP
    soap_url = "http://spsws.bki.ir/spsws.asmx"
    headers = {
        'Content-Type': 'application/soap+xml; charset=utf-8',
        'SOAPAction': 'http://tempuri.org/getKharidInfo'
    }
    
    soap_request = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <soap:Body>
            <getKharidInfo xmlns="http://tempuri.org/">
                <userName>{username}</userName>
                <pass>{password}</pass>
                <kharidId>{kharid_id}</kharidId>
            </getKharidInfo>
        </soap:Body>
    </soap:Envelope>"""
    
    # ثبت لاگ درخواست
    log_entry = BKILog(
        request_type='update_purchase_info',
        request_data=soap_request
    )
    
    try:
        # ارسال درخواست SOAP به سرویس BKI
        response = requests.post(soap_url, data=soap_request, headers=headers)
        log_entry.response_data = response.text
        
        # بررسی وضعیت پاسخ
        if response.status_code != 200:
            log_entry.is_successful = False
            log_entry.error_message = f"HTTP Error: {response.status_code}"
            log_entry.save()
            return JsonResponse({
                'success': False,
                'error': f'خطای HTTP: {response.status_code}',
                'response': response.text
            }, status=response.status_code)
        
        # تبدیل پاسخ XML به dictionary
        response_dict = xmltodict.parse(response.text)
        
        # استخراج داده‌ها از پاسخ
        try:
            # بررسی ساختار پاسخ و استخراج نتیجه
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidInfoResponse']['getKharidInfoResult']
            
            # نمایش داده‌های خام برای اشکال‌زدایی
            raw_data = json.dumps(result, indent=2, ensure_ascii=False)
            
            # بررسی ساختار پاسخ
            if not isinstance(result, dict):
                log_entry.is_successful = False
                log_entry.error_message = 'ساختار پاسخ نامعتبر است'
                log_entry.save()
                return JsonResponse({
                    'success': False, 
                    'error': 'ساختار پاسخ نامعتبر است',
                    'raw_response': raw_data
                }, status=400)
            
            # بررسی خطا در پاسخ
            if '#text' in result:
                log_entry.is_successful = False
                log_entry.error_message = result.get('#text', 'پاسخ نامعتبر')
                log_entry.save()
                return JsonResponse({
                    'success': False,
                    'error': result.get('#text', 'خطای پردازش پاسخ'),
                    'raw_response': raw_data
                }, status=400)
            
            # نگاشت فیلدهای XML به فیلدهای دیتابیس
            field_mappings = {
                'kharididentity': 'purchase_number',
                'kutajnumber': 'cargo__cottage',
                'goodtitle': 'cargo__product_type',
                'weight': 'delivered_weight',
                'buydate': 'created_at',
                'rrn': 'tracking_number',
                'buyername': 'customer__name',
                'buyeraddress': 'address',
                'delphone': 'tahvil_phone_number',
                'totalamount': 'amount_paid',
                'paymenttype': 'payment_method',
                'fi': 'customer_price',
                'buyermobile': 'customer__phone_number',
                'buyermellicode': 'code_melli_tahvil',
                'ostanname': 'customer__city',
            }
            
            # استخراج مقادیر از پاسخ
            purchase_data = {}
            for xml_field, db_field in field_mappings.items():
                if xml_field in result:
                    purchase_data[db_field] = result[xml_field]
            
            # بررسی وجود شماره خرید در پاسخ
            purchase_number = purchase_data.get('purchase_number')
            if not purchase_number:
                log_entry.is_successful = False
                log_entry.error_message = 'شماره خرید در پاسخ یافت نشد'
                log_entry.save()
                return JsonResponse({
                    'success': False, 
                    'error': 'شماره خرید در پاسخ سرویس BKI یافت نشد',
                    'raw_response': raw_data
                }, status=400)
            
            # جستجوی خرید در دیتابیس
            try:
                purchase = Purchase.objects.get(purchase_number=purchase_number)
                log_entry.purchase = purchase
                
                # به‌روزرسانی فیلدهای ساده
                simple_fields = [
                    'delivered_weight', 'tracking_number', 'address', 
                    'tahvil_phone_number', 'amount_paid', 'payment_method', 
                    'customer_price', 'code_melli_tahvil'
                ]
                
                updated_fields = []
                for field in simple_fields:
                    if field in purchase_data and purchase_data[field]:
                        # ذخیره مقدار قبلی برای نمایش تغییرات
                        old_value = getattr(purchase, field)
                        new_value = purchase_data[field]
                        
                        # اعمال تغییر
                        setattr(purchase, field, new_value)
                        
                        # ثبت تغییر
                        if str(old_value) != str(new_value):
                            updated_fields.append({
                                'field': field,
                                'old_value': old_value,
                                'new_value': new_value
                            })
                
                # به‌روزرسانی فیلدهای مشتری
                customer_updates = {}
                
                if 'customer__name' in purchase_data and purchase_data['customer__name']:
                    old_name = purchase.customer.name
                    new_name = purchase_data['customer__name']
                    if old_name != new_name:
                        purchase.customer.name = new_name
                        customer_updates['name'] = {'old': old_name, 'new': new_name}
                
                if 'customer__city' in purchase_data and purchase_data['customer__city']:
                    old_city = purchase.customer.city
                    new_city = purchase_data['customer__city']
                    if old_city != new_city:
                        purchase.customer.city = new_city
                        customer_updates['city'] = {'old': old_city, 'new': new_city}
                
                if 'customer__phone_number' in purchase_data and purchase_data['customer__phone_number']:
                    primary_phone = purchase.customer.get_primary_phone()
                    new_phone = purchase_data['customer__phone_number']
                    
                    if primary_phone != new_phone:
                        # آپدیت شماره تلفن اصلی
                        phone = purchase.customer.phone_numbers.filter(is_primary=True).first()
                        if phone:
                            old_phone = phone.number
                            phone.number = new_phone
                            phone.save()
                            customer_updates['phone'] = {'old': old_phone, 'new': new_phone}
                        else:
                            # ایجاد شماره تلفن جدید
                            from core.CustomerModel import PhoneNumber
                            PhoneNumber.objects.create(
                                customer=purchase.customer,
                                number=new_phone,
                                is_primary=True
                            )
                            customer_updates['phone'] = {'old': None, 'new': new_phone}
                
                # ذخیره تغییرات مشتری
                if customer_updates:
                    purchase.customer.save()
                
                # به‌روزرسانی تاریخ آخرین تغییر
                purchase.updated_at = timezone.now()
                
                # ذخیره تغییرات خرید
                purchase.save()
                
                # ثبت موفقیت در لاگ
                log_entry.is_successful = True
                log_entry.save()
                
                # پاسخ موفقیت‌آمیز
                return JsonResponse({
                    'success': True, 
                    'message': f'اطلاعات خرید {purchase_number} با موفقیت به‌روزرسانی شد',
                    'purchase_updates': updated_fields,
                    'customer_updates': customer_updates,
                    'is_new': False,
                    'raw_response': raw_data
                })
                
            except Purchase.DoesNotExist:
                # خرید یافت نشد - ایجاد خرید جدید
                created_objects = {}
                
                # 1. ایجاد یا یافتن مشتری
                mobile_number = purchase_data.get('customer__phone_number')
                if not mobile_number:
                    log_entry.is_successful = False
                    log_entry.error_message = 'شماره موبایل مشتری در پاسخ یافت نشد'
                    log_entry.save()
                    return JsonResponse({
                        'success': False,
                        'error': 'شماره موبایل مشتری در پاسخ سرویس BKI یافت نشد',
                        'raw_response': raw_data
                    }, status=400)
                
                # بررسی وجود مشتری با این شماره موبایل
                from core.CustomerModel import Customer, PhoneNumber
                customer = Customer.get_customer_by_phone(mobile_number)
                
                if customer:
                    # مشتری وجود دارد - به‌روزرسانی اطلاعات
                    created_objects['customer'] = {'status': 'found', 'id': customer.id}
                    
                    if 'customer__name' in purchase_data and purchase_data['customer__name']:
                        customer.name = purchase_data['customer__name']
                    
                    if 'customer__city' in purchase_data and purchase_data['customer__city']:
                        customer.city = purchase_data['customer__city']
                    
                    # ذخیره تغییرات مشتری
                    customer.save()
                else:
                    # ایجاد مشتری جدید
                    customer = Customer.objects.create(
                        name=purchase_data.get('customer__name', 'مشتری جدید'),
                        city=purchase_data.get('customer__city'),
                    )
                    created_objects['customer'] = {'status': 'created', 'id': customer.id}
                    
                    # ایجاد شماره تلفن اصلی
                    PhoneNumber.objects.create(
                        customer=customer,
                        number=mobile_number,
                        is_primary=True
                    )
                
                # 2. ایجاد یا یافتن محصول
                cottage_number = purchase_data.get('cargo__cottage')
                if cottage_number:
                    from core.CargoProductModel import CargoProduct
                    
                    try:
                        # بررسی وجود محصول با این کوتاژ
                        cargo = CargoProduct.objects.get(cottage=cottage_number)
                        created_objects['cargo'] = {'status': 'found', 'id': cargo.id}
                    except CargoProduct.DoesNotExist:
                        # ایجاد محصول جدید
                        product_type = 'corn'  # مقدار پیش‌فرض
                        
                        # تلاش برای یافتن نوع محصول از روی goodtitle
                        if 'cargo__product_type' in purchase_data:
                            product_title = purchase_data['cargo__product_type']
                            if 'ذرت' in product_title:
                                product_type = 'corn'
                            elif 'جو' in product_title:
                                product_type = 'barley'
                            elif 'سویا' in product_title and 'کنجاله' in product_title:
                                product_type = 'soy_meal'
                            elif 'آفتابگردان' in product_title:
                                product_type = 'sunflower_meal'
                            elif 'کلزا' in product_title:
                                product_type = 'rapeseed_meal'
                            elif 'پنبه' in product_title:
                                product_type = 'cotton_seed'
                            elif 'یونجه' in product_title:
                                product_type = 'alfalfa'
                        
                        cargo = CargoProduct.objects.create(
                            type='bazaargah',
                            cottage=cottage_number,
                            company_price=purchase_data.get('fi', 0),
                            customer_price=purchase_data.get('fi', 0),
                            product_type=product_type,
                            country='iran',  # مقدار پیش‌فرض
                            port='امام خمینی',  # مقدار پیش‌فرض
                            weight=1000000  # مقدار پیش‌فرض - 1000 تن
                        )
                        created_objects['cargo'] = {'status': 'created', 'id': cargo.id}
                else:
                    cargo = None
                    created_objects['cargo'] = {'status': 'not_created', 'reason': 'cottage_number_missing'}
                
                # 3. ایجاد خرید جدید
                try:
                    new_purchase = Purchase.objects.create(
                        purchase_number=purchase_number,
                        customer=customer,
                        cargo=cargo,
                        address=purchase_data.get('address'),
                        delivered_weight=purchase_data.get('delivered_weight', 0),
                        tracking_number=purchase_data.get('rrn'),
                        tahvil_phone_number=purchase_data.get('delphone'),
                        amount_paid=purchase_data.get('totalamount', 0),
                        payment_method=purchase_data.get('paymenttype', 'نقدی'),
                        customer_price=purchase_data.get('fi', 0),
                        company_price=purchase_data.get('fi', 0),
                        code_melli_tahvil=purchase_data.get('buyermellicode'),
                        type='bazaargah',
                        state='PAYMENT_VERIFIED'
                    )
                    
                    # تنظیم تاریخ ایجاد براساس تاریخ خرید
                    if 'created_at' in purchase_data and purchase_data['created_at']:
                        try:
                            buy_date = datetime.strptime(purchase_data['created_at'], '%Y-%m-%d')
                            new_purchase.created_at = timezone.make_aware(buy_date)
                            new_purchase.save(update_fields=['created_at'])
                        except (ValueError, TypeError):
                            # خطا در تبدیل تاریخ، از تاریخ پیش‌فرض استفاده می‌شود
                            pass
                    
                    created_objects['purchase'] = {'status': 'created', 'id': new_purchase.id}
                    
                    # ثبت لاگ
                    log_entry.purchase = new_purchase
                    log_entry.is_successful = True
                    log_entry.save()
                    
                    return JsonResponse({
                        'success': True,
                        'message': f'خرید جدید با شماره {purchase_number} با موفقیت ایجاد شد',
                        'created_objects': created_objects,
                        'is_new': True,
                        'raw_response': raw_data
                    })
                    
                except Exception as e:
                    log_entry.is_successful = False
                    log_entry.error_message = f'خطا در ایجاد خرید جدید: {str(e)}'
                    log_entry.save()
                    
                    return JsonResponse({
                        'success': False,
                        'error': f'خطا در ایجاد خرید جدید: {str(e)}',
                        'created_objects': created_objects,
                        'raw_response': raw_data
                    }, status=500)
                
        except (KeyError, TypeError) as e:
            # خطا در پردازش پاسخ
            log_entry.is_successful = False
            log_entry.error_message = f'خطا در پردازش پاسخ: {str(e)}'
            log_entry.save()
            
            return JsonResponse({
                'success': False,
                'error': f'خطا در پردازش پاسخ: {str(e)}',
                'raw_response': response.text
            }, status=400)
    
    except Exception as e:
        # خطا در ارتباط با سرویس
        log_entry.is_successful = False
        log_entry.error_message = f'خطا در ارتباط با سرویس BKI: {str(e)}'
        log_entry.save()
        
        return JsonResponse({
            'success': False,
            'error': f'خطا در ارتباط با سرویس BKI: {str(e)}'
        }, status=500)

@role_required('admin')
def bulk_update_purchases(request):
    """View for bulk updating purchases from BKI API."""
    context = {
        'purchase_ids': '',
        'results': None
    }
    
    if request.method == 'POST':
        purchase_ids = request.POST.get('purchase_ids', '').strip()
        if not purchase_ids:
            messages.error(request, 'لطفاً حداقل یک شماره خرید وارد کنید.')
            return render(request, 'bki_api/bulk_update.html', context)
        
        # Save the purchase IDs in the context to show them again after processing
        context['purchase_ids'] = purchase_ids
        
        # Process the purchase IDs
        results = bulk_update_purchase_info(purchase_ids)
        context['results'] = results
        
        # Count successes and failures
        successes = sum(1 for r in results if r['success'])
        failures = len(results) - successes
        created = sum(1 for r in results if r['created'])
        updated = successes - created
        
        # Show summary messages
        if successes > 0:
            messages.success(
                request, 
                f'عملیات با موفقیت انجام شد. {successes} خرید با موفقیت به‌روزرسانی شد. '
                f'({created} خرید جدید ایجاد شد، {updated} خرید موجود به‌روزرسانی شد)'
            )
        
        if failures > 0:
            messages.warning(
                request, 
                f'{failures} خرید با خطا مواجه شد. جزئیات را در جدول نتایج ببینید.'
            )
    
    return render(request, 'bki_api/bulk_update.html', context)

