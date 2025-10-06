from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction
from django.db.models import Q
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent
from core.decorators.decorators import role_required
from major.models.NonBazargahProduct import NonBazargahProduct
from major.models.Product import Product
from .models import CompanyInfo, ProformaInvoice, ProformaInvoiceItem
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
        
        # CSS برای فونت وزیر
        css = CSS(string='''
            @font-face {
                font-family: 'Vazir';
                src: url('https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-Regular.ttf') format('truetype');
                font-weight: normal;
                font-style: normal;
            }
            @font-face {
                font-family: 'Vazir';
                src: url('https://cdn.jsdelivr.net/gh/rastikerdar/vazir-font@v30.1.0/dist/Vazir-Bold.ttf') format('truetype');
                font-weight: bold;
                font-style: normal;
            }
            body {
                font-family: 'Vazir', sans-serif;
            }
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
