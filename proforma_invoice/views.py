from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent
from core.decorators.decorators import role_required
from major.models.NonBazargahProduct import NonBazargahProduct
from major.models.Product import Product
from .models import CompanyInfo, ProformaInvoice, ProformaInvoiceItem, ProformaInvoiceDelivery
import jdatetime
import tempfile
import os
import json
import logging

# لاگر اختصاصی برای پیش‌فاکتور
logger = logging.getLogger('proforma_invoice')


@role_required('sales_agent', 'admin', 'financial_manager')
@login_required
def proforma_step1_customer_info(request, customer_id):
    """مرحله 1: تایید اطلاعات مشتری"""
    customer = get_object_or_404(Customer, id=customer_id)
    company_info = CompanyInfo.get_active_company()
    
    logger.info(f"کاربر {request.user.username} وارد مرحله ۱ صدور پیش‌فاکتور برای مشتری {customer.name} (ID: {customer_id}) شد")
    
    # بررسی کامل بودن اطلاعات مشتری
    missing_fields = []
    if not customer.invoice_id_code:
        missing_fields.append('کد/شناسه ملی')
    if not customer.invoice_address:
        missing_fields.append('آدرس رسمی')
    if not customer.invoice_postal_code:
        missing_fields.append('کد پستی رسمی')
    if not customer.invoice_phone_number:
        missing_fields.append('شماره تلفن رسمی')
    
    if missing_fields:
        logger.warning(f"اطلاعات ناقص مشتری {customer.name} (ID: {customer_id}): {', '.join(missing_fields)}")
    
    # بررسی وجود اطلاعات شرکت
    if not company_info:
        logger.error(f"اطلاعات شرکت موجود نیست - کاربر {request.user.username}")
        messages.error(request, "لطفاً ابتدا اطلاعات شرکت را از پنل مدیریت تکمیل کنید.")
        return redirect(f"{reverse('general_customer_CRUD')}?customer_id={customer_id}")
    
    context = {
        'customer': customer,
        'company_info': company_info,
        'missing_fields': missing_fields,
        'step': 1,
    }
    
    return render(request, 'proforma_invoice/step1_customer_info.html', context)


