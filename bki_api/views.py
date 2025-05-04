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
    
    # Prepare SOAP request
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
    
    context = {
        'kharid_id': kharid_id,
        'success': False
    }
    
    try:
        # Send SOAP request
        response = requests.post(soap_url, data=soap_request, headers=headers)
        
        # Save request/response to BKILog
        log_entry = BKILog(
            request_type='getKharidInfo',
            request_data=soap_request,
            response_data=response.text
        )
        
        # Convert XML response to dictionary
        response_dict = xmltodict.parse(response.text)
        
        # Check if response contains error
        if response.status_code != 200:
            log_entry.is_successful = False
            log_entry.error_message = f"HTTP Error: {response.status_code}"
            log_entry.save()
            
            context['error_message'] = f"خطای HTTP: {response.status_code}"
            context['response_data'] = response.text
            return render(request, 'bki_api/test_result.html', context)
        
        # Try to extract the result data
        try:
            # Parse the SOAP response to get the actual data
            soap_body = response_dict['soap:Envelope']['soap:Body']
            result = soap_body['getKharidInfoResponse']['getKharidInfoResult']
            
            # The actual data may be in a complex structure, extract as needed
            # This is a simplified example - you'll need to adapt based on actual response format
            if isinstance(result, dict) and 'schema' in result:
                # Successfully got data
                log_entry.is_successful = True
                log_entry.save()
                
                context['success'] = True
                context['response_data'] = json.dumps(result, indent=2, ensure_ascii=False)
                
                # Extract and parse useful data if possible
                # This is a placeholder - actual parsing depends on response structure
                try:
                    if '#text' in result:
                        parsed_data = {'message': result['#text']}
                    else:
                        parsed_data = {'status': 'Data received but requires custom parsing'}
                    
                    context['parsed_data'] = parsed_data
                except Exception as e:
                    context['parsed_data'] = {'parsing_error': str(e)}
                
                return render(request, 'bki_api/test_result.html', context)
            else:
                # Got response but no valid data
                error_msg = "پاسخ دریافت شد اما داده‌های معتبری یافت نشد"
                log_entry.is_successful = False
                log_entry.error_message = error_msg
                log_entry.save()
                
                context['error_message'] = error_msg
                context['response_data'] = json.dumps(response_dict, indent=2, ensure_ascii=False)
                return render(request, 'bki_api/test_result.html', context)
                
        except Exception as e:
            # Error parsing response
            log_entry.is_successful = False
            log_entry.error_message = str(e)
            log_entry.save()
            
            context['error_message'] = f"خطا در پردازش پاسخ: {str(e)}"
            context['response_data'] = response.text
            return render(request, 'bki_api/test_result.html', context)
    
    except Exception as e:
        # Error sending request
        error_message = f"خطا در برقراری ارتباط با سرویس: {str(e)}"
        
        # Create log entry for the error
        log_entry = BKILog(
            request_type='getKharidInfo',
            request_data=soap_request,
            is_successful=False,
            error_message=error_message
        )
        log_entry.save()
        
        context['error_message'] = error_message
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
    """
    نمایش فرم وارد کردن شماره خرید‌ها و به‌روزرسانی آنها به صورت دسته‌ای
    """
    # بررسی دسترسی به اطلاعات کاربری BKI
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است. ابتدا اطلاعات کاربری را تنظیم کنید.')
        return redirect('bki_api:credentials')
    
    results = []
    
    if request.method == 'POST':
        # دریافت شماره خرید‌ها از فرم
        purchase_ids_text = request.POST.get('purchase_ids', '')
        
        # جدا کردن شماره خرید‌ها (با فاصله، خط جدید یا کاما)
        purchase_ids = [pid.strip() for pid in purchase_ids_text.replace(',', ' ').replace('\n', ' ').split() if pid.strip()]
        
        if not purchase_ids:
            messages.error(request, 'لطفاً حداقل یک شماره خرید وارد کنید.')
            return render(request, 'bki_api/bulk_update.html')
        
        # پردازش هر شماره خرید
        for kharid_id in purchase_ids:
            # ساخت یک درخواست داخلی برای هر شماره خرید
            fake_request = type('obj', (object,), {
                'method': 'GET',
                'GET': {'kharid_id': kharid_id}
            })
            
            # فراخوانی تابع به‌روزرسانی
            response = update_purchase_info(fake_request)
            
            # استخراج نتیجه
            try:
                response_data = json.loads(response.content)
                
                # اضافه کردن شماره خرید به نتیجه
                response_data['kharid_id'] = kharid_id
                
                # اضافه کردن به لیست نتایج
                results.append(response_data)
            except:
                # در صورت خطا در پردازش پاسخ
                results.append({
                    'kharid_id': kharid_id,
                    'success': False,
                    'error': 'خطا در پردازش پاسخ',
                })
        
        # خلاصه نتایج
        success_count = sum(1 for r in results if r.get('success', False))
        
        if success_count > 0:
            messages.success(request, f'{success_count} خرید از {len(results)} خرید با موفقیت به‌روزرسانی شد.')
        else:
            messages.error(request, 'هیچ خریدی به‌روزرسانی نشد. لطفاً جزئیات خطا را بررسی کنید.')
        
        # نمایش فرم با نتایج
        return render(request, 'bki_api/bulk_update.html', {'results': results, 'purchase_ids': purchase_ids_text})
    
    # نمایش فرم خالی
    return render(request, 'bki_api/bulk_update.html') 