from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from major.models.NonBazargahPurchase import NonBazargahPurchase
from major.models.NonBazargahAllocation import NonBazargahAllocation
from major.models.NonBazargahProduct import NonBazargahProduct
from core.CustomerModel import Customer
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from ERP.views.managers_profile_view import get_client_ip
from ERP.models.NotificationService import NotificationService

from collections import OrderedDict
import logging

logger = logging.getLogger("major_non_bazargah_crud")


class NonBazargahAllocationForm(forms.ModelForm):
    """فرم تخصیص آدرس - جایگزین دسته‌بندی اطلاعات تحویل"""
    
    class Meta:
        model = NonBazargahAllocation
        fields = [
            'delivery_address', 'delivery_postal_code', 'delivery_receiver_name',
            'coordination_phone', 'allocated_weight', 'notes'
        ]
        widgets = {
            'delivery_address': forms.Textarea(attrs={'rows': 3, 'placeholder': 'آدرس کامل محل تحویل کالا'}),
            'delivery_postal_code': forms.TextInput(attrs={'placeholder': 'کد پستی 10 رقمی'}),
            'delivery_receiver_name': forms.TextInput(attrs={'placeholder': 'نام شخص گیرنده کالا'}),
            'coordination_phone': forms.TextInput(attrs={'placeholder': 'شماره تماس برای هماهنگی'}),
            'allocated_weight': forms.NumberInput(attrs={'placeholder': 'وزن به کیلوگرم'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'توضیحات اضافی (اختیاری)'}),
        }
        labels = {
            'delivery_address': 'آدرس تحویل',
            'delivery_postal_code': 'کد پستی',
            'delivery_receiver_name': 'نام گیرنده',
            'coordination_phone': 'شماره هماهنگی',
            'allocated_weight': 'وزن تخصیص یافته (کیلوگرم)',
            'notes': 'توضیحات',
        }
    
    def __init__(self, *args, purchase=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.purchase = purchase
        
        if purchase:
            # تنظیم حداکثر وزن قابل تخصیص
            remaining_weight = purchase.get_remaining_weight_for_allocation()
            if remaining_weight > 0:
                self.fields['allocated_weight'].help_text = f'حداکثر وزن قابل تخصیص: {remaining_weight} کیلوگرم'
                self.fields['allocated_weight'].widget.attrs['max'] = remaining_weight
            else:
                self.fields['allocated_weight'].help_text = 'همه وزن تخصیص شده است'
                self.fields['allocated_weight'].widget.attrs['readonly'] = True
                self.fields['allocated_weight'].widget.attrs['disabled'] = True
    
    def clean_allocated_weight(self):
        allocated_weight = self.cleaned_data.get('allocated_weight')
        
        # استفاده از purchase که در __init__ تنظیم شده
        if self.purchase and allocated_weight:
            # محاسبه وزن باقی‌مانده
            remaining_weight = self.purchase.get_remaining_weight_for_allocation()
            
            # اگر در حال ویرایش هستیم، وزن فعلی instance را به باقی‌مانده اضافه کنیم
            if self.instance and self.instance.pk and hasattr(self.instance, 'allocated_weight'):
                remaining_weight += (self.instance.allocated_weight or 0)
            
            if allocated_weight > remaining_weight:
                raise ValidationError(f'وزن تخصیص یافته نمی‌تواند از {remaining_weight} کیلوگرم بیشتر باشد')
        
        return allocated_weight


class RoleBasedNonBazargahPurchaseForm(forms.ModelForm):
    # فیلد بایپس برای اعتبارسنجی
    bypass_validation = forms.BooleanField(required=False, widget=forms.HiddenInput())
    
    class Meta:
        model = NonBazargahPurchase
        fields = '__all__'
        widgets = {
            'payment_document': forms.FileInput(attrs={'accept': '.pdf,.jpg,.jpeg,.png'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'logistics_notes': forms.Textarea(attrs={'rows': 2}),
            'payment_notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # اطمینان از وجود مقادیر اولیه (جلوگیری از خطای required)
        if self.instance and self.instance.pk:
            # تنظیم فی خرید از محصول در instance
            if self.instance.product and not self.instance.company_price:
                product_price = self.instance.get_product_purchase_price()
                if product_price:
                    self.instance.company_price = product_price
        
        # حذف فیلدهای قیمت از فرم (اطلاعات محرمانه)
        price_fields = ['company_price']
        for field_name in price_fields:
            if field_name in self.fields:
                del self.fields[field_name]
        
        # فیلدهای همیشه قفل را اختیاری کن
        readonly_fields = ['customer', 'product', 'quantity', 'customer_price', 'amount_paid', 'bag_weight', 'unit']
        for field_name in readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
                # تنظیم مقدار اولیه برای فیلدهای readonly
                if self.instance and self.instance.pk and hasattr(self.instance, field_name):
                    self.initial[field_name] = getattr(self.instance, field_name)
        
        # تنظیم فیلدها بر اساس نقش کاربر
        if user_role == 'sales_agent':
            # کارشناس فروش فقط اطلاعات اولیه و اطلاعات خریدار
            allowed_fields = [
                'customer', 'product', 'unit', 'quantity', 'bag_weight',
                'customer_price', 'description',
                'buyer_name', 'buyer_postal_code', 'buyer_national_id',
                'buyer_user_type', 'address', 'tahvil_phone_number', 
                'code_melli_tahvil', 'barbary_confidential_number', 
                'barbary_customer_number', 'vehicle_type'
            ]
            
        elif user_role == 'financial_manager':
            # مدیر مالی - تایید پرداخت و فیلدهای مالی
            allowed_fields = [
                'customer', 'product', 'unit', 'quantity',
                'customer_price', 'amount_paid', 'payment_document',
                'payment_notes', 'description', 'state'
            ]
            
        elif user_role == 'logistics_manager':
            # مدیر لجستیک - مدیریت وزن‌گیری و لجستیک
            allowed_fields = [
                'customer', 'product', 'unit', 'quantity',
                'customer_price', 'logistics_notes', 'empty_weight', 'loaded_weight',
                'delivered_weight', 'weight_difference', 'description',
                'state', 'vehicle_type', 'barbary_confidential_number',
                'barbary_customer_number', 'warehouse_contact_person',
                'warehouse_contact_phone'
            ]
            
        elif user_role == 'admin':
            # ادمین - دسترسی کامل
            allowed_fields = list(self.fields.keys())
            
        else:
            # سایر نقش‌ها - فقط مشاهده
            allowed_fields = []
        
        # اضافه کردن bypass_validation
        allowed_fields.append('bypass_validation')
        
        # حذف فیلدهای غیر مجاز
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]
        
        # قفل کردن فیلدها بر اساس وضعیت
        self._lock_fields_based_on_state()
        
        # مرتب کردن فیلدها
        custom_order_fields = [
            'customer', 'product', 'unit', 'quantity', 'bag_weight',
            'customer_price', 'amount_paid',
            'buyer_name', 'buyer_postal_code', 'buyer_national_id',
            'buyer_user_type', 'address', 'tahvil_phone_number', 
            'code_melli_tahvil', 'warehouse_contact_person', 
            'warehouse_contact_phone', 'empty_weight', 'loaded_weight',
            'delivered_weight', 'payment_document', 'state',
            'description', 'logistics_notes', 'payment_notes'
        ]
        ordered_field_names = [f for f in custom_order_fields if f in self.fields]
        self.fields = OrderedDict((f, self.fields[f]) for f in ordered_field_names)
    
    def _lock_fields_based_on_state(self):
        """قفل کردن فیلدها بر اساس وضعیت خرید"""
        if not self.instance or not self.instance.pk:
            return
            
        state = self.instance.state
        
        # فیلدهای همیشه قفل (غیرقابل ادیت)
        always_readonly_fields = [
            'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
            'bag_weight', 'unit', 'state'
        ]
        for field_name in always_readonly_fields:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'readonly': 'readonly', 'disabled': True
                })
        
        # فیلدهای اساسی بعد از تایید پرداخت قفل می‌شوند
        payment_verified_states = [
            'payment_verified', 'address_assigned', 'sent_to_warehouse',
            'carrier_notified', 'vehicle_arrived', 'empty_weighed',
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]
        
        if state in payment_verified_states:
            readonly_fields = [
                'product'
            ]
            for field_name in readonly_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
        
        # فیلدهای اطلاعات خریدار بعد از تخصیص آدرس قفل می‌شوند
        address_assigned_states = [
            'address_assigned', 'sent_to_warehouse', 'carrier_notified',
            'vehicle_arrived', 'empty_weighed', 'loaded_weighed',
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]
        
        if state in address_assigned_states:
            buyer_info_fields = [
                'buyer_name', 'buyer_postal_code', 'buyer_national_id',
                'buyer_user_type', 'address', 'tahvil_phone_number', 
                'code_melli_tahvil'
            ]
            for field_name in buyer_info_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
        
        # فیلدهای وزن‌گیری فقط در مراحل مناسب قابل ویرایش
        weight_fields = ['empty_weight', 'loaded_weight', 'delivered_weight']
        if state not in ['vehicle_arrived', 'empty_weighed', 'loaded_weighed', 'barnameh_issued']:
            for field_name in weight_fields:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs.update({
                        'readonly': 'readonly', 'disabled': True
                    })
    
    def clean(self):
        cleaned_data = super().clean()
        
        # بایپس اعتبارسنجی برای دکمه‌های اکشن
        if cleaned_data.get('bypass_validation'):
            # بازگردانی مقادیر فیلدهای readonly از instance اصلی
            if self.instance and self.instance.pk:
                readonly_fields = [
                    'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
                    'bag_weight', 'unit', 'state'
                ]
                for field_name in readonly_fields:
                    if hasattr(self.instance, field_name):
                        cleaned_data[field_name] = getattr(self.instance, field_name)
            
            return cleaned_data
        
        # تنظیم فی خرید از محصول (فقط برای instance، نه برای فرم)
        if self.instance and self.instance.pk and self.instance.product:
            product_price = self.instance.get_product_purchase_price()
            if product_price:
                # تنظیم مستقیم در instance، نه در cleaned_data
                self.instance.company_price = product_price
        
        # اطمینان از وجود customer_price
        customer_price = cleaned_data.get('customer_price')
        
        # اگر فیلدهای readonly خالی هستند، از instance بگیر
        if self.instance and self.instance.pk:
            if not customer_price:
                cleaned_data['customer_price'] = self.instance.customer_price
            
            # اطمینان از وجود سایر فیلدهای ضروری
            essential_fields = ['customer', 'product', 'quantity', 'unit', 'bag_weight', 'amount_paid']
            for field_name in essential_fields:
                if not cleaned_data.get(field_name) and hasattr(self.instance, field_name):
                    cleaned_data[field_name] = getattr(self.instance, field_name)
        
        # اعتبارسنجی وزن‌ها
        empty_weight = cleaned_data.get('empty_weight')
        loaded_weight = cleaned_data.get('loaded_weight')
        
        if empty_weight and loaded_weight and loaded_weight <= empty_weight:
            raise ValidationError('وزن پر باید از وزن خالی بیشتر باشد')
        
        return cleaned_data


@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
@login_required
def non_bazargah_purchase_CRUD_view(request, purchase_id):
    """صفحه مدیریت خرید خارج بازارگاه"""
    logger.warning(f"دسترسی به خرید خارج بازارگاه {purchase_id} توسط {request.user.username}, IP: {get_client_ip(request)}")
    
    purchase = get_object_or_404(NonBazargahPurchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کارشناس فروش
    if user_role == 'sales_agent':
        if not purchase.customer or not hasattr(request.user, 'sales_agent'):
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
        
        # بررسی که کارشناس فروش مربوط به این مشتری است
        if not purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
    
    # تعریف مراحل پیشرفت
    progress_steps = [
        {'name': 'شروع شده', 'status': True},
        {'name': 'انتظار تایید پرداخت', 'status': purchase.state != 'initiated'},
        {'name': 'تایید پرداخت', 'status': purchase.state in [
            'payment_verified', 'address_assigned', 'sent_to_warehouse',
            'carrier_notified', 'vehicle_arrived', 'empty_weighed',
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'تخصیص آدرس', 'status': purchase.state in [
            'address_assigned', 'sent_to_warehouse', 'carrier_notified',
            'vehicle_arrived', 'empty_weighed', 'loaded_weighed',
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'ارسال به انبار', 'status': purchase.state in [
            'sent_to_warehouse', 'carrier_notified', 'vehicle_arrived',
            'empty_weighed', 'loaded_weighed', 'barnameh_issued',
            'delivered', 'purchase_closed'
        ]},
        {'name': 'اعلام بار به باربری', 'status': purchase.state in [
            'carrier_notified', 'vehicle_arrived', 'empty_weighed',
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'ورود ماشین', 'status': purchase.state in [
            'vehicle_arrived', 'empty_weighed', 'loaded_weighed',
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'وزن خالی', 'status': purchase.state in [
            'empty_weighed', 'loaded_weighed', 'barnameh_issued',
            'delivered', 'purchase_closed'
        ]},
        {'name': 'بارگیری و وزن پر', 'status': purchase.state in [
            'loaded_weighed', 'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'صدور بارنامه', 'status': purchase.state in [
            'barnameh_issued', 'delivered', 'purchase_closed'
        ]},
        {'name': 'تحویل به مشتری', 'status': purchase.state in [
            'delivered', 'purchase_closed'
        ]},
        {'name': 'بستن خرید', 'status': purchase.state == 'purchase_closed'},
    ]
    
    # دریافت تخصیص‌های موجود
    allocations = purchase.allocations.all().order_by('-id')
    
    # محاسبه وزن‌های کلیدی
    total_allocated_weight = purchase.get_total_allocated_weight() or 0
    remaining_weight = purchase.get_remaining_weight_for_allocation() or 0
    
    # تبدیل وزن درخواستی به کیلوگرم برای نمایش
    requested_weight_kg = purchase.quantity or 0
    if purchase.unit == 'Ton' and purchase.quantity:
        requested_weight_kg = purchase.quantity * 1000
    elif purchase.unit == 'Kiseh' and purchase.quantity and purchase.bag_weight:
        requested_weight_kg = purchase.quantity * purchase.bag_weight
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        
        # بررسی دکمه‌های اکشن
        action_buttons = [
            'approve_payment', 'add_allocation', 'approve_allocations', 'send_to_warehouse',
            'notify_carrier', 'confirm_vehicle_arrival', 'record_empty_weight',
            'record_loaded_weight', 'issue_barnameh', 'confirm_delivery',
            'close_purchase', 'cancel_purchase', 'archive_purchase', 'upload_document',
            'delete_allocation'
        ]
        
        is_action_button_pressed = any(action in request.POST for action in action_buttons)
        
        # پردازش آپلود مدرک
        if 'upload_document' in request.POST:
            document_file = request.FILES.get('payment_document_upload')
            if document_file:
                purchase.payment_document = document_file
                # تنظیم company_price از محصول
                if purchase.product:
                    product_price = purchase.get_product_purchase_price()
                    if product_price:
                        purchase.company_price = product_price
                purchase.save()
                messages.success(request, 'مدرک پرداخت با موفقیت بارگذاری شد - حالا می‌توانید پرداخت را تایید کنید')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            else:
                messages.error(request, 'لطفاً یک فایل انتخاب کنید')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش اضافه کردن تخصیص جدید
        if 'add_allocation' in request.POST and user_role in ['logistics_manager', 'admin']:
            if not purchase.can_assign_addresses():
                messages.error(request, 'برای تخصیص آدرس ابتدا باید پرداخت تایید شود')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            
            # ایجاد فرم با داده‌های POST و تنظیم purchase
            allocation_form_data = NonBazargahAllocationForm(request.POST, purchase=purchase)
            if allocation_form_data.is_valid():
                try:
                    allocation = allocation_form_data.save(commit=False)
                    allocation.purchase = purchase  # تنظیم صریح خرید
                    allocation.save()
                    messages.success(request, f'تخصیص جدید با وزن {allocation.allocated_weight} کیلوگرم اضافه شد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except Exception as e:
                    messages.error(request, f'خطا در ذخیره تخصیص: {str(e)}')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
            else:
                for field, errors in allocation_form_data.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
                return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        # پردازش حذف تخصیص
        if 'delete_allocation' in request.POST and user_role in ['logistics_manager', 'admin']:
            allocation_id = request.POST.get('allocation_id')
            if allocation_id:
                try:
                    allocation = NonBazargahAllocation.objects.get(id=allocation_id, purchase=purchase)
                    allocation.delete()
                    messages.success(request, 'تخصیص حذف شد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                except NonBazargahAllocation.DoesNotExist:
                    messages.error(request, 'تخصیص مورد نظر یافت نشد')
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
        
        if is_action_button_pressed:
            post_data['bypass_validation'] = 'true'
            # برای دکمه‌های اکشن، اطمینان از وجود فیلدهای ضروری
            if not post_data.get('customer_price'):
                post_data['customer_price'] = purchase.customer_price
            if not post_data.get('quantity'):
                post_data['quantity'] = purchase.quantity
            if not post_data.get('unit'):
                post_data['unit'] = purchase.unit
            if not post_data.get('bag_weight'):
                post_data['bag_weight'] = purchase.bag_weight
            if not post_data.get('amount_paid'):
                post_data['amount_paid'] = purchase.amount_paid
            
            # تنظیم قیمت‌ها از محصول (فقط customer_price در فرم)
            if purchase.customer_price:
                post_data['customer_price'] = purchase.customer_price
        
        form = RoleBasedNonBazargahPurchaseForm(post_data, request.FILES, instance=purchase, user_role=user_role)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # پردازش اکشن‌های مختلف
                    action_taken = False
                    
                    # اکشن‌های مدیر مالی
                    if user_role in ['financial_manager', 'admin']:
                        if purchase.state in ['initiated', 'payment_verification_pending'] and 'approve_payment' in request.POST:
                            # بررسی وجود مدرک پرداخت
                            if not purchase.payment_document:
                                messages.error(request, 'برای تایید پرداخت ابتدا باید مدرک پرداخت آپلود شود')
                            else:
                                purchase.state = 'payment_verified'
                                purchase.payment_verified_by = request.user
                                purchase.payment_verified_at = timezone.now()
                                action_taken = True
                                messages.success(request, 'پرداخت با موفقیت تایید شد')
                    
                    # اکشن‌های مدیر لجستیک
                    if user_role in ['logistics_manager', 'admin']:
                        if purchase.state == 'payment_verified' and 'approve_allocations' in request.POST:
                            logger.info(f"تلاش برای تایید تخصیص‌ها - خرید {purchase.id}")
                            # بررسی اینکه آیا همه وزن تخصیص شده است
                            if remaining_weight > 0:
                                logger.warning(f"وزن باقی‌مانده: {remaining_weight}")
                                messages.error(request, f'هنوز {remaining_weight} کیلوگرم وزن برای تخصیص باقی مانده است')
                            elif not allocations.exists():
                                logger.warning("هیچ تخصیصی وجود ندارد")
                                messages.error(request, 'ابتدا باید حداقل یک تخصیص اضافه کنید')
                            else:
                                try:
                                    # تغییر مستقیم وضعیت بدون استفاده از متد approve_all_allocations
                                    logger.info(f"تغییر وضعیت خرید {purchase.id} به address_assigned")
                                    purchase.state = 'address_assigned'
                                    purchase.save()
                                    action_taken = True
                                    messages.success(request, 'همه تخصیص‌ها تایید شد و وضعیت خرید تغییر کرد')
                                    logger.info(f"وضعیت خرید {purchase.id} با موفقیت تغییر کرد")
                                except Exception as e:
                                    logger.error(f"خطا در تایید تخصیص‌ها: {str(e)}")
                                    messages.error(request, f'خطا در تایید تخصیص‌ها: {str(e)}')
                        
                        elif purchase.state == 'address_assigned' and 'send_to_warehouse' in request.POST:
                            purchase.state = 'sent_to_warehouse'
                            action_taken = True
                            messages.success(request, 'اطلاعات به انبار ارسال شد')
                        
                        elif purchase.state == 'sent_to_warehouse' and 'notify_carrier' in request.POST:
                            purchase.state = 'carrier_notified'
                            action_taken = True
                            messages.success(request, 'بار به باربری اعلام شد')
                        
                        elif purchase.state == 'carrier_notified' and 'confirm_vehicle_arrival' in request.POST:
                            purchase.state = 'vehicle_arrived'
                            action_taken = True
                            messages.success(request, 'ورود ماشین تایید شد')
                        
                        elif purchase.state == 'vehicle_arrived' and 'record_empty_weight' in request.POST:
                            purchase.state = 'empty_weighed'
                            action_taken = True
                            messages.success(request, 'وزن خالی ثبت شد')
                        
                        elif purchase.state == 'empty_weighed' and 'record_loaded_weight' in request.POST:
                            purchase.state = 'loaded_weighed'
                            action_taken = True
                            messages.success(request, 'وزن پر ثبت شد')
                        
                        elif purchase.state == 'loaded_weighed' and 'issue_barnameh' in request.POST:
                            purchase.state = 'barnameh_issued'
                            action_taken = True
                            messages.success(request, 'بارنامه صادر شد')
                        
                        elif purchase.state == 'barnameh_issued' and 'confirm_delivery' in request.POST:
                            purchase.state = 'delivered'
                            action_taken = True
                            messages.success(request, 'تحویل به مشتری تایید شد')
                        
                        elif purchase.state == 'delivered' and 'close_purchase' in request.POST:
                            purchase.state = 'purchase_closed'
                            action_taken = True
                            messages.success(request, 'خرید بسته شد')
                    
                    # اکشن‌های ادمین
                    if user_role == 'admin':
                        if 'cancel_purchase' in request.POST:
                            purchase.state = 'canceled'
                            action_taken = True
                            messages.success(request, 'خرید لغو شد')
                        
                        elif 'archive_purchase' in request.POST:
                            purchase.state = 'archived'
                            action_taken = True
                            messages.success(request, 'خرید آرشیو شد')
                    
                    # ذخیره فرم فقط اگر اکشن انجام نشده باشد
                    if not action_taken:
                        # فیلدهای قفل شده که نباید تغییر کنند
                        locked_fields = [
                            'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
                            'bag_weight', 'unit', 'state'
                        ]
                        
                        # ذخیره مقادیر اصلی فیلدهای قفل شده
                        original_values = {}
                        for field_name in locked_fields:
                            if hasattr(purchase, field_name):
                                original_values[field_name] = getattr(purchase, field_name)
                        
                        # ذخیره فرم
                        purchase_instance = form.save(commit=False)
                        
                        # بازگردانی مقادیر اصلی فیلدهای قفل شده
                        for field_name, original_value in original_values.items():
                            setattr(purchase_instance, field_name, original_value)
                        
                        # تنظیم فی خرید از محصول
                        if purchase_instance.product:
                            product_price = purchase_instance.get_product_purchase_price()
                            if product_price:
                                purchase_instance.company_price = product_price
                        
                        purchase_instance.save()
                        messages.success(request, 'تغییرات با موفقیت اعمال شد')
                    else:
                        # اگر اکشن انجام شده، فقط ذخیره فرم بدون تغییر فیلدهای قفل شده
                        # فیلدهای قفل شده که نباید تغییر کنند
                        locked_fields = [
                            'customer', 'product', 'quantity', 'customer_price', 'amount_paid', 
                            'bag_weight', 'unit'
                        ]
                        
                        # ذخیره مقادیر اصلی فیلدهای قفل شده
                        original_values = {}
                        for field_name in locked_fields:
                            if hasattr(purchase, field_name):
                                original_values[field_name] = getattr(purchase, field_name)
                        
                        # ذخیره فرم
                        purchase_instance = form.save(commit=False)
                        
                        # بازگردانی مقادیر اصلی فیلدهای قفل شده
                        for field_name, original_value in original_values.items():
                            setattr(purchase_instance, field_name, original_value)
                        
                        # تنظیم فی خرید از محصول
                        if purchase_instance.product:
                            product_price = purchase_instance.get_product_purchase_price()
                            if product_price:
                                purchase_instance.company_price = product_price
                        
                        purchase_instance.save()
                    
                    return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
                    
            except ValidationError as e:
                if hasattr(e, 'message'):
                    messages.error(request, e.message)
                else:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, error)
            except Exception as e:
                logger.error(f"خطا در پردازش خرید خارج بازارگاه {purchase_id}: {str(e)}")
                messages.error(request, f'خطا: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = RoleBasedNonBazargahPurchaseForm(instance=purchase, user_role=user_role)
    
    # فرم تخصیص جدید
    allocation_form = NonBazargahAllocationForm(purchase=purchase)
    
    # دریافت نوتیفیکیشن‌ها
    notifications = NotificationService.get_unread_notifications(request.user)
    
    context = {
        'purchase': purchase,
        'form': form,
        'allocation_form': allocation_form,
        'allocations': allocations,
        'total_allocated_weight': total_allocated_weight,
        'remaining_weight': remaining_weight,
        'requested_weight_kg': requested_weight_kg,
        'progress_steps': progress_steps,
        'user_role': user_role,
        'notifications': notifications,
    }
    
    return render(request, 'non_bazargah_purchase_CRUD_view.html', context)


@role_required('admin', 'logistics_manager', 'sales_agent')
@login_required
def delete_non_bazargah_purchase_view(request, purchase_id):
    """حذف خرید خارج بازارگاه"""
    logger.warning(f"درخواست حذف خرید خارج بازارگاه {purchase_id} توسط {request.user.username} با IP {get_client_ip(request)}")
    
    purchase = get_object_or_404(NonBazargahPurchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کارشناس فروش
    if user_role == 'sales_agent':
        if not purchase.customer or not hasattr(request.user, 'sales_agent'):
            messages.error(request, 'شما اجازه حذف این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
        
        if not purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
            messages.error(request, 'شما اجازه حذف این خرید را ندارید.')
            return redirect('non_bazargah_purchase_list')
    
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, 'خرید با موفقیت حذف شد')
        return redirect('non_bazargah_purchase_list')
    
    context = {
        'purchase': purchase,
    }
    return render(request, 'confirm_delete_non_bazargah.html', context)


# View قدیمی آپلود مدرک - حذف شده چون حالا درون فرم اصلی handle می‌شود
# @role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
# @login_required  
# @csrf_exempt
# def upload_non_bazargah_document(request, purchase_id):
#     """آپلود مدارک برای خرید خارج بازارگاه - منسوخ شده"""
#     return redirect('non_bazargah_purchase_CRUD', purchase_id=purchase_id)