@role_required('sales_agent', 'admin', 'financial_manager')
@login_required
def proforma_step2_product_selection(request, customer_id):
    """مرحله 2: انتخاب محصولات و مشخصات"""
    customer = get_object_or_404(Customer, id=customer_id)
    company_info = CompanyInfo.get_active_company()
    
    logger.info(f"کاربر {request.user.username} وارد مرحله ۲ (انتخاب محصولات) برای مشتری {customer.name} شد")
    
    # دریافت محصولات فعال (هم بازارگاه و هم خارج از بازارگاه)
    cargo_products = CargoProduct.get_active_products()
    non_bazargah_products = NonBazargahProduct.get_active_products()
    
    if request.method == 'POST':
        try:
            # دریافت آیتم‌های محصول از فرم (به صورت JSON)
            items_json = request.POST.get('items')
            notes = request.POST.get('notes', '')
            
            logger.debug(f"داده‌های دریافتی از فرم: items_json={items_json[:100] if items_json else 'None'}, notes={notes[:50] if notes else ''}")
            
            if not items_json:
                logger.warning(f"کاربر {request.user.username} سعی در ثبت پیش‌فاکتور بدون محصول کرد")
                messages.error(request, "لطفاً حداقل یک محصول اضافه کنید.")
                raise ValueError("No items provided")
            
            items_data = json.loads(items_json)
            
            if not items_data:
                logger.warning(f"لیست محصولات خالی برای کاربر {request.user.username}")
                messages.error(request, "لطفاً حداقل یک محصول اضافه کنید.")
                raise ValueError("No items in list")
            
            logger.info(f"تعداد محصولات دریافتی: {len(items_data)}")
            
            # دریافت کارشناس فروش
            sales_agent = None
            if hasattr(request.user, 'sales_agent'):
                sales_agent = request.user.sales_agent
            
            # ایجاد پیش فاکتور و آیتم‌ها در یک transaction
            with transaction.atomic():
                # ایجاد پیش فاکتور
                proforma = ProformaInvoice()
                proforma.customer = customer
                proforma.sales_agent = sales_agent
                proforma.company_info = company_info
                proforma.notes = notes
                proforma.save()
                
                logger.info(f"پیش‌فاکتور {proforma.invoice_number} ایجاد شد توسط {request.user.username}")
                
                # ایجاد آیتم‌های محصول
                for idx, item_data in enumerate(items_data):
                    item = ProformaInvoiceItem()
                    item.proforma = proforma
                    item.product_name = item_data.get('product_name', '')
                    item.product_description = item_data.get('product_description', '')
                    item.quantity = float(item_data.get('quantity', 0))
                    item.unit = item_data.get('unit', 'kg')
                    item.unit_price = float(item_data.get('unit_price', 0))
                    item.discount_percent = float(item_data.get('discount_percent', 0))
                    item.discount_amount = float(item_data.get('discount_amount', 0))
                    item.extra_amount = float(item_data.get('extra_amount', 0))
                    item.item_notes = item_data.get('item_notes', '')
                    item.order = idx
                    
                    # اگر محصول انتخاب شده، آن را ست کن
                    product_id = item_data.get('product_id')
                    product_type = item_data.get('product_type')
                    
                    if product_id and product_type:
                        try:
                            if product_type == 'cargo':
                                product = CargoProduct.objects.get(id=product_id)
                                item.product = product
                            elif product_type == 'non_bazargah':
                                product = NonBazargahProduct.objects.get(id=product_id)
                                item.product = product
                        except (CargoProduct.DoesNotExist, NonBazargahProduct.DoesNotExist):
                            logger.warning(f"محصول با ID {product_id} و نوع {product_type} یافت نشد")
                    
                    item.save()
                    logger.debug(f"آیتم '{item.product_name}' با مقدار {item.quantity} {item.unit} به پیش‌فاکتور اضافه شد")
                
                # محاسبه قیمت کل
                proforma.calculate_total()
                logger.info(f"پیش‌فاکتور {proforma.invoice_number} با مبلغ کل {proforma.total_price:,} ریال ثبت شد")
            
            messages.success(request, f"پیش‌فاکتور {proforma.invoice_number} با موفقیت ایجاد شد")
            # انتقال به مرحله نمایش
            return redirect('proforma_preview', proforma_id=proforma.id)
            
        except json.JSONDecodeError as e:
            logger.error(f"خطای JSON در ثبت پیش‌فاکتور توسط {request.user.username}: {str(e)}")
            messages.error(request, "خطا در پردازش اطلاعات محصولات.")
        except Exception as e:
            logger.error(f"خطای غیرمنتظره در ثبت پیش‌فاکتور توسط {request.user.username}: {str(e)}", exc_info=True)
            messages.error(request, f"خطا در ثبت اطلاعات: {str(e)}")
    
    context = {
        'customer': customer,
        'company_info': company_info,
        'cargo_products': cargo_products,
        'non_bazargah_products': non_bazargah_products,
        'step': 2,
    }
    
    return render(request, 'proforma_invoice/step2_product_selection.html', context)


@role_required('sales_agent', 'admin', 'financial_manager')
@login_required
def proforma_preview(request, proforma_id):
    """مرحله 3: پیش‌نمایش و تایید نهایی"""
    proforma = get_object_or_404(ProformaInvoice, id=proforma_id)
    
    logger.info(f"کاربر {request.user.username} وارد پیش‌نمایش پیش‌فاکتور {proforma.invoice_number} شد")
    
    # بررسی دسترسی
    if hasattr(request.user, 'sales_agent'):
        sales_agent = request.user.sales_agent
        if proforma.sales_agent != sales_agent and not request.user.is_superuser:
            logger.warning(f"کاربر {request.user.username} سعی در دسترسی به پیش‌فاکتور {proforma.invoice_number} بدون مجوز کرد")
            messages.error(request, "شما دسترسی به این پیش فاکتور ندارید.")
            return redirect('general_customer_CRUD')
    
    if request.method == 'POST':
        if 'finalize' in request.POST:
            proforma.is_finalized = True
            proforma.save()
            logger.info(f"پیش‌فاکتور {proforma.invoice_number} توسط {request.user.username} نهایی شد")
            messages.success(request, "پیش فاکتور با موفقیت نهایی شد.")
        elif 'edit' in request.POST:
            logger.info(f"کاربر {request.user.username} وارد حالت ویرایش پیش‌فاکتور {proforma.invoice_number} شد")
            return redirect('proforma_step2', customer_id=proforma.customer.id)
    
    context = {
        'proforma': proforma,
        'step': 3,
    }
    
    return render(request, 'proforma_invoice/preview.html', context)


