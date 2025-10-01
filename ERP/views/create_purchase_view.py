from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.core.exceptions import ValidationError
import logging

from core.decorators.det_user_role import determine_user_role
from core.PurchaseModel import Purchase
from major.models.NonBazargahPurchase import NonBazargahPurchase
from core.CustomerModel import Customer
from core.SalesAgentModel import SalesAgent
from core.CargoProductModel import CargoProduct
from major.models.NonBazargahProduct import NonBazargahProduct
from ERP.forms import CreatePurchaseForm

logger = logging.getLogger('erp_create_purchase')


def is_admin_or_manager(user):
    """بررسی دسترسی کاربر - فقط ادمین و مدیران"""
    if not user.is_authenticated:
        return False
    
    user_role = determine_user_role(user)
    return user_role in ['admin', 'logistics_manager', 'financial_manager']


@login_required
@user_passes_test(is_admin_or_manager)
@csrf_protect
def create_purchase_view(request):
    """
    ویو ایجاد خرید توسط ادمین
    """
    if request.method == 'POST':
        form = CreatePurchaseForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    purchase_type = form.cleaned_data['purchase_type']
                    customer = form.cleaned_data['customer']
                    sales_agent = form.cleaned_data.get('sales_agent')
                    description = form.cleaned_data.get('description', '')
                    customer_price = form.cleaned_data.get('customer_price', 0)
                    
                    if purchase_type == 'bazaargah':
                        # ایجاد خرید بازارگاهی
                        purchase = create_bazaargah_purchase(
                            form.cleaned_data, 
                            customer, 
                            sales_agent, 
                            description,
                            customer_price,
                            request.user
                        )
                        messages.success(request, f'خرید بازارگاهی {purchase.invoice_id} با موفقیت ایجاد شد.')
                        
                    elif purchase_type == 'non_bazaargah':
                        # ایجاد خرید خارج از بازارگاه
                        purchase = create_non_bazaargah_purchase(
                            form.cleaned_data, 
                            customer, 
                            sales_agent, 
                            description,
                            customer_price,
                            request.user
                        )
                        messages.success(request, f'خرید خارج از بازارگاه {purchase.purchase_number} با موفقیت ایجاد شد.')
                    
                    # ثبت لاگ
                    logger.info(f'خرید جدید توسط {request.user.username} ایجاد شد: {purchase}')
                    
                    return redirect('purchase_list')
                    
            except ValidationError as e:
                messages.error(request, f'خطا در ایجاد خرید: {str(e)}')
                logger.error(f'خطای اعتبارسنجی در ایجاد خرید: {str(e)}')
                
            except Exception as e:
                messages.error(request, 'خطای غیرمنتظره در ایجاد خرید رخ داد.')
                logger.error(f'خطای غیرمنتظره در ایجاد خرید: {str(e)}')
        
        else:
            messages.error(request, 'لطفاً اطلاعات فرم را بررسی کنید.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{form.fields[field].label}: {error}')
    
    else:
        form = CreatePurchaseForm()
    
    # آماده‌سازی context
    context = {
        'form': form,
        'page_title': 'ایجاد خرید جدید',
        'customers': Customer.objects.all().order_by('name'),
        'sales_agents': SalesAgent.objects.select_related('user').order_by('name'),
        'bazaargah_products': CargoProduct.objects.filter(status=True).order_by('product_type'),
        'non_bazaargah_products': NonBazargahProduct.objects.filter(status=True).order_by('name'),
    }
    
    return render(request, 'create_purchase.html', context)


def create_bazaargah_purchase(form_data, customer, sales_agent, description, customer_price, user):
    """
    ایجاد خرید بازارگاهی
    """
    product = form_data['bazaargah_product']
    weight = form_data['bazaargah_weight']
    
    purchase = Purchase.objects.create(
        customer=customer,
        cargo=product,
        order_weight=weight,
        description=description,
        customer_price=customer_price or product.customer_price,
        company_price=product.company_price,
        state='INITIATED',
        type='bazaargah',
        unique_sales_agent=sales_agent
    )
    
    # اضافه کردن کارشناس فروش به خرید
    if sales_agent:
        purchase.sales_agent.add(sales_agent)
        
        # اضافه کردن کارشناس فروش به مشتری اگر قبلاً نداشته
        if not customer.sales_agent.filter(id=sales_agent.id).exists():
            customer.sales_agent.add(sales_agent)
    
    return purchase


