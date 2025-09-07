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
from core.SupportAgentModel import SupportAgent
from core.SupportAgentTask import SupportAgentTask
from django.db import transaction
from jdatetime import datetime, date
from django.utils.translation import gettext_lazy as _
from core.CustomerModel import PhoneNumber

from core.CustomerModel import Customer, PhoneNumber, FIELD_OF_ACTIVITY, PAYMENT_PREFERENCE_CHOICES, ActivityField, ProductPreference, PaymentPreference
from core.TaskModel import Task
from core.CallSessionModel import CallSession
from core.PurchaseModel import Purchase
from core.CargoProductModel import CargoProduct
from core.SalesAgentModel import SalesAgent, PhoneAssignment
from core.decorators.decorators import role_required
from major.models.NonBazargahProduct import NonBazargahProduct
from major.models.NonBazargahPurchase import NonBazargahPurchase

import json
from django.template.loader import render_to_string
import logging

logger = logging.getLogger("general_customer_CRUD_view")

def persian_digits_to_english(persian_text):
    """تبدیل اعداد فارسی به انگلیسی در یک رشته."""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"
    translation_table = str.maketrans(persian_digits, english_digits)
    return persian_text.translate(translation_table)

def clean_and_validate_phone(phone_input):
    """تمیز کردن و اعتبارسنجی شماره تلفن."""
    if not phone_input:
        return None, False
    
    # تبدیل اعداد فارسی به انگلیسی
    clean_phone = persian_digits_to_english(phone_input)
    
    # پاکسازی شماره از کاراکترهای غیرعددی
    clean_phone = ''.join(c for c in clean_phone if c.isdigit())
    
    # اگر با صفر شروع می‌شود، آن را حذف می‌کنیم
    if clean_phone.startswith('0'):
        clean_phone = clean_phone[1:]
    
    # حذف کد کشور ایران اگر وجود داشت
    if clean_phone.startswith('98'):
        clean_phone = clean_phone[2:]
    
    # بررسی اعتبار شماره
    is_valid = (
        len(clean_phone) == 10 and 
        clean_phone.startswith('9') and
        clean_phone.isdigit()
    )
    
    return clean_phone, is_valid
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
    assignment_id = forms.IntegerField(widget=forms.HiddenInput(), required=False)
    field_of_activity = forms.MultipleChoiceField(
        choices=FIELD_OF_ACTIVITY,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("حیطه فعالیت")
    )
    phone_number = forms.CharField(
        label=_("شماره تلفن اصلی"),
        max_length=20,
        required=False,  # به صورت پیش فرض غیرالزامی و در __init__ تنظیم می‌شود
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
            # برای مشتریان موجود، فیلد شماره تلفن الزامی نیست
            self.fields['phone_number'].required = False
            
            primary_phone = self.instance.phone_numbers.filter(is_primary=True).first()
            if primary_phone:
                self.initial['phone_number'] = primary_phone.number
            elif self.instance.phone_number:
                self.initial['phone_number'] = self.instance.phone_number
                
            # Use the property methods for initial values
            self.initial['field_of_activity'] = self.instance.get_field_of_activity_list()
            self.initial['product_preferences'] = self.instance.get_product_preferences_list()
            self.initial['purchase_preferences'] = self.instance.get_purchase_preferences_list()
        else:
            # برای مشتریان جدید، فیلد شماره تلفن الزامی است
            self.fields['phone_number'].required = True
                
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
        
        # اگر شماره تلفن خالی است
        if not phone_number:
            # برای مشتریان جدید، شماره الزامی است
            if not (self.instance and self.instance.pk):
                raise forms.ValidationError(_('شماره تلفن اصلی الزامی است.'))
            # برای مشتریان موجود، شماره خالی مجاز است
            return phone_number
        
        # اگر شماره وارد شده، آن را validate کن
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
        # اگر شماره تلفن خالی است، آن را null بگذار
        elif not phone_number and not (self.instance and self.instance.pk):
            # برای مشتریان جدید که شماره ندارند، خطا بده
            raise forms.ValidationError(_('شماره تلفن اصلی الزامی است.'))
        
        # اول مشتری را ذخیره می‌کنیم تا primary key داشته باشد
        instance.save()
        
        # حالا که مشتری ذخیره شده و primary key دارد، رابطه‌ها را تنظیم می‌کنیم
        instance.field_of_activity_list = self.cleaned_data['field_of_activity']
        instance.product_preferences_list = self.cleaned_data['product_preferences']
        instance.purchase_preferences_list = self.cleaned_data['purchase_preferences']
        
        # ایجاد شماره تلفن فقط اگر شماره وارد شده باشد
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

class NonBazargahPurchaseForm(forms.ModelForm):
    """فرم خرید خارج بازارگاه"""
    
    class Meta:
        model = NonBazargahPurchase
        fields = ['product', 'unit', 'quantity', 'bag_weight', 'customer_price', 'description']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'bag_weight': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'وزن هر کیسه (کیلوگرم)'}),
            'customer_price': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'قیمت واحد (ریال)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'توضیحات خرید'}),
        }
        labels = {
            'product': 'محصول',
            'unit': 'واحد',
            'quantity': 'مقدار',
            'bag_weight': 'وزن کیسه (کیلوگرم)',
            'customer_price': 'قیمت واحد (ریال)',
            'description': 'توضیحات',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # فقط محصولات فعال را نمایش بده
        self.fields['product'].queryset = NonBazargahProduct.get_active_products()
        
        # تنظیم فیلدهای اختیاری
        self.fields['bag_weight'].required = False
        self.fields['customer_price'].required = False
        self.fields['description'].required = False
    
    def clean(self):
        cleaned_data = super().clean()
        unit = cleaned_data.get('unit')
        bag_weight = cleaned_data.get('bag_weight')
        
        # اگر واحد کیسه انتخاب شده، وزن کیسه الزامی است
        if unit == 'Kiseh' and not bag_weight:
            raise forms.ValidationError('در صورت انتخاب واحد کیسه، وزن کیسه الزامی است.')
        
        # اگر واحد کیسه نیست، وزن کیسه نباید وارد شود
        if unit != 'Kiseh' and bag_weight:
            cleaned_data['bag_weight'] = None
        
        return cleaned_data

def check_customer_sales_agent(customer, sales_agent):
    if sales_agent not in customer.sales_agent.all():
        raise PermissionDenied("You do not have permission to access this customer.")

@role_required('sales_agent', 'admin')
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

@role_required('sales_agent', 'admin')
@login_required
def customer_search(request):
    query = request.GET.get('query', '')
    results = []
    
    if query:
        try:
            # جستجوی کاربران مرتبط با این مدیر فروش
            sales_agent = SalesAgent.objects.get(user=request.user)
            
            # تبدیل اعداد فارسی به انگلیسی
            if query:
                persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                english_digits = "0123456789"
                translation_table = str.maketrans(persian_digits, english_digits)
                query = query.translate(translation_table)
            
            # تمیز کردن شماره تلفن اگر عدد باشد
            if query.isdigit():
                clean_query = query
                if clean_query.startswith('0'):
                    clean_query = clean_query[1:]
            else:
                clean_query = query
            
            # جستجوی مشتریانی که این کارشناس فروش را دارند
            # جستجو در هر دو فیلد: phone_number و PhoneNumber
            customers = Customer.objects.filter(
                (Q(phone_number__icontains=clean_query) | 
                Q(name__icontains=query) |
                Q(phone_numbers__number__icontains=clean_query)),
                sales_agent=sales_agent
            ).distinct()[:10]
            
            results = []
            for c in customers:
                # تشخیص اینکه جستجو بر اساس کدام شماره انجام شده
                matching_phone = None
                
                # اگر جستجو بر اساس عدد بود، بررسی کنیم کدام شماره مطابقت دارد
                if clean_query and clean_query.isdigit():
                    # ابتدا بررسی شماره‌های PhoneNumber
                    matching_phone_obj = c.phone_numbers.filter(number__icontains=clean_query).first()
                    if matching_phone_obj:
                        matching_phone = matching_phone_obj.number
                    # اگر در PhoneNumber یافت نشد، شماره قدیمی را بررسی کن
                    elif c.phone_number and clean_query in c.phone_number:
                        matching_phone = c.phone_number
                
                # اگر شماره مطابق پیدا نشد یا جستجو بر اساس نام بود، شماره اصلی را نمایش بده
                if not matching_phone:
                    matching_phone = c.get_primary_phone()
                
                customer_info = {
                    'id': c.id,
                    'name': c.name if c.name else 'بدون نام',
                    'phone_number': matching_phone,
                    'city': c.city or '',
                }
                results.append(customer_info)
                
        except Exception as e:
            print(f"Error during customer search: {e}")
            results = []
    
    return JsonResponse(results, safe=False)

@role_required('sales_agent', 'admin')

@login_required
def general_customer_CRUD_view(request):
    """
    نمای کلی برای ایجاد، مشاهده، و ویرایش مشتریان، تماس‌ها، تسک‌ها و خریدها.
    """
    query = request.GET.get('search_query', '')
    customer_id = request.GET.get('customer_id')
    assignment_id = request.GET.get('assignment_id')
    customer = None
    sales_agent = None

    # اطمینان از اینکه کاربر یک کارشناس فروش است
    if hasattr(request.user, 'sales_agent'):
        sales_agent = request.user.sales_agent

    # اول بررسی customer_id (اولویت بالاتر)
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            # بررسی دسترسی کارشناس فروش
            if sales_agent and customer not in sales_agent.get_all_customers():
                
                messages.error(request, "شما دسترسی به این مشتری ندارید.")
                customer = None
        except Customer.DoesNotExist:
            messages.error(request, "مشتری یافت نشد.")
            customer = None
    elif query:
        # تمیز کردن و اعتبارسنجی شماره تلفن
        clean_phone, is_valid_phone = clean_and_validate_phone(query)
        
        if is_valid_phone:
            # جستجوی مشتری با شماره تمیز شده
            customer = Customer.get_customer_by_phone(clean_phone)
            if customer:
                if sales_agent:
                    if sales_agent not in customer.get_sales_agents():
                        messages.error(request, "شما دسترسی به این مشتری ندارید.")
                        customer = None
            
            if not customer:
                # اگر شماره معتبر است ولی مشتری پیدا نشد، پیام مناسب نمایش بده
                messages.info(request, f"مشتری با شماره {clean_phone} یافت نشد. می‌توانید مشتری جدید ایجاد کنید.")
        else:
    # اگر ورودی شماره تلفن معتبر نیست، جستجوی عادی انجام بده
            matching_customers = Customer.objects.filter(name__icontains=query)
    
            customer = None
            for candidate in matching_customers:
                if sales_agent in candidate.get_sales_agents():
                    customer = candidate
                    break  # اولین مشتری مناسب را پیدا کردیم، کافیست
            
            if not sales_agent:
                customer = Customer.objects.filter(phone_number__icontains=query).first()

            if not customer:
                messages.warning(request, f"هیچ مشتری با نام '{query}' که به این کارشناس فروش تخصیص داشته باشد یافت نشد.")
            elif clean_phone:
        # اگر شماره نامعتبر بود، راهنمایی بده
                messages.error(request, "فرمت شماره تلفن نامعتبر است. شماره باید 10 رقم باشد و با 9 شروع شود. (مثال: 9123456789)")

        
        # اگر شماره معتبر بود برای استفاده در initial_data
        if is_valid_phone:
            query = clean_phone

    # مدیریت جستجو با دکمه phone_search
    if request.method == 'POST' and 'phone_search' in request.POST:
        search_query = request.POST.get('search_query', '').strip()
        if search_query:
            # redirect به همین صفحه با query parameter
            return redirect(reverse('general_customer_CRUD') + f'?search_query={search_query}')
        else:
            messages.warning(request, "لطفاً چیزی برای جستجو وارد کنید")
            return redirect(reverse('general_customer_CRUD'))

    # آماده کردن فرم مشتری
    form = None
    if request.method == 'POST' and 'save_customer' in request.POST:
        # فقط در صورت submit فرم مشتری، فرم را validate کن
        form = CustomerForm(request.POST, instance=customer, sales_agent=sales_agent)
    else:
        # در غیر این صورت، فرم را برای نمایش آماده کن
        if customer:
            form = CustomerForm(instance=customer, sales_agent=sales_agent)
        else:
            # پر کردن شماره تلفن و آیدی تخصیص در فرم اگر مشتری جدید باشد
            initial_data = {'phone_number': query}
            if assignment_id:
                initial_data['assignment_id'] = assignment_id
            form = CustomerForm(initial=initial_data, sales_agent=sales_agent)

    # مدیریت فرم مشتری فقط وقتی دکمه ذخیره مشتری زده شده
    if request.method == 'POST' and 'save_customer' in request.POST:
        if form.is_valid():
            try:
                with transaction.atomic():
                    new_customer = form.save()
                    
                    # بررسی و آپدیت وضعیت تخصیص شماره
                    assignment_id = form.cleaned_data.get('assignment_id')
                    if assignment_id:
                        try:
                            assignment = PhoneAssignment.objects.get(id=assignment_id)
                            assignment.mark_as_converted()
                        except PhoneAssignment.DoesNotExist:
                            # اگر تخصیص یافت نشد، مشکلی نیست، فقط ادامه می‌دهیم
                            pass

                    messages.success(request, f"مشتری '{new_customer.name}' با موفقیت ذخیره شد.")
                    return redirect(reverse('general_customer_CRUD') + f'?search_query={new_customer.get_primary_phone()}')
            except forms.ValidationError as e:
                messages.error(request, e.message)
            except Exception as e:
                messages.error(request, f"خطا در ذخیره مشتری: {str(e)}")
        else:
            # نمایش خطاها فقط برای فرم مشتری
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"خطا در فیلد '{form.fields[field].label}': {error}")
    
    # مدیریت فرم‌های POST مختلف
    if request.method == 'POST' and customer:
        # ثبت تماس جدید
        if 'create_call' in request.POST:
            call_type = request.POST.get('call_type')
            note = request.POST.get('note')
            active_tab = request.POST.get('active_tab', 'calls')
            
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
                messages.error(request, f"خطا در ثبت تماس: {e}")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}&active_tab={active_tab}')
        
        # ثبت تسک جدید
        elif 'create_task' in request.POST:
            task_description = request.POST.get('task_description')
            due_date_str = request.POST.get('due_date')
            active_tab = request.POST.get('active_tab', 'tasks')
            
            if task_description and due_date_str:
                try:
                    due_date = jalali_to_gregorian(due_date_str)
                    new_task = Task(
                        customer=customer,
                        description=task_description,
                        due_date=due_date
                    )
                    new_task.full_clean()
                    new_task.save()
                    messages.success(request, "تسک جدید ثبت شد")
                except (ValueError, ValidationError) as e:
                    messages.error(request, f"خطا در ثبت تسک: {e}")
            else:
                messages.error(request, "لطفاً تمام فیلدهای ضروری را پر کنید")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}&active_tab={active_tab}')
        
        # ثبت خرید جدید بدون پیامک
        elif 'create_purchase_without_sms' in request.POST:
            cottage_number = request.POST.get('cottage_number')
            weight = request.POST.get('weight')
            use_custom_price = request.POST.get('use_custom_price')
            custom_price = request.POST.get('custom_price')
            active_tab = request.POST.get('active_tab', 'purchases')
            
            if cottage_number and weight:
                try:
                    cargo = CargoProduct.objects.get(cottage=cottage_number, status=True)
                    
                    # تعیین قیمت
                    if use_custom_price and custom_price:
                        customer_price = int(custom_price)
                    else:
                        customer_price = cargo.customer_price
                    
                    # ایجاد خرید جدید
                    from core.PurchaseModel import Purchase
                    new_purchase = Purchase(
                        customer=customer,
                        cargo=cargo,
                        order_weight=int(weight),
                        customer_price=customer_price,
                        state='INITIATED'
                    )
                    
                    # تنظیم کارشناس فروش یکتا
                    if sales_agent:
                        new_purchase.unique_sales_agent = sales_agent
                        new_purchase.unique_sales_agent_code = sales_agent.factor_code
                    
                    new_purchase.full_clean()
                    new_purchase.save()
                    
                    # اضافه کردن کارشناس فروش به خرید (برای سازگاری با سیستم قدیمی)
                    if sales_agent:
                        new_purchase.sales_agent.add(sales_agent)
                    
                    messages.success(request, "خرید با موفقیت ثبت شد (بدون ارسال پیامک)")
                        
                except CargoProduct.DoesNotExist:
                    messages.error(request, "کوتاژ انتخاب شده یافت نشد")
                except (ValueError, ValidationError) as e:
                    messages.error(request, f"خطا در ثبت خرید: {e}")
            else:
                messages.error(request, "لطفاً تمام فیلدهای ضروری را پر کنید")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}&active_tab={active_tab}')

        # ثبت خرید خارج بازارگاه
        elif 'create_non_bazargah_purchase' in request.POST:
            active_tab = request.POST.get('active_tab', 'non_bazargah_purchases')
            
            # ایجاد فرم خرید خارج بازارگاه
            purchase_form = NonBazargahPurchaseForm(request.POST)
            
            if purchase_form.is_valid():
                try:
                    with transaction.atomic():
                        # ایجاد خرید جدید
                        new_purchase = purchase_form.save(commit=False)
                        new_purchase.customer = customer
                        new_purchase.type = 'non_bazaargah'
                        new_purchase.state = 'initiated'
                        
                        # تنظیم کارشناس فروش یکتا
                        if sales_agent:
                            new_purchase.unique_sales_agent = sales_agent
                            new_purchase.unique_sales_agent_code = sales_agent.factor_code
                        
                        # محاسبه وزن کل بر اساس واحد
                        unit = new_purchase.unit
                        quantity = new_purchase.quantity
                        
                        if unit == 'Kilo':
                            new_purchase.total_weight = quantity
                        elif unit == 'Ton':
                            new_purchase.total_weight = quantity * 1000  # تبدیل تن به کیلوگرم
                        elif unit == 'Kiseh' and new_purchase.bag_weight:
                            new_purchase.total_weight = quantity * new_purchase.bag_weight
                        
                        new_purchase.full_clean()
                        new_purchase.save()
                        
                        messages.success(request, f"خرید خارج بازارگاه '{new_purchase.product.name}' با موفقیت ثبت شد")
                        
                except Exception as e:
                    messages.error(request, f"خطا در ثبت خرید خارج بازارگاه: {str(e)}")
            else:
                # نمایش خطاهای فرم
                for field, errors in purchase_form.errors.items():
                    for error in errors:
                        messages.error(request, f"خطا در فیلد '{purchase_form.fields[field].label}': {error}")
            
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}&active_tab={active_tab}')

        # اضافه کردن شماره تلفن جدید
        elif 'add_phone' in request.POST:
            new_phone = request.POST.get('new_phone')
            phone_description = request.POST.get('phone_description', '').strip()
            
            if new_phone:
                try:
                    # تمیز کردن شماره تلفن
                    # تبدیل اعداد فارسی به انگلیسی
                    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                    english_digits = "0123456789"
                    translation_table = str.maketrans(persian_digits, english_digits)
                    clean_phone = new_phone.translate(translation_table)
                    
                    # پاکسازی شماره از کاراکترهای غیرعددی
                    clean_phone = ''.join(c for c in clean_phone if c.isdigit())
                    
                    # اگر با صفر شروع می‌شود، آن را حذف می‌کنیم
                    if clean_phone.startswith('0'):
                        clean_phone = clean_phone[1:]
                    
                    # حذف کد کشور ایران اگر وجود داشت
                    if clean_phone.startswith('98'):
                        clean_phone = clean_phone[2:]
                    
                    # بررسی اینکه شماره حداقل معقول باشه
                    if len(clean_phone) < 10:
                        messages.error(request, "شماره تلفن باید حداقل 10 رقم باشد")
                    else:
                        # بررسی تکراری نبودن شماره
                        existing_phone = PhoneNumber.objects.filter(number=clean_phone).first()
                        
                        if existing_phone:
                            if existing_phone.customer == customer:
                                messages.error(request, "این شماره قبلاً برای این مشتری ثبت شده است")
                            else:
                                messages.error(request, f"این شماره قبلاً برای مشتری '{existing_phone.customer.name}' ثبت شده است")
                        else:
                            # ایجاد شماره جدید
                            phone_obj = PhoneNumber(
                                number=clean_phone,
                                customer=customer,
                                is_primary=False,
                                sms_enabled=True,  # دیفالت روشن
                                description=phone_description if phone_description else None
                            )
                            phone_obj.save()
                            success_msg = f"شماره تلفن {clean_phone} با موفقیت اضافه شد"
                            if phone_description:
                                success_msg += f" (توضیحات: {phone_description})"
                            messages.success(request, success_msg)
                            
                except Exception as e:
                    messages.error(request, f"خطا در اضافه کردن شماره: {str(e)}")
            else:
                messages.error(request, "لطفاً شماره تلفن را وارد کنید")
                
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
        
        # تغییر وضعیت پیامک شماره تلفن
        elif 'toggle_sms' in request.POST:
            phone_id = request.POST.get('phone_id')
            try:
                phone_obj = PhoneNumber.objects.get(id=phone_id, customer=customer)
                phone_obj.sms_enabled = not phone_obj.sms_enabled
                phone_obj.save()
                status = "فعال" if phone_obj.sms_enabled else "غیرفعال"
                messages.success(request, f"ارسال پیامک برای شماره {phone_obj.number} {status} شد")
            except PhoneNumber.DoesNotExist:
                messages.error(request, "شماره یافت نشد")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

        # تنظیم شماره اصلی
        elif 'make_primary' in request.POST:
            phone_id = request.POST.get('make_primary')
            try:
                phone_obj = PhoneNumber.objects.get(id=phone_id, customer=customer)
                # حذف primary از شماره‌های قبلی
                customer.phone_numbers.update(is_primary=False)
                # تنظیم شماره جدید به عنوان primary
                phone_obj.is_primary = True
                phone_obj.save()
                messages.success(request, "شماره اصلی تغییر کرد")
            except PhoneNumber.DoesNotExist:
                messages.error(request, "شماره یافت نشد")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

        # ویرایش توضیحات شماره تلفن
        elif 'edit_phone_description' in request.POST:
            phone_id = request.POST.get('phone_id')
            new_description = request.POST.get('new_description', '').strip()
            try:
                phone_obj = PhoneNumber.objects.get(id=phone_id, customer=customer)
                phone_obj.description = new_description if new_description else None
                phone_obj.save()
                if new_description:
                    messages.success(request, f"توضیحات شماره {phone_obj.number} با موفقیت ذخیره شد")
                else:
                    messages.success(request, f"توضیحات شماره {phone_obj.number} حذف شد")
            except PhoneNumber.DoesNotExist:
                messages.error(request, "شماره یافت نشد")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

        # مدیریت پاپ‌آپ SMS
        elif 'sms_action' in request.POST:
            sms_action = request.POST.get('sms_action')
            selected_phones = request.POST.getlist('selected_phones')
            
            if not selected_phones:
                messages.error(request, "لطفاً حداقل یک شماره تلفن انتخاب کنید")
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
            
            # حذف شماره‌های تکراری و نرمال‌سازی
            normalized_phones = set()
            for phone in selected_phones:
                if phone:
                    phone_str = str(phone).strip()
                    # تبدیل اعداد فارسی به انگلیسی
                    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                    english_digits = "0123456789"
                    translation_table = str.maketrans(persian_digits, english_digits)
                    phone_str = phone_str.translate(translation_table)
                    
                    # حذف کاراکترهای غیرعددی
                    cleaned = ''.join(c for c in phone_str if c.isdigit())
                    
                    # نرمال‌سازی پیشوندها
                    if cleaned.startswith('0098'):
                        cleaned = cleaned[4:]
                    elif cleaned.startswith('98') and len(cleaned) == 12:
                        cleaned = cleaned[2:]
                    elif cleaned.startswith('0') and len(cleaned) == 11:
                        cleaned = cleaned[1:]
                    
                    # اعتبارسنجی نهایی
                    if len(cleaned) == 10 and cleaned.startswith('9') and cleaned.isdigit():
                        normalized_phones.add(cleaned)
            
            selected_phones = list(normalized_phones)
            
            if not selected_phones:
                messages.error(request, "هیچ شماره معتبری انتخاب نشده است")
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
            
            try:
                from sms_api.apis import queue_sms
                sent_count = 0
                
                if sms_action == 'purchase':
                    # ایجاد خرید جدید
                    cottage_number = request.POST.get('cottage_number')
                    weight = request.POST.get('weight')
                    use_custom_price = request.POST.get('use_custom_price')
                    custom_price = request.POST.get('custom_price')
                    
                    if cottage_number and weight:
                        try:
                            cargo = CargoProduct.objects.get(cottage=cottage_number, status=True)
                            
                            # تعیین قیمت
                            if use_custom_price and custom_price:
                                customer_price = int(custom_price)
                            else:
                                customer_price = cargo.customer_price
                            
                            # ایجاد خرید جدید
                            from core.PurchaseModel import Purchase
                            new_purchase = Purchase(
                                customer=customer,
                                cargo=cargo,
                                order_weight=int(weight),
                                customer_price=customer_price,
                                state='INITIATED'
                            )
                            
                            # تنظیم کارشناس فروش یکتا
                            if sales_agent:
                                new_purchase.unique_sales_agent = sales_agent
                                new_purchase.unique_sales_agent_code = sales_agent.factor_code
                            
                            new_purchase.full_clean()
                            new_purchase.save()
                            
                            # اضافه کردن کارشناس فروش به خرید
                            if sales_agent:
                                new_purchase.sales_agent.add(sales_agent)
                            
                            # ارسال پیامک خرید به شماره‌های انتخاب شده
                            message = f"سلام {customer.name}\nخرید شما ثبت شد:\nکوتاژ: {cottage_number}\nوزن: {weight} کیلوگرم\nفی: {customer_price:,} ریال\nکارشناس: {sales_agent.name}"
                            
                            for phone in selected_phones:
                                try:
                                    queue_sms(phone, message, notification_type='purchase_registered')
                                    sent_count += 1
                                except Exception as e:
                                    print(f"خطا در ارسال پیامک خرید به شماره {phone}: {e}")
                            
                            messages.success(request, f"خرید ثبت شد و پیامک به {sent_count} شماره ارسال شد")
                            
                        except CargoProduct.DoesNotExist:
                            messages.error(request, "کوتاژ انتخاب شده یافت نشد")
                        except (ValueError, ValidationError) as e:
                            messages.error(request, f"خطا در ثبت خرید: {e}")
                    else:
                        messages.error(request, "لطفاً تمام فیلدهای ضروری خرید را پر کنید")
                        
                elif sms_action == 'social':
                    # ارسال لینک شبکه‌های اجتماعی
                    social_media_message = """لینک شبکه‌های اجتماعی شرکت تأمین نهاده سیمرغ:

واتساپ: chat.whatsapp.com/DMqFJ2OUZXb9IA8GUqDMFH
بله: ble.ir/join/baS6duS998
روبیکا: rubika.ir/simurgh360
ایتا: eitaa.com/simurgh360
تلگرام: t.me/simurgh360
اینستاگرام: instagram.com/simurgh360
وبسایت: simurgh360.com
 """
                    
                    for phone in selected_phones:
                        try:
                            queue_sms(phone, social_media_message, notification_type='social_media_links')
                            sent_count += 1
                        except Exception as e:
                            print(f"خطا در ارسال پیامک شبکه‌های اجتماعی به شماره {phone}: {e}")
                    
                    messages.success(request, f"لینک شبکه‌های اجتماعی به {sent_count} شماره ارسال شد")
                    
                elif sms_action == 'followup':
                    # ارسال پیام پیگیری
                    followup_message = f"مشتری گرامی {customer.name}\nمشکل شما به واحد پیگیری منتقل شد و به‌زودی با شما تماس خواهیم گرفت.\nشرکت تأمین نهاده سیمرغ"
                    
                    for phone in selected_phones:
                        try:
                            queue_sms(phone, followup_message, notification_type='followup')
                            sent_count += 1
                        except Exception as e:
                            print(f"خطا در ارسال پیامک پیگیری به شماره {phone}: {e}")
                    
                    messages.success(request, f"پیام پیگیری به {sent_count} شماره ارسال شد")
                    
                elif sms_action == 'custom':
                    # ارسال پیامک سفارشی
                    custom_message = request.POST.get('custom_message', '').strip()
                    
                    if custom_message:
                        for phone in selected_phones:
                            try:
                                queue_sms(phone, custom_message, notification_type='custom')
                                sent_count += 1
                            except Exception as e:
                                print(f"خطا در ارسال پیامک سفارشی به شماره {phone}: {e}")
                        
                        messages.success(request, f"پیامک سفارشی به {sent_count} شماره ارسال شد")
                    else:
                        messages.error(request, "لطفاً متن پیامک را وارد کنید")
                        
            except Exception as e:
                messages.error(request, f"خطا در ارسال پیامک: {str(e)}")
                
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

    # دریافت داده‌ها برای نمایش
    calls = customer.get_calls_by_time() if customer else []
    tasks = customer.get_tasks_by_time() if customer else []
    purchases = customer.get_purchases_by_time() if customer else []
    non_bazargah_purchases = customer.non_bazargah_purchases_made.all().order_by('-created_at') if customer else []
    all_phone_numbers = customer.get_all_phone_numbers() if customer else []
    purchase_phone_numbers = customer.get_purchase_phone_numbers() if customer else []
    
    # صفحه‌بندی تسک‌ها
    if customer:
        from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
        task_paginator = Paginator(tasks, 10)
        task_page = request.GET.get('task_page', 1)
        try:
            tasks = task_paginator.page(task_page)
        except PageNotAnInteger:
            tasks = task_paginator.page(1)
        except EmptyPage:
            tasks = task_paginator.page(task_paginator.num_pages)
        
        # صفحه‌بندی خریدها
        purchase_paginator = Paginator(purchases, 10)
        purchase_page = request.GET.get('purchase_page', 1)
        try:
            purchases = purchase_paginator.page(purchase_page)
        except PageNotAnInteger:
            purchases = purchase_paginator.page(1)
        except EmptyPage:
            purchases = purchase_paginator.page(purchase_paginator.num_pages)
    
    # دریافت محصولات فعال برای نمایش در فرم خرید
    active_products = CargoProduct.get_active_products()
    active_non_bazargah_products = NonBazargahProduct.get_active_products()
    
    # ایجاد فرم خرید خارج بازارگاه
    non_bazargah_purchase_form = NonBazargahPurchaseForm()
    
    # بررسی آیا کاربر شماره معتبر وارد کرده و مشتری پیدا نشده
    search_valid_phone = False
    if query and customer is None:
        clean_phone, is_valid_phone = clean_and_validate_phone(query)
        search_valid_phone = is_valid_phone

    # اطمینان از اینکه form همیشه موجود باشد
    if form is None:
        if customer:
            form = CustomerForm(instance=customer, sales_agent=sales_agent)
        else:
            initial_data = {'phone_number': query}
            if assignment_id:
                initial_data['assignment_id'] = assignment_id
            form = CustomerForm(initial=initial_data, sales_agent=sales_agent)
    if customer:
        logger.debug(f"phones: {all_phone_numbers}, phone function: {customer.get_all_phone_numbers()}")
    context = {
        'form': form,
        'customer': customer,
        'calls': calls,
        'tasks': tasks,
        'purchases': purchases,
        'non_bazargah_purchases': non_bazargah_purchases,
        'all_phone_numbers': all_phone_numbers,
        'purchase_phone_numbers': purchase_phone_numbers,
        'search_query': query,
        'assignment_id': assignment_id,
        'active_products': active_products,
        'active_non_bazargah_products': active_non_bazargah_products,
        'non_bazargah_purchase_form': non_bazargah_purchase_form,
        'is_new_customer': customer is None,
        'search_valid_phone': search_valid_phone,
        'sales_agent': sales_agent,
    }

    return render(request, 'general_customer_CRUD_view.html', context)