@role_required('sales_agent', 'admin', 'financial_manager')
@login_required
def proforma_download_pdf(request, proforma_id):
    """دانلود پیش فاکتور به صورت PDF"""
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        logger.error(f"پکیج WeasyPrint نصب نیست - درخواست توسط {request.user.username}")
        messages.error(request, "خطا: پکیج WeasyPrint به درستی نصب نشده است. لطفاً با مدیر سیستم تماس بگیرید.")
        return redirect('proforma_preview', proforma_id=proforma_id)
    
    proforma = get_object_or_404(ProformaInvoice, id=proforma_id)
    
    logger.info(f"کاربر {request.user.username} درخواست دانلود PDF پیش‌فاکتور {proforma.invoice_number} کرد")
    
    # بررسی دسترسی
    if hasattr(request.user, 'sales_agent'):
        sales_agent = request.user.sales_agent
        if proforma.sales_agent != sales_agent and not request.user.is_superuser:
            logger.warning(f"کاربر {request.user.username} سعی در دانلود پیش‌فاکتور {proforma.invoice_number} بدون مجوز کرد")
            messages.error(request, "شما دسترسی به این پیش فاکتور ندارید.")
            return redirect('general_customer_CRUD')
    
    try:
        # رندر HTML
        html_string = render_to_string('proforma_invoice/pdf_template.html', {
            'proforma': proforma,
        })
        
        # تبدیل به PDF
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        
        # کانفیگ فونت برای فارسی
        font_config = FontConfiguration()
        
        # مسیر فایل فونت محلی
        from django.conf import settings
        import os
        font_dir = os.path.join(settings.BASE_DIR, 'core', 'static', 'vendor', 'vazir-font-30.1.0')
        
        # CSS برای فونت وزیر
        css = CSS(string=f'''
            @font-face {{
                font-family: 'Vazir';
                src: url('file://{font_dir}/Vazir-Regular.ttf') format('truetype');
                font-weight: normal;
                font-style: normal;
            }}
            @font-face {{
                font-family: 'Vazir';
                src: url('file://{font_dir}/Vazir-Bold.ttf') format('truetype');
                font-weight: bold;
                font-style: normal;
            }}
            body {{
                font-family: 'Vazir', sans-serif;
            }}
        ''', font_config=font_config)
        
        # تولید PDF
        pdf = html.write_pdf(stylesheets=[css], font_config=font_config)
        
        logger.info(f"PDF پیش‌فاکتور {proforma.invoice_number} با موفقیت تولید شد")
        
        # ارسال به عنوان پاسخ
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="proforma_{proforma.invoice_number}.pdf"'
        
        return response
    except Exception as e:
        logger.error(f"خطا در تولید PDF پیش‌فاکتور {proforma.invoice_number}: {str(e)}", exc_info=True)
        messages.error(request, "خطا در تولید PDF. لطفاً با مدیر سیستم تماس بگیرید.")
        return redirect('proforma_preview', proforma_id=proforma_id)


@role_required('sales_agent', 'admin', 'financial_manager')
@login_required
def proforma_list(request):
    """لیست تمام پیش فاکتورها"""
    logger.info(f"کاربر {request.user.username} وارد لیست پیش‌فاکتورها شد")
    
    if hasattr(request.user, 'sales_agent') and not request.user.is_superuser:
        sales_agent = request.user.sales_agent
        proformas = ProformaInvoice.objects.filter(sales_agent=sales_agent)
        logger.debug(f"نمایش {proformas.count()} پیش‌فاکتور برای کارشناس {sales_agent}")
    else:
        proformas = ProformaInvoice.objects.all()
        logger.debug(f"نمایش همه {proformas.count()} پیش‌فاکتور")
    
    context = {
        'proformas': proformas,
    }
    
    return render(request, 'proforma_invoice/list.html', context)