def create_non_bazaargah_purchase(form_data, customer, sales_agent, description, customer_price, user):
    """
    ایجاد خرید خارج از بازارگاه
    """
    product = form_data['non_bazaargah_product']
    unit = form_data['non_bazaargah_unit']
    quantity = form_data['non_bazaargah_quantity']
    bag_weight = form_data.get('non_bazaargah_bag_weight')
    
    # محاسبه وزن کل خرید بر اساس واحد
    total_weight_kg = calculate_purchase_weight(unit, quantity, bag_weight)
    
    # ثبت لاگ برای بررسی
    logger.info(f'محاسبه وزن خرید خارج از بازارگاه: واحد={unit}, مقدار={quantity}, وزن کیسه={bag_weight}, وزن کل={total_weight_kg} کیلوگرم')
    
    # ایجاد خرید - شماره خرید به صورت خودکار تولید می‌شود (از 100000)
    purchase = NonBazargahPurchase.objects.create(
        customer=customer,
        product=product,
        unit=unit,
        quantity=quantity,
        bag_weight=bag_weight,
        # purchase_number حذف شد - مدل خودش خودکار تولید می‌کند
        description=description,
        customer_price=customer_price or product.customer_price,
        company_price=product.get_purchase_price(),
        state='initiated',
        type='non_bazaargah',
        # اضافه کردن وزن محاسبه شده
        total_weight=total_weight_kg,  # وزن کل به کیلوگرم
    )
    
    # اضافه کردن کارشناس فروش به مشتری اگر قبلاً نداشته
    if sales_agent and not customer.sales_agent.filter(id=sales_agent.id).exists():
        customer.sales_agent.add(sales_agent)
    
    return purchase


def calculate_purchase_weight(unit, quantity, bag_weight=None):
    """
    محاسبه وزن کل خرید بر اساس واحد
    
    Args:
        unit: نوع واحد ('Kilo', 'Ton', 'Kiseh')
        quantity: مقدار
        bag_weight: وزن هر کیسه (فقط برای واحد کیسه)
    
    Returns:
        int: وزن کل به کیلوگرم
    """
    if unit == 'Kilo':
        # مقدار به کیلوگرم است
        return int(quantity)
    elif unit == 'Ton':
        # تبدیل تن به کیلوگرم
        return int(quantity * 1000)
    elif unit == 'Kiseh' and bag_weight:
        # تعداد کیسه × وزن هر کیسه
        return int(quantity * bag_weight)
    else:
        # در صورت عدم تطبیق، مقدار را به عنوان کیلوگرم در نظر بگیر
        return int(quantity)


@login_required
@require_http_methods(["GET"])
def get_product_details_api(request):
    """
    API برای دریافت جزئیات محصول
    """
    product_id = request.GET.get('product_id')
    product_type = request.GET.get('product_type')
    
    if not product_id or not product_type:
        return JsonResponse({'error': 'پارامترهای لازم ارسال نشده'}, status=400)
    
    try:
        if product_type == 'bazaargah':
            product = CargoProduct.objects.get(id=product_id)
            data = {
                'customer_price': product.customer_price,
                'company_price': product.company_price,
                'weight': product.weight,
                'product_type': product.get_product_type_display(),
                'country': product.get_country_display(),
            }
        elif product_type == 'non_bazaargah':
            product = NonBazargahProduct.objects.get(id=product_id)
            data = {
                'customer_price': product.customer_price,
                'purchase_price': product.get_purchase_price(),
                'name': product.name,
            }
        else:
            return JsonResponse({'error': 'نوع محصول نامعتبر'}, status=400)
            
        return JsonResponse(data)
        
    except (CargoProduct.DoesNotExist, NonBazargahProduct.DoesNotExist):
        return JsonResponse({'error': 'محصول یافت نشد'}, status=404)
    except Exception as e:
        logger.error(f'خطا در دریافت جزئیات محصول: {str(e)}')
        return JsonResponse({'error': 'خطای سرور'}, status=500)


@login_required
@require_http_methods(["GET"])
def get_customer_details_api(request):
    """
    API برای دریافت جزئیات مشتری
    """
    customer_id = request.GET.get('customer_id')
    
    if not customer_id:
        return JsonResponse({'error': 'شناسه مشتری ارسال نشده'}, status=400)
    
    try:
        customer = Customer.objects.prefetch_related('sales_agent').get(id=customer_id)
        
        # دریافت کارشناسان فروش مشتری
        sales_agents = []
        for agent in customer.sales_agent.all():
            sales_agents.append({
                'id': agent.id,
                'name': agent.name,
                'factor_code': agent.factor_code
            })
        
        data = {
            'name': customer.name,
            'city': customer.city,
            'sales_agents': sales_agents,
        }
        
        return JsonResponse(data)
        
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'مشتری یافت نشد'}, status=404)
    except Exception as e:
        logger.error(f'خطا در دریافت جزئیات مشتری: {str(e)}')
        return JsonResponse({'error': 'خطای سرور'}, status=500)
