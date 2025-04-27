from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse
from persiantools.jdatetime import JalaliDateTime
from core._models import Customer, CallSession, Task, Purchase, CargoProduct
from core.CustomerModel import FIELD_OF_ACTIVITY, PAYMENT_PREFERENCE_CHOICES
from django.contrib.auth.decorators import login_required
from django.db.models import Q

# core/forms.py
from django import forms
from core.SalesAgentModel import SalesAgent
from django.core.exceptions import PermissionDenied
from django.db import transaction
from jdatetime import datetime, date
from django.utils.translation import gettext_lazy as _
from core.CustomerModel import PhoneNumber

from core.CustomerModel import Customer, PhoneNumber, FIELD_OF_ACTIVITY, PAYMENT_PREFERENCE_CHOICES, ActivityField, ProductPreference, PaymentPreference
from core.TaskModel import Task
from core.CallSessionModel import CallSession
from core.PurchaseModel import Purchase
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent

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
    field_of_activity = forms.MultipleChoiceField(
        choices=FIELD_OF_ACTIVITY,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("حیطه فعالیت")
    )
    phone_number = forms.CharField(
        label=_("شماره تلفن اصلی"),
        max_length=20,
        required=True,
        help_text=_("شماره تلفن اصلی مشتری")
    )
    product_preferences = forms.MultipleChoiceField(
        choices=CargoProduct.PRODUCT_TYPES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("ترجیحات کالایی")
    )
    purchase_preferences = forms.MultipleChoiceField(
        choices=PAYMENT_PREFERENCE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("ترجیحات پرداخت")
    )
    
    def __init__(self, *args, **kwargs):
        sales_agent = kwargs.pop('sales_agent', None)
        super(CustomerForm, self).__init__(*args, **kwargs)
        self.sales_agent = sales_agent
        
        if self.instance and self.instance.pk:
            primary_phone = self.instance.phone_numbers.filter(is_primary=True).first()
            if primary_phone:
                self.initial['phone_number'] = primary_phone.number
            elif self.instance.phone_number:
                self.initial['phone_number'] = self.instance.phone_number
                
            # Use the property methods for initial values
            self.initial['field_of_activity'] = self.instance.get_field_of_activity_list()
            self.initial['product_preferences'] = self.instance.get_product_preferences_list()
            self.initial['purchase_preferences'] = self.instance.get_purchase_preferences_list()
                
        self.fields['name'].required = True

    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['created_at', 'updated_at', 'contact_start_time', 'contact_end_time', 'phone_number', 
                   'field_of_activity', 'product_preferences', 'purchase_preferences']
        widgets = {
            'added_description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Convert Persian digits to English digits if needed
            persian_digits = "۰۱۲۳۴۵۶۷۸۹"
            english_digits = "0123456789"
            translation_table = str.maketrans(persian_digits, english_digits)
            phone_number = phone_number.translate(translation_table)
            
            # Clean the number - keep only digits
            phone_number = ''.join(c for c in phone_number if c.isdigit())
            
            # Handle formats with leading zero
            if phone_number.startswith('0'):
                phone_number = phone_number[1:]
            
            # Validate format - must be 10 digits and start with 9
            if not phone_number.startswith('9'):
                raise forms.ValidationError(
                    _('شماره تلفن باید با 9 شروع شود. مثال: 9123456789')
                )
            
            if len(phone_number) != 10:
                raise forms.ValidationError(
                    _('شماره تلفن باید 10 رقم باشد. مثال: 9123456789')
                )
        return phone_number

    def clean_product_preferences(self):
        preferences = self.cleaned_data.get('product_preferences')
        valid_choices = [choice[0] for choice in CargoProduct.PRODUCT_TYPES]
        if preferences:
            for pref in preferences:
                if pref not in valid_choices:
                    raise forms.ValidationError(_(f"ترجیح کالایی '{pref}' معتبر نیست."))
        return preferences

    def clean_field_of_activity(self):
        activities = self.cleaned_data.get('field_of_activity')
        valid_choices = [choice[0] for choice in FIELD_OF_ACTIVITY]
        if activities:
            for activity in activities:
                if activity not in valid_choices:
                    raise forms.ValidationError(_(f"حیطه فعالیت '{activity}' معتبر نیست."))
        return activities

    def clean_purchase_preferences(self):
        preferences = self.cleaned_data.get('purchase_preferences')
        valid_choices = [choice[0] for choice in PAYMENT_PREFERENCE_CHOICES]
        if preferences:
            for pref in preferences:
                if pref not in valid_choices:
                    raise forms.ValidationError(_(f"ترجیح پرداخت '{pref}' معتبر نیست."))
        return preferences

    def save(self, commit=True):
        instance = super(CustomerForm, self).save(commit=False)
        
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            existing_phone = PhoneNumber.objects.filter(number=phone_number).first()
            if existing_phone and existing_phone.customer.id != instance.id:
                raise forms.ValidationError(
                    f"این شماره تلفن قبلاً برای مشتری {existing_phone.customer.name} ثبت شده است."
                )
            instance.phone_number = phone_number
        
        # ذخیره داده‌های مربوط به ترجیحات مشتری
        instance.field_of_activity_list = self.cleaned_data['field_of_activity']
        instance.product_preferences_list = self.cleaned_data['product_preferences']
        instance.purchase_preferences_list = self.cleaned_data['purchase_preferences']
        
        instance.save()
        
        if phone_number:
            if not existing_phone:
                try:
                    new_phone = PhoneNumber(
                        number=phone_number,
                        customer=instance,
                        is_primary=True
                    )
                    new_phone.save()
                except Exception as e:
                    print(f"Error creating phone number: {str(e)}")
            elif existing_phone.customer.id == instance.id and not existing_phone.is_primary:
                existing_phone.is_primary = True
                existing_phone.save()
        
        # Set ManyToMany relationships using the property setters
        if self.sales_agent and not instance.sales_agent.filter(id=self.sales_agent.id).exists():
            instance.sales_agent.add(self.sales_agent)
        
        if commit:
            instance.save()
        
        return instance

def check_customer_sales_agent(customer, sales_agent):
    if sales_agent not in customer.sales_agent.all():
        raise PermissionDenied("You do not have permission to access this customer.")

@login_required
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

@login_required
def customer_search(request):
    query = request.GET.get('query', '')
    results = []
    
    if query:
        try:
            # جستجوی کاربران مرتبط با این مدیر فروش
            sales_agent = SalesAgent.objects.get(user=request.user)
            # جستجوی مشتریانی که این کارشناس فروش را دارند
            customers = Customer.objects.filter(
                Q(phone_number__icontains=query) | 
                Q(name__icontains=query),
                sales_agent=sales_agent
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

@login_required
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

    if request.method == "POST" and 'save_customer' in request.POST:
        print("===== SAVE CUSTOMER POST DATA =====")
        for key, value in request.POST.items():
            print(f"{key}: {value}")
        print("==================================")
        
        phone = request.POST.get('phone_number')
        
        # Convert any Persian digits to English in the phone field
        if phone:
            persian_digits = "۰۱۲۳۴۵۶۷۸۹"
            english_digits = "0123456789"
            translation_table = str.maketrans(persian_digits, english_digits)
            phone = phone.translate(translation_table)
            phone = ''.join(c for c in phone if c.isdigit())
            # Handle formats with leading zero
            if phone.startswith('0'):
                phone = phone[1:]
        
        # حالت بروزرسانی مشتری موجود
        if request.POST.get('customer_id'):
            customer = get_object_or_404(Customer, id=request.POST.get('customer_id'))
            form = CustomerForm(request.POST, instance=customer, sales_agent=sales_agent)
        else:
            # جستجوی مشتری با شماره تلفن
            customer = Customer.get_customer_by_phone(phone)
            if customer:  # Update existing
                form = CustomerForm(request.POST, instance=customer, sales_agent=sales_agent)
            else:  # Create new
                form = CustomerForm(request.POST, sales_agent=sales_agent)
                is_new_customer = True
                
        # برای اطمینان از اینکه شماره تلفن در فرم پر شده
        if is_new_customer and phone:
            form.data = form.data.copy()  # ایجاد کپی قابل تغییر از داده‌های فرم
            form.data['phone_number'] = phone
            
        if form.is_valid():
            try:
                saved_customer = form.save()
                # اگر مشتری جدید ایجاد شده، کارشناس فروش را به آن اضافه می‌کنیم
                if is_new_customer and sales_agent:
                    saved_customer.sales_agent.add(sales_agent)
                    saved_customer.save()
                msg = "مشتری با موفقیت بروزرسانی شد" if not is_new_customer else "مشتری جدید ایجاد شد"
                messages.success(request, msg)
                print(f"Successfully saved customer: ID={saved_customer.id}, Name={saved_customer.name}")
                # ارجاع به صفحه مشتری
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={saved_customer.id}')
            except Exception as e:
                messages.error(request, f"خطا در ذخیره سازی: {str(e)}")
                print(f"Error saving customer: {str(e)}")
        else:
            # نمایش خطاهای فرم به صورت مشخص‌تر
            error_messages = []
            for field, errors in form.errors.items():
                field_name = form.fields[field].label if field in form.fields else field
                for error in errors:
                    error_messages.append(f"{field_name}: {error}")
            
            error_text = " | ".join(error_messages)
            messages.error(request, f"خطا در فرم - لطفا مقادیر را بررسی کنید: {error_text}")
            # برای دیباگ
            print(f"Form errors: {form.errors}")
            
            # مقدار پیش‌فرض برای فیلد نام
            if is_new_customer and not form.data.get('name'):
                form.initial['name'] = 'مشتری جدید'

    # بخش جستجو
    elif request.method == "POST" and 'phone_search' in request.POST:
        search_query = request.POST.get('search_query')
        
        if search_query:
            # جستجو بر اساس شماره تلفن یا نام
            if search_query.isdigit():
                # تمیز کردن شماره تلفن
                clean_number = search_query
                if clean_number.startswith('0'):
                    clean_number = clean_number[1:]
                    
                # جستجو با شماره تلفن تمیز شده
                customer = Customer.get_customer_by_phone(clean_number)
            else:
                # جستجو بر اساس نام و شماره‌های تلفن
                customers = Customer.objects.filter(
                    Q(name__icontains=search_query) |
                    Q(phone_number__icontains=search_query) |
                    Q(phone_numbers__number__icontains=search_query)
                ).distinct()[:1]
                customer = customers[0] if customers else None
            
            if customer:
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
            else:
                # ایجاد مشتری جدید اگر شماره تلفن معتبر باشد
                if search_query.isdigit() and len(search_query) == 10 and search_query.startswith('9'):
                    # شماره جدید - مشتری جدید ایجاد می‌کنیم
                    form = CustomerForm(initial={
                        'phone_number': search_query,
                        'name': 'مشتری جدید'
                    }, sales_agent=sales_agent)
                    # نمایش فرم خالی برای ایجاد مشتری جدید
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
        order_weight = request.POST.get('weight')
        use_custom_price = request.POST.get('use_custom_price') == 'on'
        custom_price = request.POST.get('custom_price')
        
        # try:
        with transaction.atomic():
            cargo = CargoProduct.objects.get(cottage=cottage_number) if cottage_number else None

            new_purchase = Purchase(
                customer=customer,
                order_weight=order_weight,
                cargo=cargo
            )
            new_purchase.full_clean()
            
            # استفاده از قیمت سفارشی اگر انتخاب شده باشد
            if use_custom_price and custom_price and custom_price.isdigit():
                new_purchase.customer_price = int(custom_price)
            else:
                new_purchase.customer_price = new_purchase.cargo.customer_price
                
            new_purchase.company_price = new_purchase.cargo.company_price
            new_purchase.amount_paid = new_purchase.customer_price * new_purchase.order_weight
            new_purchase.save()
            messages.success(request, "خرید جدید ثبت شد")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
    elif request.method == "POST" and 'create_purchase_without_sms' in request.POST and customer:
        cottage_number = request.POST.get('cottage_number')
        order_weight = request.POST.get('weight')
        use_custom_price = request.POST.get('use_custom_price') == 'on'
        custom_price = request.POST.get('custom_price')
        
        # try:
        with transaction.atomic():
            cargo = CargoProduct.objects.get(cottage=cottage_number) if cottage_number else None

            new_purchase = Purchase(
                customer=customer,
                order_weight=order_weight,
                cargo=cargo,
                send_cottage_sms=False
            )
            new_purchase.full_clean()
            
            # استفاده از قیمت سفارشی اگر انتخاب شده باشد
            if use_custom_price and custom_price and custom_price.isdigit():
                new_purchase.customer_price = int(custom_price)
            else:
                new_purchase.customer_price = new_purchase.cargo.customer_price
                
            new_purchase.company_price = new_purchase.cargo.company_price
            new_purchase.amount_paid = new_purchase.customer_price * new_purchase.order_weight
            new_purchase.save()
            messages.success(request, "خرید جدید ثبت شد")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

        # except Exception as e:
        #     messages.error(request, f"خطا در خرید: {e}")
        #     return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
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


    if customer:
        try:
            tasks = customer.get_tasks_by_time()
        except:
            tasks = []
    task_page = request.GET.get('task_page', 1)  
    task_paginator = Paginator(tasks, 4)  
    try:
        tasks = task_paginator.page(task_page)
    except PageNotAnInteger:
        tasks = task_paginator.page(1)
    except EmptyPage:
        tasks = task_paginator.page(task_paginator.num_pages)

    # بخش افزودن شماره تلفن جدید
    if request.method == "POST" and 'add_phone' in request.POST and customer:
        new_phone = request.POST.get('new_phone', '').strip()
        
        # Convert Persian digits to English digits if needed
        persian_digits = "۰۱۲۳۴۵۶۷۸۹"
        english_digits = "0123456789"
        translation_table = str.maketrans(persian_digits, english_digits)
        new_phone = new_phone.translate(translation_table)
        
        # Clean the number - keep only digits
        new_phone = ''.join(c for c in new_phone if c.isdigit())
        
        # Handle formats with leading zero
        if new_phone.startswith('0'):
            new_phone = new_phone[1:]
        
        if new_phone:
            # Basic format validation
            if not new_phone.startswith('9'):
                messages.error(request, "شماره تلفن باید با 9 شروع شود. مثال: 9123456789")
            elif len(new_phone) != 10:
                messages.error(request, "شماره تلفن باید 10 رقم باشد. مثال: 9123456789")
            else:
                # بررسی تکراری نبودن شماره
                existing_phone = PhoneNumber.objects.filter(number=new_phone).first()
                if existing_phone:
                    if existing_phone.customer == customer:
                        messages.warning(request, "این شماره تلفن قبلاً برای این مشتری ثبت شده است.")
                    else:
                        messages.error(request, f"این شماره تلفن قبلاً برای مشتری {existing_phone.customer.name} ثبت شده است.")
                else:
                    # ایجاد شماره جدید (غیر اصلی)
                    try:
                        PhoneNumber.objects.create(
                            number=new_phone,
                            customer=customer,
                            is_primary=False
                        )
                        messages.success(request, "شماره تلفن جدید اضافه شد.")
                    except ValidationError as e:
                        messages.error(request, f"خطا در افزودن شماره تلفن: {str(e)}")
        else:
            messages.error(request, "شماره تلفن نمی‌تواند خالی باشد.")
            
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
    
    # بخش تنظیم شماره تلفن اصلی
    if request.method == "POST" and 'make_primary' in request.POST and customer:
        phone_id = request.POST.get('make_primary')
        try:
            phone = PhoneNumber.objects.get(id=phone_id, customer=customer)
            
            # تمام شماره‌های این مشتری را غیر اصلی کنیم
            PhoneNumber.objects.filter(customer=customer).update(is_primary=False)
            
            # این شماره را اصلی کنیم
            phone.is_primary = True
            phone.save()
            
            messages.success(request, f"شماره {phone.number} به عنوان شماره اصلی تنظیم شد.")
        except PhoneNumber.DoesNotExist:
            messages.error(request, "شماره تلفن مورد نظر یافت نشد.")
        
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

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

def get_related_products(request):
    customer_id = request.GET.get('customer_id')
    country_filter = request.GET.get('country', '')
    type_filter = request.GET.get('type', '')  # این می‌تونه از پیش‌بینی بیاد
    if not customer_id:
        return JsonResponse({'error': 'No customer ID provided'}, status=400)
    try:
        purchases = Purchase.objects.filter(customer_id=customer_id).select_related("cargo")
        purchased_types = set(p.cargo.product_type for p in purchases if p.cargo)
        purchased_cottages = set(p.cargo.cottage for p in purchases if p.cargo)

        related_products = CargoProduct.objects.filter(
            product_type__in=purchased_types
        ).exclude(cottage__in=purchased_cottages)
        
        if country_filter:
            related_products = related_products.filter(country=country_filter)
        if type_filter:
            related_products = related_products.filter(product_type=type_filter)

        product_scores = {}
        for purchase in purchases:
            if purchase.cargo:
                key = (purchase.cargo.product_type, purchase.cargo.country)
                if key not in product_scores:
                    product_scores[key] = {'count': 0, 'weight': 0}
                product_scores[key]['count'] += 1
                product_scores[key]['weight'] += purchase.weight or 0

        product_data = []
        for product in related_products:
            key = (product.product_type, product.country)
            score = product_scores.get(key, {'count': 0, 'weight': 0})
            product_data.append({
                'cottage': product.cottage,
                'product_type': product.get_product_type_display(),
                'product_type_code': product.product_type,
                'country': product.get_country_display(),
                'country_code': product.country,
                'loading_time': product.loading_time,
                'score': score['count'] * 10 + score['weight'] / 1000,
                'available_weight': product.weight or 0
            })
        product_data.sort(key=lambda x: x['score'], reverse=True)
        return JsonResponse({
            'products': product_data[:5],
            'countries': list(set(p['country_code'] for p in product_data)),
            'types': list(set(p['product_type_code'] for p in product_data))
        }, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@login_required
def handle_form_submission(request, form, success_msg, redirect_url):
    if form.is_valid():
        instance = form.save()
        messages.success(request, success_msg)
        return redirect(redirect_url)
    else:
        for field, errors in form.errors.items():
            messages.error(request, f"خطا در {form.fields[field].label}: {', '.join(errors)}")
        return None
    
from django.http import JsonResponse
from django.db.models import Avg, Count
from datetime import timedelta
from core._models import Purchase
from django.utils import timezone

@login_required
def predict_next_purchase(request):
    customer_id = request.GET.get('customer_id')
    if not customer_id:
        return JsonResponse({'error': 'No customer ID provided'}, status=400)
    
    try:
        # خریدهای مشتری
        purchases = Purchase.objects.filter(customer_id=customer_id).select_related('cargo').order_by('created_at')
        if not purchases.exists():
            return JsonResponse({'prediction': None, 'message': 'هیچ خریدی برای پیش‌بینی وجود ندارد.'})

        # تحلیل ساده
        # 1. نوع محصول پرطرفدار
        product_types = purchases.values('cargo__product_type').annotate(
            count=Count('cargo__product_type'),
            total_weight=Avg('weight')
        ).order_by('-count')
        top_product = product_types.first()
        
        # 2. میانگین فاصله زمانی بین خریدها
        purchase_dates = [p.created_at for p in purchases]
        if len(purchase_dates) > 1:
            time_diffs = [(purchase_dates[i+1] - purchase_dates[i]).days for i in range(len(purchase_dates)-1)]
            avg_time_diff = sum(time_diffs) / len(time_diffs)
            last_purchase_date = purchase_dates[-1]
            next_purchase_date = last_purchase_date + timedelta(days=avg_time_diff)
        else:
            next_purchase_date = purchase_dates[0] + timedelta(days=7)  # فرض پیش‌فرض: ۷ روز بعد

        # 3. میانگین وزن خرید
        avg_weight = purchases.aggregate(avg_weight=Avg('weight'))['avg_weight']

        # داده‌های پیش‌بینی
        prediction = {
            'product_type': top_product['cargo__product_type'] if top_product else None,
            'product_type_display': CargoProduct.objects.filter(product_type=top_product['cargo__product_type']).first().get_product_type_display() if top_product else 'نامشخص',
            'next_date': next_purchase_date.strftime('%Y-%m-%d'),
            'avg_weight': round(avg_weight, 2),
            'confidence': min(0.9, 0.5 + (len(purchases) / 10)),  # یه معیار ساده برای اطمینان
            'history': [{
                'date': p.created_at.strftime('%Y-%m-%d'),
                'weight': p.weight,
                'product_type': p.cargo.get_product_type_display() if p.cargo else 'نامشخص'
            } for p in purchases[:5]]  # ۵ خرید آخر برای نمودار
        }
        return JsonResponse({'prediction': prediction})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)