@role_required('admin', 'financial_manager')
@login_required
def financial_dashboard(request):
    """داشبورد مدیر مالی برای مدیریت پیش‌فاکتورها"""
    logger.info(f"کاربر {request.user.username} وارد داشبورد مالی پیش‌فاکتور شد")
    
    customer_id = request.GET.get('customer_id')
    customer = None
    company_info = CompanyInfo.get_active_company()
    
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            logger.info(f"مشتری {customer.name} (ID: {customer_id}) در داشبورد مالی انتخاب شد")
        except Customer.DoesNotExist:
            logger.warning(f"مشتری با ID {customer_id} یافت نشد")
            messages.error(request, "مشتری یافت نشد.")
    
    # بروزرسانی اطلاعات مشتری
    if request.method == 'POST' and customer:
        try:
            customer.invoice_id_code = request.POST.get('invoice_id_code', '')
            customer.invoice_address = request.POST.get('invoice_address', '')
            customer.invoice_postal_code = request.POST.get('invoice_postal_code', '')
            customer.invoice_phone_number = request.POST.get('invoice_phone_number', '')
            customer.eqtesadi_code = request.POST.get('eqtesadi_code', '')
            customer.sabt_number = request.POST.get('sabt_number', '')
            customer.yekta_code = request.POST.get('yekta_code', '')
            customer.haqiqi_hoquqi = request.POST.get('haqiqi_hoquqi', 'haqiqi')
            
            customer.save()
            logger.info(f"اطلاعات فاکتوری مشتری {customer.name} توسط {request.user.username} بروزرسانی شد")
            messages.success(request, f"اطلاعات فاکتوری {customer.name} با موفقیت ذخیره شد.")
            
            return redirect(f"{reverse('financial_dashboard')}?customer_id={customer.id}")
        except Exception as e:
            logger.error(f"خطا در بروزرسانی اطلاعات مشتری {customer.name}: {str(e)}", exc_info=True)
            messages.error(request, f"خطا در ذخیره اطلاعات: {str(e)}")
    
    # دریافت پیش‌فاکتورهای مشتری
    proformas = []
    if customer:
        proformas = ProformaInvoice.objects.filter(customer=customer).order_by('-created_at')
    
    context = {
        'customer': customer,
        'company_info': company_info,
        'proformas': proformas,
    }
    
    return render(request, 'proforma_invoice/financial_dashboard.html', context)


