from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db import transaction
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


@role_required('sales_agent', 'admin')
@login_required
def proforma_step1_customer_info(request, customer_id):
    """مرحله 1: تایید اطلاعات مشتری"""
    customer = get_object_or_404(Customer, id=customer_id)
    company_info = CompanyInfo.get_active_company()
    
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
    
    # بررسی وجود اطلاعات شرکت
    if not company_info:
        messages.error(request, "لطفاً ابتدا اطلاعات شرکت را از پنل مدیریت تکمیل کنید.")
        return redirect(f"{reverse('general_customer_CRUD')}?customer_id={customer_id}")
    
    context = {
        'customer': customer,
        'company_info': company_info,
        'missing_fields': missing_fields,
        'step': 1,
    }
    
    return render(request, 'proforma_invoice/step1_customer_info.html', context)


@role_required('sales_agent', 'admin')
@login_required
def proforma_step2_product_selection(request, customer_id):
    """مرحله 2: انتخاب محصولات و مشخصات"""
    customer = get_object_or_404(Customer, id=customer_id)
    company_info = CompanyInfo.get_active_company()
    
    # دریافت محصولات فعال (هم بازارگاه و هم خارج از بازارگاه)
    cargo_products = CargoProduct.get_active_products()
    non_bazargah_products = NonBazargahProduct.get_active_products()
    
    if request.method == 'POST':
        try:
            # دریافت آیتم‌های محصول از فرم (به صورت JSON)
            items_json = request.POST.get('items')
            notes = request.POST.get('notes', '')
            
            if not items_json:
                messages.error(request, "لطفاً حداقل یک محصول اضافه کنید.")
                raise ValueError("No items provided")
            
            items_data = json.loads(items_json)
            
            if not items_data:
                messages.error(request, "لطفاً حداقل یک محصول اضافه کنید.")
                raise ValueError("No items in list")
            
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
                
                # ایجاد آیتم‌های محصول
                for idx, item_data in enumerate(items_data):
                    item = ProformaInvoiceItem()
                    item.proforma = proforma
                    item.product_name = item_data.get('product_name', '')
                    item.product_description = item_data.get('product_description', '')
                    item.quantity = float(item_data.get('quantity', 0))
                    item.unit = item_data.get('unit', 'kg')
                    item.unit_price = float(item_data.get('unit_price', 0))
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
                            pass
                    
                    item.save()
                
                # محاسبه قیمت کل
                proforma.calculate_total()
            
            # انتقال به مرحله نمایش
            return redirect('proforma_preview', proforma_id=proforma.id)
            
        except json.JSONDecodeError:
            messages.error(request, "خطا در پردازش اطلاعات محصولات.")
        except Exception as e:
            messages.error(request, f"خطا در ثبت اطلاعات: {str(e)}")
    
    context = {
        'customer': customer,
        'company_info': company_info,
        'cargo_products': cargo_products,
        'non_bazargah_products': non_bazargah_products,
        'step': 2,
    }
    
    return render(request, 'proforma_invoice/step2_product_selection.html', context)


@role_required('sales_agent', 'admin')
@login_required
def proforma_preview(request, proforma_id):
    """مرحله 3: پیش‌نمایش و تایید نهایی"""
    proforma = get_object_or_404(ProformaInvoice, id=proforma_id)
    
    # بررسی دسترسی
    if hasattr(request.user, 'sales_agent'):
        sales_agent = request.user.sales_agent
        if proforma.sales_agent != sales_agent and not request.user.is_superuser:
            messages.error(request, "شما دسترسی به این پیش فاکتور ندارید.")
            return redirect('general_customer_CRUD')
    
    if request.method == 'POST':
        if 'finalize' in request.POST:
            proforma.is_finalized = True
            proforma.save()
            messages.success(request, "پیش فاکتور با موفقیت نهایی شد.")
        elif 'edit' in request.POST:
            return redirect('proforma_step2', customer_id=proforma.customer.id)
    
    context = {
        'proforma': proforma,
        'step': 3,
    }
    
    return render(request, 'proforma_invoice/preview.html', context)


@role_required('sales_agent', 'admin')
@login_required
def proforma_download_pdf(request, proforma_id):
    """دانلود پیش فاکتور به صورت PDF"""
    try:
        from weasyprint import HTML, CSS
        from weasyprint.text.fonts import FontConfiguration
    except ImportError:
        messages.error(request, "خطا: پکیج WeasyPrint به درستی نصب نشده است. لطفاً با مدیر سیستم تماس بگیرید.")
        return redirect('proforma_preview', proforma_id=proforma_id)
    
    proforma = get_object_or_404(ProformaInvoice, id=proforma_id)
    
    # بررسی دسترسی
    if hasattr(request.user, 'sales_agent'):
        sales_agent = request.user.sales_agent
        if proforma.sales_agent != sales_agent and not request.user.is_superuser:
            messages.error(request, "شما دسترسی به این پیش فاکتور ندارید.")
            return redirect('general_customer_CRUD')
    
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
    
    # ارسال به عنوان پاسخ
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="proforma_{proforma.invoice_number}.pdf"'
    
    return response


@role_required('sales_agent', 'admin')
@login_required
def proforma_list(request):
    """لیست تمام پیش فاکتورها"""
    if hasattr(request.user, 'sales_agent') and not request.user.is_superuser:
        sales_agent = request.user.sales_agent
        proformas = ProformaInvoice.objects.filter(sales_agent=sales_agent)
    else:
        proformas = ProformaInvoice.objects.all()
    
    context = {
        'proformas': proformas,
    }
    
    return render(request, 'proforma_invoice/list.html', context)
