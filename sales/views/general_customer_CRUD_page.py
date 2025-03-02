from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from datetime import datetime
from core.CustomerModel import Customer, FIELD_OF_ACTIVITY
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from persiantools.jdatetime import JalaliDateTime

# core/forms.py
from django import forms
from core.SalesAgentModel import SalesAgent
from django.core.exceptions import PermissionDenied
from django.db import transaction
from jdatetime import datetime, date

def get_related_products(request):
    customer_id = request.GET.get('customer_id')
    if not customer_id:
        return JsonResponse({'error': 'No customer ID provided'}, status=400)
    try:
        purchases = Purchase.objects.filter(customer_id=customer_id).select_related("cargo")
        purchased_product_types = [purchase.cargo.product_type for purchase in purchases if purchase.cargo]
        related_products = CargoProduct.objects.filter(product_type__in=purchased_product_types).exclude(cottage__in=[p.cottage for p in purchases])
        product_data = [{
            'cottage': product.cottage,
            'product_type': product.get_product_type_display(),
            'country': product.get_country_display(),
            'loading_time': product.loading_time,
        } for product in related_products]
        return JsonResponse(product_data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def persian_digits_to_english(persian_text):
    """تبدیل اعداد فارسی به انگلیسی در یک رشته."""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    return persian_text.translate(translation_table)
def jalali_to_gregorian(jalali_datetime_str):
    """تبدیل رشته جلالی (با اعداد فارسی) به DateTime گرگوریان."""
    try:
        # تبدیل اعداد فارسی به انگلیسی
        jalali_datetime_str_en = persian_digits_to_english(jalali_datetime_str)

        # تلاش برای تبدیل با فرمت صحیح
        return JalaliDateTime.strptime(jalali_datetime_str_en, "%Y/%m/%d %H:%M").to_gregorian()
    except Exception as e:
        raise ValueError(f"فرمت تاریخ نامعتبر است: {jalali_datetime_str} - خطای اصلی: {str(e)}")
 
class CustomerForm(forms.ModelForm):
    field_of_activity = forms.ChoiceField(
        choices=FIELD_OF_ACTIVITY,
        label="حیطه فعالیت",
        required=False
    )
    def __init__(self, *args, **kwargs):
        sales_agent = kwargs.pop('sales_agent', None)
        super().__init__(*args, **kwargs)
        if sales_agent:
            self.fields['sales_agent'].initial = sales_agent
            self.fields['sales_agent'].disabled = True

    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['created_at', 'updated_at',  'contact_start_time', 'contact_end_time']
        widgets = {
            'contact_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'contact_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'added_description': forms.Textarea(attrs={'rows': 3}),
        }

def check_customer_sales_agent(customer, sales_agent):
    if customer.sales_agent != sales_agent:
        raise PermissionDenied("You do not have permission to access this customer.")


from django.http import JsonResponse
from core.CustomerModel import Customer  # Remove duplicate import
from django.db.models import Q
def change_task_status(request, pk):
    task = get_object_or_404(Task, id=pk)
    if request.method == "POST":
        try:
            task.change_status()
            task.full_clean()
            task.save()
            messages.success(request, "وضعیت تسک با موفقیت تغییر کرد")
        except ValidationError as e:
            messages.error(request, f"خطا در تغییر وضعیت تسک: {e}")
    else:
        messages.error(request, "وضعیت جدید معتبر نیست")

    
    return redirect(request.META.get('HTTP_REFERER'))

def customer_search(request):
    query = request.GET.get('query', '')
    results = []
    
    if query:
        try:
            customers = Customer.objects.filter(
                Q(phone_number__icontains=query) | 
                Q(name__icontains=query),
                sales_agent__user=request.user
            )[:10]
            
            results = [
                {
                    'name': c.name if c.name else 'بدون نام',
                    'phone_number': c.phone_number
                }
                for c in customers
            ]
        except Exception as e:
            print(f"Error during customer search: {e}")
            results = []
    return JsonResponse(results, safe=False)

def general_customer_CRUD_view(request):
    """
    ویو جامع مدیریت مشتری شامل:
    - جستجو با شماره تلفن
    - نمایش پروفایل و تاریخچه‌ها
    - ثبت تماس/تسک/خرید
    """

    customer = None
    tasks = []
    calls = []
    purchases = []
    cargo_product = None
    try:
        sales_agent = SalesAgent.objects.get(user=request.user)
    except SalesAgent.DoesNotExist:
        sales_agent = None

    form = None
    is_new_customer = False

    # بخش مدیریت فرم مشتری
    if request.method == "POST" and 'save_customer' in request.POST:
        phone = request.POST.get('phone_number')
        customer = Customer.get_customer_by_phone(phone)
        
        if customer:  # Update existing
            form = CustomerForm(request.POST, instance=customer, sales_agent=sales_agent)
        else:  # Create new
            form = CustomerForm(request.POST, sales_agent=sales_agent)
            is_new_customer = True
            
        if form.is_valid():
            saved_customer = form.save()
            msg = "مشتری با موفقیت بروزرسانی شد" if customer else "مشتری جدید ایجاد شد"
            messages.success(request, msg)
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={saved_customer.id}')
        else:
            messages.error(request, "خطا در فرم - لطفا مقادیر را بررسی کنید")

    # بخش جستجو
    elif request.method == "POST" and 'phone_search' in request.POST:
        search_query = request.POST.get('search_query')
        
        if search_query:
            # جستجو بر اساس شماره تلفن یا نام
            if search_query.isdigit():
                customer = Customer.get_customer_by_phone(search_query)
            else:
                customers = Customer.objects.filter(
                    Q(phone_number__icontains=search_query) |
                    Q(name__icontains=search_query)
                )[:1]
                customer = customers[0] if customers else None
            
            if customer:
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
            else:
                # ایجاد مشتری جدید اگر شماره تلفن معتبر باشد
                if search_query.isdigit() and len(search_query) == 10 and search_query.startswith('9'):
                    customer = Customer(phone_number=search_query)
                    form = CustomerForm(instance=customer, sales_agent=sales_agent)
                    is_new_customer = True
                else:
                    messages.error(request, "شماره تلفن معتبر نیست")

    # بارگیری مشتری موجود
    customer_id = request.GET.get('customer_id')
    if customer_id and not form:
        customer = get_object_or_404(Customer, id=customer_id)
        check_customer_sales_agent(customer=customer, sales_agent=sales_agent)
        form = CustomerForm(instance=customer, sales_agent=sales_agent)
        tasks = customer.get_tasks_by_time()
        calls = customer.get_calls_by_time()
        purchases = customer.get_purchases_by_time()

    # بخش ثبت تماس
    if request.method == "POST" and 'create_call' in request.POST and customer:
        call_type = request.POST.get('call_type')
        call_status = request.POST.get('call_status')
        note = request.POST.get('note')
        
        new_call = CallSession(
            customer=customer,
            type=call_type,
            status='successful',
            note=note
        )
        try:
            new_call.full_clean()
            new_call.save()
            messages.success(request, "تماس جدید ثبت شد")
        except ValidationError as e:
            messages.error(request, f"خطا در تماس: {e}")
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

    # بخش ثبت تسک
    if request.method == "POST" and 'create_task' in request.POST and customer:
        task_description = request.POST.get('task_description')
        due_date_str = request.POST.get('due_date', '').strip()

        new_task = Task(
            description=task_description,
            customer=customer,
            due_date = jalali_to_gregorian(due_date_str),
            # due_date=datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M') if due_date_str else None,  # توجه به فرمت datetime-local HTML
            status=False
        )
        try:
            new_task.full_clean()
            new_task.save()
            messages.success(request, "تسک جدید ثبت شد")
        except ValidationError as e:
            messages.error(request, f"خطا در تسک: {e}")
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

    # بخش ثبت خرید
    if request.method == "POST" and 'create_purchase' in request.POST and customer:
        cottage_number = request.POST.get('cottage_number')
        weight = request.POST.get('weight')
        
        try:
            with transaction.atomic():
                cargo = CargoProduct.objects.get(cottage=cottage_number) if cottage_number else None

                new_purchase = Purchase(
                    customer=customer,
                    weight=weight,
                    cargo=cargo
                )
                new_purchase.full_clean()
                new_purchase.save()
                messages.success(request, "خرید جدید ثبت شد")
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
        except Exception as e:
            messages.error(request, f"خطا در خرید: {e}")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
    active_products = CargoProduct.get_active_products()

    if customer:
        try:
            purchases = customer.get_purchases_by_time()
        except:
            purchases = []
    purchase_page = request.GET.get('purchase_page', 1)  # دریافت شماره صفحه از URL
    purchase_paginator = Paginator(purchases, 4)  # نمایش ۵ خرید در هر صفحه
    try:
        purchases = purchase_paginator.page(purchase_page)
    except PageNotAnInteger:
        purchases = purchase_paginator.page(1)
    except EmptyPage:
        purchases = purchase_paginator.page(purchase_paginator.num_pages)

    context = {
        'customer': customer,
        'form': form,
        'is_new_customer': is_new_customer,
        'tasks': tasks,
        'calls': calls,
        'purchases': purchases,
        'cargo_product': cargo_product,
        'active_products': active_products,
    }

    print( context )
    return render(request, 'general_customer_CRUD_view.html', context)