@role_required('admin', 'financial_manager', 'sales_agent')
@login_required
def customer_search_api(request):
    """API جستجوی مشتری برای autocomplete"""
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'customers': []})
    
    logger.debug(f"جستجوی مشتری با کوئری: {query}")
    
    try:
        # جستجوی بر اساس نام یا شماره تلفن
        customers = Customer.objects.filter(
            Q(name__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(phone_numbers__number__icontains=query) |
            Q(invoice_id_code__icontains=query)
        ).distinct()[:20]
        
        results = []
        for customer in customers:
            results.append({
                'id': customer.id,
                'name': customer.name or 'بدون نام',
                'phone': customer.get_primary_phone() or 'بدون شماره',
                'city': customer.city or '',
                'invoice_id_code': customer.invoice_id_code or '',
            })
        
        logger.debug(f"تعداد نتایج جستجو: {len(results)}")
        return JsonResponse({'customers': results})
    except Exception as e:
        logger.error(f"خطا در جستجوی مشتری: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'خطا در جستجو'}, status=500)


@role_required('sales_agent', 'admin', 'financial_manager')
@login_required
def send_sms_popup(request, proforma_id):
    """نمایش پاپ‌آپ برای انتخاب شماره‌های ارسال پیامک"""
    proforma = get_object_or_404(ProformaInvoice, id=proforma_id)
    
    logger.info(f"کاربر {request.user.username} وارد صفحه ارسال پیامک برای پیش‌فاکتور {proforma.invoice_number} شد")
    
    # بررسی دسترسی
    if hasattr(request.user, 'sales_agent'):
        sales_agent = request.user.sales_agent
        if proforma.sales_agent != sales_agent and not request.user.is_superuser:
            logger.warning(f"کاربر {request.user.username} سعی در دسترسی بدون مجوز کرد")
            messages.error(request, "شما دسترسی به این پیش فاکتور ندارید.")
            return redirect('general_customer_CRUD')
    
    # دریافت شماره‌های مشتری
    customer = proforma.customer
    phone_numbers = []
    
    # شماره‌های ثبت شده در PhoneNumber model
    for phone in customer.phone_numbers.all():
        phone_numbers.append({
            'number': phone.number,
            'description': phone.description or 'شماره ثبت شده',
            'is_primary': phone.is_primary,
            'sms_enabled': phone.sms_enabled,
        })
    
    # شماره تلفن رسمی
    if customer.invoice_phone_number:
        phone_numbers.append({
            'number': customer.invoice_phone_number,
            'description': 'شماره تلفن رسمی',
            'is_primary': False,
            'sms_enabled': True,
        })
    
    if request.method == 'POST':
        try:
            from .models import ProformaInvoiceDelivery
            
            # دریافت شماره‌های انتخاب شده
            selected_phones = request.POST.getlist('selected_phones[]')
            
            # دریافت شماره‌های دستی
            manual_phones = request.POST.get('manual_phones', '').strip()
            if manual_phones:
                # پردازش شماره‌های دستی (با کاما یا خط جدید جدا شده)
                import re
                manual_list = re.split(r'[,\n\r]+', manual_phones)
                for phone in manual_list:
                    phone = phone.strip()
                    if phone:
                        selected_phones.append(phone)
            
            if not selected_phones:
                messages.error(request, "لطفاً حداقل یک شماره تلفن انتخاب کنید.")
                return redirect('send_sms_popup', proforma_id=proforma_id)
            
            # ایجاد درخواست ارسال
            delivery = ProformaInvoiceDelivery()
            delivery.proforma = proforma
            delivery.phone_numbers = selected_phones
            delivery.sent_by = request.user
            delivery.status = 'pending'
            delivery.save()
            
            logger.info(f"درخواست ارسال پیش‌فاکتور {proforma.invoice_number} توسط {request.user.username} ثبت شد با {len(selected_phones)} شماره")
            
            messages.success(request, f"درخواست ارسال به {len(selected_phones)} شماره با موفقیت ثبت شد. پیش‌فاکتور به زودی برای مشتری ارسال خواهد شد.")
            return redirect('proforma_preview', proforma_id=proforma_id)
            
        except Exception as e:
            logger.error(f"خطا در ثبت درخواست ارسال: {str(e)}", exc_info=True)
            messages.error(request, f"خطا در ثبت درخواست: {str(e)}")
    
    context = {
        'proforma': proforma,
        'phone_numbers': phone_numbers,
    }
    
    return render(request, 'proforma_invoice/send_sms_popup.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def api_poll_pending_deliveries(request):
    """
    API endpoint برای KunQalay جهت دریافت پیش‌فاکتورهای در انتظار ارسال
    این endpoint هر 20 ثانیه توسط KunQalay فراخوانی می‌شود
    """
    # بررسی API Key
    api_key = request.headers.get('X-API-KEY')
    expected_key = getattr(settings, 'CRM_API_KEY', None)
    
    if not settings.DEBUG:
        if not api_key or not expected_key or api_key != expected_key:
            logger.warning(f"تلاش ناموفق برای دسترسی به API: {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        from .models import ProformaInvoiceDelivery
        
        # دریافت درخواست‌های pending
        pending_deliveries = ProformaInvoiceDelivery.objects.filter(
            status='pending'
        ).select_related('proforma', 'proforma__customer', 'proforma__company_info')[:10]
        
        deliveries_data = []
        
        for delivery in pending_deliveries:
            proforma = delivery.proforma
            
            # تولید PDF
            try:
                from weasyprint import HTML, CSS
                from weasyprint.text.fonts import FontConfiguration
                from django.template.loader import render_to_string
                
                # رندر HTML
                html_string = render_to_string('proforma_invoice/pdf_template.html', {
                    'proforma': proforma,
                })
                
                # تبدیل به PDF
                html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
                
                # کانفیگ فونت برای فارسی
                font_config = FontConfiguration()
                
                # مسیر فایل فونت محلی
                from django.conf import settings
                import os
                font_dir = os.path.join(settings.BASE_DIR, 'core', 'static', 'vendor', 'vazir-font-30.1.0')
                
                # CSS برای فونت وزیر
                css = CSS(string=f'''
                    @font-face {{
                        font-family: 'Vazir';
                        src: url('file://{font_dir}/Vazir-Regular.ttf') format('truetype');
                        font-weight: normal;
                        font-style: normal;
                    }}
                    @font-face {{
                        font-family: 'Vazir';
                        src: url('file://{font_dir}/Vazir-Bold.ttf') format('truetype');
                        font-weight: bold;
                        font-style: normal;
                    }}
                    body {{
                        font-family: 'Vazir', sans-serif;
                    }}
                ''', font_config=font_config)
                
                # تولید PDF
                pdf_bytes = html.write_pdf(stylesheets=[css], font_config=font_config)
                
                # تبدیل به base64 برای انتقال
                import base64
                pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                
                deliveries_data.append({
                    'delivery_id': delivery.id,
                    'invoice_number': proforma.invoice_number,
                    'customer_name': proforma.customer.name,
                    'customer_phone': proforma.customer.get_primary_phone(),
                    'phone_numbers': delivery.phone_numbers,
                    'pdf_base64': pdf_base64,
                    'total_price': str(proforma.total_price),
                    'created_at': delivery.created_at.isoformat() if delivery.created_at else None,
                })
                
                # تغییر وضعیت به sent
                delivery.status = 'sent'
                delivery.sent_at = timezone.now()
                delivery.save()
                
                logger.info(f"پیش‌فاکتور {proforma.invoice_number} برای ارسال به KunQalay آماده شد")
                
            except Exception as e:
                logger.error(f"خطا در تولید PDF برای {proforma.invoice_number}: {str(e)}", exc_info=True)
                delivery.status = 'failed'
                delivery.notes = f"خطا در تولید PDF: {str(e)}"
                delivery.save()
                continue
        
        return JsonResponse({
            'success': True,
            'count': len(deliveries_data),
            'deliveries': deliveries_data,
        })
        
    except Exception as e:
        logger.error(f"خطا در API دریافت پیش‌فاکتورها: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'خطای داخلی سرور'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_confirm_delivery(request):
    """
    API endpoint برای تایید دریافت پیش‌فاکتور توسط KunQalay
    """
    # بررسی API Key
    api_key = request.headers.get('X-API-KEY')
    expected_key = getattr(settings, 'CRM_API_KEY', None)
    
    if not settings.DEBUG:
        if not api_key or not expected_key or api_key != expected_key:
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        data = json.loads(request.body)
        delivery_id = data.get('delivery_id')
        
        if not delivery_id:
            return JsonResponse({
                'success': False,
                'error': 'delivery_id is required'
            }, status=400)
        
        from .models import ProformaInvoiceDelivery
        
        delivery = ProformaInvoiceDelivery.objects.get(id=delivery_id)
        delivery.status = 'downloaded'
        delivery.downloaded_at = timezone.now()
        delivery.save()
        
        logger.info(f"دریافت پیش‌فاکتور {delivery.proforma.invoice_number} توسط KunQalay تایید شد")
        
        return JsonResponse({
            'success': True,
            'message': 'Delivery confirmed'
        })
        
    except ProformaInvoiceDelivery.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found'
        }, status=404)
    except Exception as e:
        logger.error(f"خطا در تایید دریافت: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Internal server error'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_queue_proforma_sms(request):
    """
    API endpoint برای queue کردن پیامک پیش‌فاکتور
    این endpoint توسط KunQalay بعد از دریافت پیش‌فاکتور فراخوانی می‌شود
    """
    # بررسی API Key
    api_key = request.headers.get('X-API-KEY')
    expected_key = getattr(settings, 'CRM_API_KEY', None)
    
    if not settings.DEBUG:
        if not api_key or not expected_key or api_key != expected_key:
            logger.warning(f"تلاش ناموفق برای دسترسی به API queue SMS: {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=401)
    
    try:
        from sms_api.apis import queue_sms
        
        data = json.loads(request.body)
        phone_numbers = data.get('phone_numbers', [])
        invoice_number = data.get('invoice_number', '')
        download_url = data.get('download_url', '')
        
        if not phone_numbers or not download_url:
            return JsonResponse({
                'success': False,
                'error': 'phone_numbers and download_url are required'
            }, status=400)
        
        # متن پیامک
        message = f"""با سلام؛

پیش‌فاکتور شما صادر شد.

برای دانلود فایل PDF به لینک زیر مراجعه کنید:
{download_url}

شرکت تأمین نهاده سیمرغ
021-66562216"""
        
        # queue کردن پیامک برای هر شماره
        queued_count = 0
        failed_numbers = []
        
        for phone in phone_numbers:
            try:
                queue_sms(
                    number=phone,
                    message=message,
                    notification_type='custom',
                    purchase=None,
                    suspended=False
                )
                queued_count += 1
                logger.info(f"پیامک پیش‌فاکتور {invoice_number} برای شماره {phone} queue شد")
            except Exception as e:
                logger.error(f"خطا در queue کردن پیامک برای {phone}: {str(e)}")
                failed_numbers.append(phone)
        
        return JsonResponse({
            'success': True,
            'queued_count': queued_count,
            'failed_count': len(failed_numbers),
            'failed_numbers': failed_numbers,
            'message': f'{queued_count} پیامک با موفقیت queue شد'
        })
        
    except Exception as e:
        logger.error(f"خطا در API queue کردن پیامک: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'خطای داخلی سرور'
        }, status=500)