@role_required('sales_agent', 'admin')
@login_required
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
    messages.warning(request, "this function is not implemented yet")
    return None
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

@role_required('sales_agent', 'admin')
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

@role_required('sales_agent', 'admin')
@login_required
def update_task_order(request):
    if request.method == "POST":
        task_order = request.POST.getlist('task_order[]')
        for i, task_id in enumerate(task_order):
            Task.objects.filter(id=task_id).update(order=i)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@role_required('sales_agent', 'admin')
@login_required
def get_purchase_history(request):
    """
    نمایش تاریخچه خرید برای یک مشتری با قابلیت صفحه‌بندی AJAX
    """
    customer_id = request.GET.get('customer_id')
    if not customer_id:
        return JsonResponse({'status': 'error', 'message': 'شناسه مشتری وجود ندارد'}, status=400)
    
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        sales_agent = SalesAgent.objects.get(user=request.user)
        check_customer_sales_agent(customer=customer, sales_agent=sales_agent)

        # بارگیری تاریخچه خرید
        purchases = customer.get_purchases_by_time()
        
        # صفحه‌بندی
        page = request.GET.get('page', 1)
        paginator = Paginator(purchases, 9) 
        
        try:
            purchases_page = paginator.page(page)
        except PageNotAnInteger:
            purchases_page = paginator.page(1)
        except EmptyPage:
            purchases_page = paginator.page(paginator.num_pages)
        
        # ساخت HTML برای تاریخچه خرید
        purchases_html = render_to_string('partials/purchase_history_items.html', {
            'purchases': purchases_page,
            'customer': customer
        })
        
        # ساخت HTML برای پیجینیشن
        pagination_html = render_to_string('partials/purchase_pagination.html', {
            'purchases': purchases_page,
            'customer': customer
        })
        
        return JsonResponse({
            'status': 'success',
            'html': purchases_html,
            'pagination': pagination_html
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# ----------------- Call Session Management -----------------
@role_required('sales_agent', 'admin')
@login_required
def add_call(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        call_type = request.POST.get('call_type')
        call_status = request.POST.get('call_status')
        note = request.POST.get('note')
        active_tab = request.POST.get('active_tab', 'calls')
        
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
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}&active_tab={active_tab}')

# ----------------- Support Task Management -----------------
@role_required('sales_agent', 'admin')
@login_required
def create_support_task_from_customer(request):
    """ایجاد تسک کارشناس پشتیبانی از صفحه مشتری"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'فقط درخواست POST مجاز است'}, status=405)
    
    try:
        # دریافت داده‌ها
        customer_id = request.POST.get('customer_id')
        support_agent_id = request.POST.get('support_agent_id')
        description = request.POST.get('description', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        send_sms = request.POST.get('send_sms', 'false') == 'true'
        
        # اعتبارسنجی
        if not customer_id:
            return JsonResponse({'status': 'error', 'message': 'شناسه مشتری الزامی است'}, status=400)
        
        if not support_agent_id:
            return JsonResponse({'status': 'error', 'message': 'انتخاب کارشناس پشتیبانی الزامی است'}, status=400)
        
        if not description:
            return JsonResponse({'status': 'error', 'message': 'توضیحات الزامی است'}, status=400)
        
        # دریافت مشتری
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'مشتری یافت نشد'}, status=404)
        
        # دریافت کارشناس پشتیبانی
        try:
            support_agent = SupportAgent.objects.get(id=support_agent_id)
        except SupportAgent.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'کارشناس پشتیبانی یافت نشد'}, status=404)
        
        # ایجاد تسک کارشناس پشتیبانی
        support_task = SupportAgentTask.objects.create(
            customer=customer,
            support_agent=support_agent,
            description=description,
            phone_number=phone_number or customer.get_primary_phone(),
            urgency_level=9,  # سطح فوریت بالا
        )
        
        # ارسال پیامک به مشتری (در صورت انتخاب)
        if send_sms and (phone_number or customer.get_primary_phone()):
            try:
                from sms_api.apis import queue_sms
                customer_phone = phone_number or customer.get_primary_phone()
                
                sms_message = f"""مشتری گرامی {customer.name}
درخواست شما به واحد پشتیبانی ارجاع داده شد و به‌زودی با شما تماس خواهیم گرفت.
شماره پیگیری: {support_task.id}
شرکت تأمین نهاده سیمرغ"""
                
                queue_sms(
                    phone_number=customer_phone,
                    message=sms_message,
                    notification_type='support_task'
                )
            except Exception as e:
                # در صورت خطا در ارسال پیامک، تسک همچنان ایجاد می‌شود
                print(f"Error sending SMS to customer: {e}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'تسک کارشناس پشتیبانی با موفقیت ایجاد شد',
            'task_id': support_task.id
        })
        
    except Exception as e:
        print(f"Error creating support task: {e}")
        return JsonResponse({
            'status': 'error',
            'message': f'خطا در ایجاد تسک: {str(e)}'
        }, status=500)