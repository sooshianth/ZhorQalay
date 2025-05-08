from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import ValidationError
from core._models import Purchase
from core.PurchaseModel import PurchaseHistory, PurchaseStateChange, ShenaseTakhsis, PurchaseReceipts
from django.http import HttpResponse
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
import os
import jdatetime
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT
import uuid
from django.utils.text import slugify
import mimetypes
from django.utils import timezone
from ERP.models.NotificationService import NotificationService

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    BIDI_ENABLED = True
except ImportError:
    BIDI_ENABLED = False

def determine_user_role(user):
    """
    تشخیص نقش کاربر براساس روابط او
    به جای بررسی مستقیم role که وجود ندارد، روابط بررسی می‌شود
    نقش لجستیک بر فروش ارجحیت دارد
    """
    if hasattr(user, 'financial_manager') and user.financial_manager is not None:
        return 'financial_manager'
    elif hasattr(user, 'logistics_manager') and user.logistics_manager is not None:
        return 'logistics_manager'
    elif hasattr(user, 'sales_agent') and user.sales_agent is not None:
        return 'sales_agent'
    elif hasattr(user, 'support_agent') and user.support_agent is not None:
        return 'support_agent'
    elif user.is_superuser:
        # مدیر ارشد دسترسی کامل دارد
        return 'admin'
    return None

class RoleBasedPurchaseForm(forms.ModelForm):
    # اضافه کردن فیلد برای بایپس اعتبارسنجی هنگام تغییر وضعیت
    bypass_validation = forms.BooleanField(required=False, widget=forms.HiddenInput())
    
    # فیلد چندگانه برای شناسه‌های تخصیص
    allocation_ids = forms.CharField(
        label="شناسه‌های تخصیص (هر شناسه در یک خط جدید)",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'هر شناسه تخصیص را در یک خط وارد کنید', 'dir': 'ltr'}),
        required=False
    )
    
    class Meta:
        model = Purchase
        fields = '__all__'
        exclude = ['shenase_takhsis']  # حذف فیلد قدیمی شناسه تخصیص
    
    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        
        # اگر این یک فرم ویرایش است، شناسه های تخصیص موجود را بازیابی کن
        if self.instance.pk:
            # بازیابی شناسه‌های تخصیص موجود
            existing_allocation_ids = ShenaseTakhsis.objects.filter(purchase=self.instance)
            if existing_allocation_ids.exists():
                self.fields['allocation_ids'].initial = '\n'.join([item.code for item in existing_allocation_ids])
        
        if user_role == 'sales_agent' or user_role == 'admin':
            allowed_fields = [
                'order_weight', 'delivered_weight', 'description', 'tracking_number', 'purchase_date', 'purchase_number', 'barnameh', 
                'payment_method', 'customer_price','amount_paid', 'cargo', 'allocation_ids', 'code_melli_tahvil', 
                'bazaargah_phone_number', 'tahvil_phone_number',
            ]
        elif user_role == 'logistics_manager':
            allowed_fields = [
                'order_weight', 'delivered_weight', 'description', 'tracking_number', 'purchase_number', 'amount_paid', 'barnameh', 
                'customer_price', 'payment_method', 'cargo', 'allocation_ids', 'code_melli_tahvil', 
                'bazaargah_phone_number', 'tahvil_phone_number', 'address',
            ]
        elif user_role == 'financial_manager':
            allowed_fields = [
                'description', 'payment_method', 'company_price', 'customer_price', 'amount_paid', 'barnameh', 
                'cargo', 'purchase_date', 'purchase_number', 'tracking_number', 'order_weight', 'delivered_weight'
            ]
        else:
            allowed_fields = []
        
        # اگر بارنامه صادر شده باشد، فیلدهای اختلاف را نشان بده
        if True or self.instance.state == 'BARNAMEH_ISSUED':
            allowed_fields += ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
            
        # اضافه کردن فیلد bypass_validation به لیست فیلدهای مجاز
        allowed_fields.append('bypass_validation')
            
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]
                
        # برای خریدهای خارج از بازارگاه، فیلدهای مرتبط با بازارگاه را حذف می‌کنیم
        if self.instance.type == 'non_bazaargah':
            if 'purchase_number' in self.fields:
                del self.fields['purchase_number']
            if 'tracking_number' in self.fields:
                del self.fields['tracking_number']
        
        # اینجا محدودیت‌های ویرایش پذیری فیلدها را بر اساس وضعیت خرید اعمال می‌کنیم
        
        # 1. فیلدهای پایه از بعد تأیید پرداخت غیرقابل ویرایش می‌شوند
        payment_verified_states = ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 
                                   'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 
                                   'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                   'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                   'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
        
        if self.instance.state in payment_verified_states:
            read_only_fields_after_payment = ['order_weight', 'company_price', 'customer_price', 
                                             'amount_paid', 'purchase_number', 'tracking_number', 'cargo']
            for field_name in read_only_fields_after_payment:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs['readonly'] = True
                    self.fields[field_name].widget.attrs['disabled'] = True
        
        # 2. فیلدهای مربوط به تحویل از بعد تحویل غیرقابل ویرایش می‌شوند
        delivery_completed_states = ['DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                    'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                    'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
        
        if self.instance.state in delivery_completed_states:
            read_only_fields_after_delivery = ['delivered_weight', 'barnameh', 'code_melli_tahvil', 
                                             'bazaargah_phone_number', 'tahvil_phone_number', 'address',
                                             'allocation_ids']  # شناسه‌های تخصیص هم بعد از تحویل غیرقابل ویرایش می‌شوند
            for field_name in read_only_fields_after_delivery:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs['readonly'] = True
                    self.fields[field_name].widget.attrs['disabled'] = True
        
        # 3. فیلدهای مربوط به اختلاف از بعد ثبت رسید غیرقابل ویرایش می‌شوند
        receipt_submitted_states = ['RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                   'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
        
        if self.instance.state in receipt_submitted_states:
            read_only_fields_after_receipt = ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
            for field_name in read_only_fields_after_receipt:
                if field_name in self.fields:
                    self.fields[field_name].widget.attrs['readonly'] = True
                    self.fields[field_name].widget.attrs['disabled'] = True
        
        # توضیحات همیشه قابل ویرایش باشد
        if 'description' in self.fields:
            if 'readonly' in self.fields['description'].widget.attrs:
                del self.fields['description'].widget.attrs['readonly']
            if 'disabled' in self.fields['description'].widget.attrs:
                del self.fields['description'].widget.attrs['disabled']
                
    def clean(self):
        cleaned_data = super().clean()
        
        # مشکل: مقادیر از قبل موجود (وزن و قیمت) در زمان ارسال فرم پاک می‌شوند
        # اگر فیلدهای اجباری خالی هستند، مقادیر را از نمونه (instance) اصلی بازیابی می‌کنیم
        if self.instance and self.instance.pk:
            # در صورتی که فیلدهای اجباری customer_price و order_weight خالی هستند
            # مقادیر اصلی آنها را از نمونه دریافت می‌کنیم
            if 'customer_price' in self.fields and not cleaned_data.get('customer_price'):
                cleaned_data['customer_price'] = self.instance.customer_price
                if 'customer_price' in self._errors:
                    del self._errors['customer_price']
                    
            if 'order_weight' in self.fields and not cleaned_data.get('order_weight'):
                cleaned_data['order_weight'] = self.instance.order_weight
                if 'order_weight' in self._errors:
                    del self._errors['order_weight']
                    
            if 'delivered_weight' in self.fields and not cleaned_data.get('delivered_weight'):
                cleaned_data['delivered_weight'] = self.instance.delivered_weight
                if 'delivered_weight' in self._errors:
                    del self._errors['delivered_weight']

            if 'company_price' in self.fields and not cleaned_data.get('company_price'):
                cleaned_data['company_price'] = self.instance.company_price
                if 'company_price' in self._errors:
                    del self._errors['company_price']
        
        # اگر بایپس اعتبارسنجی فعال باشد، خطاهای فیلدهای اجباری را نادیده بگیر
        if cleaned_data.get('bypass_validation'):
            # پر کردن مقادیر پیش‌فرض برای فیلدهای اجباری که خالی هستند
            required_fields = ['company_price', 'customer_price', 'order_weight', 'delivered_weight']
            for field in required_fields:
                if field in self.fields and not cleaned_data.get(field):
                    # اگر فیلد در cleaned_data نیست، یک مقدار پیش‌فرض معقول تنظیم کن
                    if field in ['company_price', 'customer_price']:
                        # برای فیلدهای قیمت، یک مقدار پیش‌فرض معقول تنظیم کن
                        cleaned_data[field] = 100000  # مثلا 100,000 ریال
                    elif field in ['order_weight', 'delivered_weight']:
                        # برای فیلدهای وزن، یک مقدار پیش‌فرض معقول تنظیم کن
                        cleaned_data[field] = 10001  # مثلا 10,001 کیلوگرم (بیشتر از حداقل مورد نیاز)
                    
                    # اگر فیلد در خطاها وجود دارد، آن را حذف کن
                    if field in self._errors:
                        del self._errors[field]
        
        # فیلدهای readonly را از cleaned_data حذف می‌کنیم تا تغییر نکنند
        if self.instance.pk:
            instance = self.Meta.model.objects.get(pk=self.instance.pk)
            payment_verified_states = ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 
                                     'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 
                                     'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                     'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                     'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
            
            if instance.state in payment_verified_states:
                read_only_fields_after_payment = ['order_weight', 'company_price', 'customer_price', 
                                                'amount_paid', 'purchase_number', 'tracking_number', 'cargo']
                for field_name in read_only_fields_after_payment:
                    if field_name in cleaned_data:
                        cleaned_data[field_name] = getattr(instance, field_name)
            
            delivery_completed_states = ['DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                         'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                         'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
            
            if instance.state in delivery_completed_states:
                read_only_fields_after_delivery = ['delivered_weight', 'barnameh', 'code_melli_tahvil', 
                                                'bazaargah_phone_number', 'tahvil_phone_number', 'address',
                                                'allocation_ids']
                for field_name in read_only_fields_after_delivery:
                    if field_name in cleaned_data:
                        if field_name == 'allocation_ids':
                            # برای شناسه های تخصیص، مقدار اصلی را حفظ می‌کنیم
                            existing_allocation_ids = ShenaseTakhsis.objects.filter(purchase=instance)
                            if existing_allocation_ids.exists():
                                cleaned_data[field_name] = '\n'.join([item.code for item in existing_allocation_ids])
                        else:
                            cleaned_data[field_name] = getattr(instance, field_name)
            
            receipt_submitted_states = ['RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                         'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
            
            if instance.state in receipt_submitted_states:
                read_only_fields_after_receipt = ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
                for field_name in read_only_fields_after_receipt:
                    if field_name in cleaned_data:
                        cleaned_data[field_name] = getattr(instance, field_name)
        
        # اعتبارسنجی شناسه‌های تخصیص
        allocation_ids_text = cleaned_data.get('allocation_ids', '')
        if allocation_ids_text:
            allocation_ids = [code.strip() for code in allocation_ids_text.strip().split('\n') if code.strip()]
            
            # بررسی یکتا بودن شناسه‌های تخصیص
            unique_ids = set()
            duplicate_ids = []
            
            for code in allocation_ids:
                if code in unique_ids:
                    duplicate_ids.append(code)
                else:
                    unique_ids.add(code)
                    
            if duplicate_ids:
                self.add_error('allocation_ids', f'شناسه‌های تخصیص تکراری: {", ".join(duplicate_ids)}')
            
            # بررسی یکتا بودن در پایگاه داده - شناسه نباید متعلق به خرید دیگری باشد
            if self.instance.pk:
                for code in unique_ids:
                    existing = ShenaseTakhsis.objects.filter(code=code).exclude(purchase=self.instance).first()
                    if existing:
                        self.add_error('allocation_ids', f'شناسه تخصیص "{code}" قبلاً برای خرید دیگری ثبت شده است (خرید {existing.purchase.id})')
                        break
        
        return cleaned_data

@login_required
def purchase_CRUD_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    history_logs = PurchaseHistory.objects.filter(purchase=purchase).order_by('-timestamp')
    state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('-changed_at')
    user_role = determine_user_role(request.user)
    
    # ساخت مراحل پیشرفت بر اساس state (وضعیت فعلی)
    progress_steps = [
        {'name': 'شروع شده', 'status': True},  # همیشه شروع شده
        {'name': 'پیامک ارسال شده', 'status': purchase.state != 'INITIATED'},
        {'name': 'تأیید ثبت خرید در بازارگاه', 'status': purchase.state in ['BAZAARGAH_CONFIRMED', 'PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تأیید انجام پرداخت توسط واحد مالی', 'status': purchase.state in ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ثبت تخصیص توسط مشتری', 'status': purchase.state in ['ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید تخصیص', 'status': purchase.state in ['ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تسویه با واردکننده', 'status': purchase.state in ['VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ارسال آدرس به واردکننده', 'status': purchase.state in ['ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ارسال آدرس به باربری', 'status': purchase.state in ['SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'بارنامه صادر شده', 'status': purchase.state in ['BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تحویل به مشتری', 'status': purchase.state in ['DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید اختلاف', 'status': purchase.state in ['DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'کسری/سرک واریز شده', 'status': purchase.state in ['DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ثبت رسید', 'status': purchase.state in ['RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'صدور فاکتور', 'status': purchase.state in ['INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید نهایی واحد فروش', 'status': purchase.state in ['SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید نهایی واحد لجستیک', 'status': purchase.state in ['LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید نهایی واحد مالی', 'status': purchase.state in ['FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تکمیل شده', 'status': purchase.state == 'COMPLETED'},
    ]
    
    # برای خریدهای خارج از بازارگاه مراحل مرتبط با بازارگاه را حذف می‌کنیم
    if purchase.type == 'non_bazaargah':
        progress_steps = [step for i, step in enumerate(progress_steps) if i not in [2, 4, 5]]

    if request.method == 'POST':
        # کپی کردن داده‌های POST برای اعمال حفاظت فیلدهای غیرقابل ویرایش
        post_data = request.POST.copy()
        
        # همیشه مقادیر customer_price و order_weight را از نمونه اصلی بگذاریم
        # این باعث می‌شود خطای "required" برای این فیلدها رخ ندهد
        post_data['customer_price'] = purchase.customer_price
        post_data['order_weight'] = purchase.order_weight
        post_data['delivered_weight'] = purchase.delivered_weight
        
        # بررسی اینکه آیا یک دکمه اکشن فشرده شده است
        action_buttons = [
            'approve_bazaargah', 'approve_payment', 'approve_allocation', 
            'approve_allocation_approval', 'approve_tasvied_with_vared_konandeh',
            'approve_address', 'approve_sent_to_barbari', 'approve_barnamed',
            'approve_delivered', 'approve_ekhtelaf', 'approve_kasri', 
            'approve_sarak', 'approve_kasri_reciept', 'approve_factor',
            'approve_salesman', 'approve_logistics', 'approve_financial'
        ]
        
        is_action_button_pressed = any(action in request.POST for action in action_buttons)
        
        # اگر دکمه اکشن فشرده شده، بایپس اعتبارسنجی را فعال کن
        if is_action_button_pressed:
            post_data['bypass_validation'] = 'true'
        
        # اینجا می توانیم فیلدهای غیرقابل ویرایش را بر اساس وضعیت خرید به مقادیر اصلی برگردانیم
        if purchase.state in ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 
                            'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 
                            'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                            'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                            'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']:
            # فیلدهای پایه بعد از تایید پرداخت غیرقابل ویرایش هستند
            readonly_fields_after_payment = ['order_weight', 'company_price', 'customer_price', 
                                          'amount_paid', 'purchase_number', 'tracking_number', 'cargo']
            for field in readonly_fields_after_payment:
                if field in post_data and hasattr(purchase, field):
                    post_data[field] = getattr(purchase, field)
        
        if purchase.state in ['DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                            'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                            'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']:
            # فیلدهای مربوط به تحویل بعد از تحویل غیرقابل ویرایش هستند
            readonly_fields_after_delivery = ['delivered_weight', 'barnameh', 'code_melli_tahvil', 
                                           'bazaargah_phone_number', 'tahvil_phone_number', 'address',
                                           'allocation_ids']
            for field in readonly_fields_after_delivery:
                if field in post_data and hasattr(purchase, field):
                    post_data[field] = getattr(purchase, field)
        
        if purchase.state in ['RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                            'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']:
            # فیلدهای مربوط به اختلاف بعد از ثبت رسید غیرقابل ویرایش هستند
            readonly_fields_after_receipt = ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
            for field in readonly_fields_after_receipt:
                if field in post_data and hasattr(purchase, field):
                    post_data[field] = getattr(purchase, field)
        
        form = RoleBasedPurchaseForm(post_data, instance=purchase, user_role=user_role)
        if form.is_valid():
            try:
                with transaction.atomic():
                    original_obj = Purchase.objects.get(id=purchase_id)
                    changed_fields = []
                    
                    # پردازش اکشن‌های مبتنی بر نقش
                    action_taken = False
                    try:
                        # اکشن‌های مبتنی بر state machine
                        if purchase.state == 'SMS_SENT' and 'approve_bazaargah' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.confirm_bazaargah(request.user)
                            action_taken = True
                        elif purchase.state == 'BAZAARGAH_CONFIRMED' and 'approve_payment' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.verify_payment(request.user)
                            action_taken = True
                        elif purchase.state == 'PAYMENT_VERIFIED' and 'approve_allocation' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.register_allocation(request.user)
                            action_taken = True
                        elif purchase.state == 'ALLOCATION_REGISTERED' and 'approve_allocation_approval' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_allocation(request.user)
                            action_taken = True
                        elif purchase.state == 'ALLOCATION_APPROVED' and 'approve_tasvied_with_vared_konandeh' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.settle_with_vendor(request.user)
                            action_taken = True
                        elif purchase.state == 'VENDOR_SETTLED' and 'approve_address' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_address_to_vendor(request.user)
                            action_taken = True
                        elif purchase.state == 'ADDRESS_SENT' and 'approve_sent_to_barbari' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_to_shipping(request.user)
                            action_taken = True
                        elif purchase.state == 'SENT_TO_SHIPPING' and 'approve_barnamed' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.issue_barnameh(request.user)
                            action_taken = True
                        elif purchase.state == 'BARNAMEH_ISSUED' and 'approve_delivered' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.mark_as_delivered(request.user)
                            action_taken = True
                        elif purchase.state == 'DELIVERED' and 'approve_ekhtelaf' in request.POST and (user_role == 'financial_manager' or user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_difference(request.user)
                            action_taken = True
                        elif purchase.state == 'DIFFERENCE_APPROVED' and 'approve_kasri' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            success_message = purchase.deposit_difference(request.user)
                            if success_message:
                                messages.success(request, success_message)
                                return redirect('purchase_CRUD', purchase_id=purchase_id)
                            action_taken = True
                        elif purchase.state == 'DIFFERENCE_APPROVED' and 'approve_sarak' in request.POST and (user_role == 'sales_agent' or user_role == 'financial_manager' or user_role == 'admin'):
                            success_message = purchase.deposit_difference(request.user)
                            if success_message:
                                messages.success(request, success_message)
                                return redirect('purchase_CRUD', purchase_id=purchase_id)
                        elif purchase.state == 'DIFFERENCE_DEPOSITED' and 'approve_kasri_reciept' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.submit_receipt(request.user)
                            action_taken = True
                        elif purchase.state == 'RECEIPT_SUBMITTED' and 'approve_factor' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.issue_invoice(request.user)
                            action_taken = True
                        elif purchase.state == 'INVOICE_ISSUED' and 'approve_salesman' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.approve_by_sales(request.user)
                            action_taken = True
                        elif purchase.state == 'SALES_APPROVED' and 'approve_logistics' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_by_logistics(request.user)
                            action_taken = True
                        elif purchase.state == 'LOGISTICS_APPROVED' and 'approve_financial' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.approve_by_financial(request.user)
                            action_taken = True
                    except ValidationError as action_error:
                        # نمایش خطای اعتبارسنجی به صورت پیام دوستانه کاربر
                        if hasattr(action_error, 'message'):
                            messages.error(request, action_error.message)
                        else:
                            for field, errors in action_error.message_dict.items():
                                for error in errors:
                                    messages.error(request, error)
                        return redirect('purchase_CRUD', purchase_id=purchase_id)
                    
                    # پردازش تغییرات فرم فقط در صورتی که دکمه اکشن فشرده نشده باشد یا اکشن موفقیت‌آمیز بوده باشد
                    if not action_taken or (action_taken and request.POST.get('save_changes')):
                        for field in form.changed_data:
                            # فیلد bypass_validation را از تاریخچه تغییرات حذف می‌کنیم
                            if field == 'bypass_validation' or field == 'allocation_ids':
                                continue
                            old_value = getattr(original_obj, field)
                            new_value = form.cleaned_data.get(field)
                            changed_fields.append(f"{field}: {old_value} → {new_value}")
                    
                    # ابتدا فرم را ذخیره می‌کنیم تا شناسه خرید را داشته باشیم
                    purchase_instance = form.save()
                    
                    # پردازش شناسه‌های تخصیص
                    allocation_ids_text = form.cleaned_data.get('allocation_ids', '')
                    
                    # شناسه تخصیص قدیمی را برای سازگاری با کد موجود حفظ می‌کنیم 
                    # (برای پشتیبانی از اسکریپت‌های قدیمی یا فیلدهای دیگر که ممکن است به آن اشاره کنند)
                    # تنها اولین شناسه را در این فیلد ذخیره می‌کنیم
                    if allocation_ids_text:
                        first_id = allocation_ids_text.strip().split('\n')[0].strip()
                        purchase_instance.shenase_takhsis = first_id
                        
                    # بررسی می‌کنیم آیا کاربر مجاز به تغییر شناسه‌های تخصیص است
                    is_delivery_completed = purchase_instance.state in ['DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                                       'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                                       'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
                    
                    if not is_delivery_completed or form.initial.get('allocation_ids') is None:
                        # شناسه‌های تخصیص جدید را از فرم دریافت می‌کنیم
                        allocation_ids = []
                        if allocation_ids_text:
                            allocation_ids = [code.strip() for code in allocation_ids_text.strip().split('\n') if code.strip()]
                            
                        # شناسه‌های تخصیص قبلی را حذف می‌کنیم
                        ShenaseTakhsis.objects.filter(purchase=purchase_instance).delete()
                        
                        # شناسه‌های تخصیص جدید را ذخیره می‌کنیم
                        for code in allocation_ids:
                            try:
                                ShenaseTakhsis.objects.create(purchase=purchase_instance, code=code)
                                # اگر این شناسه تغییر کرده باشد، در تاریخچه ثبت می‌کنیم
                                changed_fields.append(f"شناسه تخصیص جدید: {code}")
                            except Exception as e:
                                # اگر خطایی رخ داد، آن را نادیده می‌گیریم و ادامه می‌دهیم
                                messages.warning(request, f"خطا در ذخیره شناسه تخصیص {code}: {str(e)}")
                    
                    # ذخیره تغییرات نهایی خرید
                    purchase_instance.save()
                    
                    if changed_fields:
                        PurchaseHistory.objects.create(
                            purchase=purchase_instance,
                            user=request.user,
                            changes=" | ".join(changed_fields)
                        )
                    
                    messages.success(request, 'تغییرات با موفقیت اعمال شد')
                    return redirect('purchase_CRUD', purchase_id=purchase_id)
            except ValidationError as e:
                # مدیریت خطاهای اعتبارسنجی فرم
                if hasattr(e, 'message'):
                    messages.error(request, e.message)
                else:
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            messages.error(request, error)
            except Exception as e:
                messages.error(request, f'خطا: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')

    else:
        form = RoleBasedPurchaseForm(instance=purchase, user_role=user_role)

    notifications = NotificationService.get_unread_notifications(request.user)
    

    context = {
        'purchase': purchase,
        'form': form,
        'progress_steps': progress_steps,
        'history_logs': history_logs,
        'state_changes': state_changes,
        'user_role': user_role,
        'notifications' : notifications,
    }
    return render(request, 'purchase_CRUD_view.html', context)

@login_required
def delete_purchase_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, 'خرید با موفقیت حذف شد')
        return redirect('purchase_list')  # مسیر redirect را بر اساس نیاز خود تنظیم کنید

    context = {
        'purchase': purchase,
    }
    return render(request, 'confirm_delete.html', context)

@login_required
def generate_purchase_pdf(request, purchase_id):
    user_role = determine_user_role(request.user)
    if user_role == 'support_agent':
        messages.error(request, 'شما اجازه ایجاد گزارش خرید را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)

    purchase = get_object_or_404(Purchase, id=purchase_id)
    
    # ساخت پاسخ HTTP برای PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="purchase_{purchase.invoice_id}.pdf"'
    
    # ایجاد فایل PDF در حافظه
    buffer = io.BytesIO()
    
    # تنظیم فونت فارسی
    font_path = os.path.join(settings.BASE_DIR, 'ERP', 'static', 'fonts', 'Vazir.ttf')
    pdfmetrics.registerFont(TTFont('Vazir', font_path))
    
    # تابع کمکی برای تبدیل متن فارسی به حالت صحیح برای نمایش
    def process_persian_text(text):
        """تبدیل متن فارسی به حالت صحیح برای نمایش در PDF"""
        if text is None:
            return "-"
        
        text = str(text)
        if not BIDI_ENABLED:
            return text
        
        try:
            # بازسازی متن فارسی
            reshaped_text = arabic_reshaper.reshape(text)
            # تبدیل به BIDI
            bidi_text = get_display(reshaped_text)
            return bidi_text
        except:
            return text
    
    # تابع کمکی برای تبدیل مقادیر به متن امن
    def safe_text(value, default='-'):
        """تبدیل مقادیر به متن امن"""
        if value is None:
            return default
        return process_persian_text(str(value))
    
    # تابع کمکی برای تبدیل اعداد به متن فارسی با کاما
    def format_number(value, default='0'):
        """تبدیل اعداد به متن فارسی با کاما"""
        if value is None or value == 0:
            return default
        try:
            return process_persian_text(f"{int(value):,}")
        except (ValueError, TypeError):
            return default
    
    # تنظیمات حاشیه‌ها
    doc = SimpleDocTemplate(
        buffer,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
        pagesize=A4
    )
    
    # تنظیم استایل فارسی
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Right',
        fontName='Vazir',
        alignment=TA_RIGHT,
        fontSize=10,
        leading=14,
        firstLineIndent=0,
        rightIndent=0
    ))
    styles.add(ParagraphStyle(
        name='RightTitle',
        fontName='Vazir',
        alignment=TA_RIGHT,
        fontSize=14,
        leading=16,
        spaceAfter=10,
        firstLineIndent=0,
        rightIndent=0
    ))
    
    # لیست آیتم‌های پلاتی‌پاس برای قرار دادن در PDF
    elements = []
    
    # عنوان گزارش
    title_text = process_persian_text(f"گزارش کامل خرید - کد شناسه: {safe_text(purchase.invoice_id)} - شرکت تأمین نهاده سیمرغ")
    elements.append(Paragraph(title_text, styles['RightTitle']))
    elements.append(Spacer(width=0, height=10))
    
    # بخش اطلاعات مشتری
    # دریافت شماره تلفن اصلی مشتری به جای استفاده از فیلد قدیمی
    primary_phone = purchase.customer.get_primary_phone() if hasattr(purchase.customer, 'get_primary_phone') else purchase.customer.phone_number
    
    customer_data = [
        [Paragraph(safe_text(purchase.customer.name), styles['Right']), Paragraph(process_persian_text('نام مشتری:'), styles['Right'])],
        [Paragraph(safe_text(purchase.customer.city), styles['Right']), Paragraph(process_persian_text('شهر/استان:'), styles['Right'])],
        [Paragraph(safe_text(purchase.customer.get_field_of_activity_display()), styles['Right']), Paragraph(process_persian_text('حیطه فعالیت:'), styles['Right'])],
        [Paragraph(safe_text(primary_phone), styles['Right']), Paragraph(process_persian_text('شماره تماس:'), styles['Right'])],
    ]
    
    # اضافه کردن کارشناس فروش مربوطه
    sales_agents = purchase.customer.sales_agent.all()
    if sales_agents:
        sales_agent_names = ", ".join([agent.name for agent in sales_agents])
        customer_data.append([Paragraph(safe_text(sales_agent_names), styles['Right']), Paragraph(process_persian_text('کارشناس فروش:'), styles['Right'])])
    
    customer_table = Table(customer_data, colWidths=[doc.width*3/4, doc.width/4])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph(process_persian_text("اطلاعات مشتری"), styles['RightTitle']))
    elements.append(customer_table)
    elements.append(Spacer(width=0, height=15))
    
    # بخش اطلاعات اصلی خرید
    purchase_status = dict(Purchase.STATUS_CHOICES).get(purchase.state, '')
    purchase_type = dict([('bazaargah', 'بازارگاه'), ('non_bazaargah', 'خارج از بازارگاه')]).get(purchase.type, '-')
    
    cargo_product_type = '-'
    cargo_country = '-'
    if purchase.cargo:
        try:
            cargo_product_type = purchase.cargo.get_product_type_display() or '-'
        except (AttributeError, ValueError):
            cargo_product_type = '-'
            
        try:
            cargo_country = purchase.cargo.get_country_display() or '-'
        except (AttributeError, ValueError):
            cargo_country = '-'
    
    created_at = '-'
    updated_at = '-'
    if purchase.created_at:
        try:
            created_at = purchase.created_at.strftime('%Y/%m/%d %H:%M')
        except AttributeError:
            created_at = '-'
            
    if purchase.updated_at:
        try:
            updated_at = purchase.updated_at.strftime('%Y/%m/%d %H:%M')
        except AttributeError:
            updated_at = '-'
    
    purchase_data = [
        [Paragraph(safe_text(purchase.invoice_id), styles['Right']), Paragraph(process_persian_text('کد درون سازمانی:'), styles['Right'])],
        [Paragraph(safe_text(purchase_status), styles['Right']), Paragraph(process_persian_text('وضعیت فعلی:'), styles['Right'])],
        [Paragraph(process_persian_text(purchase_type), styles['Right']), Paragraph(process_persian_text('نوع خرید:'), styles['Right'])],
        [Paragraph(process_persian_text(purchase.cargo.cottage), styles['Right']), Paragraph(process_persian_text('کوتاژ:'), styles['Right'])],
        [Paragraph(process_persian_text(cargo_product_type), styles['Right']), Paragraph(process_persian_text('نوع کالا:'), styles['Right'])],
        [Paragraph(process_persian_text(cargo_country), styles['Right']), Paragraph(process_persian_text('کشور مبدا:'), styles['Right'])],
        [Paragraph(format_number(purchase.order_weight), styles['Right']), Paragraph(process_persian_text('وزن سفارش (کیلوگرم):'), styles['Right'])],
        [Paragraph(format_number(purchase.delivered_weight), styles['Right']), Paragraph(process_persian_text('وزن تحویلی (کیلوگرم):'), styles['Right'])],
        [Paragraph(safe_text(purchase.payment_method), styles['Right']), Paragraph(process_persian_text('روش پرداخت:'), styles['Right'])],
        [Paragraph(format_number(purchase.customer_price), styles['Right']), Paragraph(process_persian_text('فی فروش (ریال):'), styles['Right'])],
        [Paragraph(format_number(purchase.amount_paid), styles['Right']), Paragraph(process_persian_text('مبلغ پرداختی (ریال):'), styles['Right'])],
        [Paragraph(process_persian_text(created_at), styles['Right']), Paragraph(process_persian_text('تاریخ ثبت:'), styles['Right'])],
        [Paragraph(process_persian_text(updated_at), styles['Right']), Paragraph(process_persian_text('تاریخ بروزرسانی:'), styles['Right'])],
    ]
    
    purchase_table = Table(purchase_data, colWidths=[doc.width*2/3, doc.width/3])
    purchase_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph(process_persian_text("اطلاعات خرید"), styles['RightTitle']))
    elements.append(purchase_table)
    elements.append(Spacer(width=0, height=15))
    
    # اطلاعات بازارگاه یا بارنامه
    if purchase.type == 'bazaargah':
        # دریافت شناسه تخصیص از جدول ManyToMany
        shenase_takhsis_list = []
        try:
            shenase_takhsis_objects = purchase.shenase_takhsis_set.all()
            if shenase_takhsis_objects.exists():
                shenase_takhsis_list = [obj.code for obj in shenase_takhsis_objects]
        except:
            pass
        
        shenase_takhsis_text = ", ".join(shenase_takhsis_list) if shenase_takhsis_list else purchase.shenase_takhsis or '-'
        
        bazargah_data = [
            [Paragraph(safe_text(purchase.purchase_number), styles['Right']), Paragraph(process_persian_text('شماره خرید بازارگاه:'), styles['Right'])],
            [Paragraph(safe_text(purchase.tracking_number), styles['Right']), Paragraph(process_persian_text('شماره پیگیری:'), styles['Right'])],
            [Paragraph(safe_text(shenase_takhsis_text), styles['Right']), Paragraph(process_persian_text('شناسه تخصیص:'), styles['Right'])],
            [Paragraph(safe_text(purchase.code_melli_tahvil), styles['Right']), Paragraph(process_persian_text('کد ملی تحویل:'), styles['Right'])],
            [Paragraph(safe_text(purchase.bazaargah_phone_number), styles['Right']), Paragraph(process_persian_text('شماره تلفن بازارگاه:'), styles['Right'])],
            [Paragraph(safe_text(purchase.tahvil_phone_number), styles['Right']), Paragraph(process_persian_text('شماره تلفن تحویل:'), styles['Right'])],
        ]
        
        bazargah_table = Table(bazargah_data, colWidths=[doc.width*2/3, doc.width/3])
        bazargah_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(process_persian_text("اطلاعات بازارگاه"), styles['RightTitle']))
        elements.append(bazargah_table)
        elements.append(Spacer(width=0, height=15))
    
    # اطلاعات بارنامه و حمل
    shipping_data = [
        [Paragraph(safe_text(purchase.barnameh), styles['Right']), Paragraph(process_persian_text('شماره بارنامه:'), styles['Right'])],
        [Paragraph(safe_text(purchase.address), styles['Right']), Paragraph(process_persian_text('آدرس تحویل:'), styles['Right'])],
    ]
    
    shipping_table = Table(shipping_data, colWidths=[doc.width*2/3, doc.width/3])
    shipping_table.setStyle(TableStyle([
        ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
        ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(Paragraph(process_persian_text("اطلاعات حمل و نقل"), styles['RightTitle']))
    elements.append(shipping_table)
    elements.append(Spacer(width=0, height=15))
    
    # اطلاعات اختلاف وزن
    if purchase.extelaf_type:
        extelaf_data = [
            [Paragraph(safe_text(purchase.extelaf_type), styles['Right']), Paragraph(process_persian_text('نوع اختلاف:'), styles['Right'])],
            [Paragraph(format_number(purchase.extelaf_weight), styles['Right']), Paragraph(process_persian_text('وزن اختلاف (کیلوگرم):'), styles['Right'])],
            [Paragraph(format_number(purchase.extelaf_amount), styles['Right']), Paragraph(process_persian_text('مبلغ اختلاف (ریال):'), styles['Right'])],
        ]
        
        extelaf_table = Table(extelaf_data, colWidths=[doc.width*2/3, doc.width/3])
        extelaf_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(process_persian_text("اطلاعات اختلاف وزن"), styles['RightTitle']))
        elements.append(extelaf_table)
        elements.append(Spacer(width=0, height=15))
    
    # توضیحات
    if purchase.description:
        desc_data = [
            [Paragraph(safe_text(purchase.description), styles['Right']), Paragraph(process_persian_text('توضیحات:'), styles['Right'])],
        ]
        
        desc_table = Table(desc_data, colWidths=[doc.width*2/3, doc.width/3])
        desc_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Vazir'),
            ('ALIGNMENT', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        
        elements.append(Paragraph(process_persian_text("توضیحات"), styles['RightTitle']))
        elements.append(desc_table)
        elements.append(Spacer(width=0, height=15))
    
    # پاورقی با تاریخ تولید گزارش
    now = jdatetime.datetime.now()
    try:
        footer_date = now.strftime('%Y/%m/%d %H:%M')
    except:
        footer_date = "تاریخ نامشخص"
        
    footer_text = process_persian_text(f"تاریخ گزارش: {footer_date}")
    elements.append(Paragraph(footer_text, styles['Right']))
    
    # ساخت PDF
    try:
        doc.build(elements)
    except Exception as e:
        # در صورت بروز خطا، یک صفحه ساده با پیام خطا نمایش دهیم
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=A4)
        p.setFont('Vazir', 14)
        p.drawCentredString(A4[0]/2, A4[1]/2, process_persian_text("خطا در تولید PDF"))
        p.drawCentredString(A4[0]/2, A4[1]/2 - 20, f"کد خطا: {str(e)[:100]}")
        p.save()
        
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

@login_required
def upload_purchase_document(request, purchase_id):
    """
    View for handling document uploads for purchases
    """
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # Check if user has permission to upload documents
    if user_role not in ['sales_agent', 'financial_manager', 'logistics_manager', 'admin']:
        messages.error(request, 'شما اجازه بارگذاری اسناد را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    if request.method == 'POST':
        document_type = request.POST.get('document_type')
        document_file = request.FILES.get('document_file')
        
        # Validate document type based on user role
        valid_types = []
        if user_role in ['logistics_manager', 'sales_agent', 'admin']:
            valid_types.extend(['bazaargah_receipt', 'non_bazaargah_receipt', 'deliver'])
        if user_role in ['financial_manager', 'sales_agent', 'admin']:
            valid_types.extend(['extelaf_receipt', 'invoice'])
            
        if document_type not in valid_types:
            messages.error(request, 'شما اجازه بارگذاری این نوع سند را ندارید')
            return redirect('purchase_CRUD', purchase_id=purchase_id)
        
        # Validate file presence
        if not document_file:
            messages.error(request, 'لطفا یک فایل انتخاب کنید')
            return redirect('purchase_CRUD', purchase_id=purchase_id)
        
        # Validate file size (max 5MB)
        if document_file.size > 5 * 1024 * 1024:
            messages.error(request, 'حجم فایل باید کمتر از ۵ مگابایت باشد')
            return redirect('purchase_CRUD', purchase_id=purchase_id)
        
        # Validate file type
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        file_extension = os.path.splitext(document_file.name)[1].lower()
        if file_extension not in allowed_extensions:
            messages.error(request, 'فرمت فایل غیرمجاز است. لطفا از فرمت‌های PDF، JPG یا PNG استفاده کنید')
            return redirect('purchase_CRUD', purchase_id=purchase_id)
        
        try:
            # Generate unique filename
            original_filename = os.path.splitext(document_file.name)[0]
            file_extension = os.path.splitext(document_file.name)[1].lower()
            safe_filename = slugify(original_filename)  # Convert filename to safe format
            unique_id = str(uuid.uuid4())[:8]  # Short unique identifier
            timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
            
            # Get human-readable document type
            receipt_types_dict = dict([
                ('bazaargah_receipt', 'رسید بازارگاه'),
                ('non_bazaargah_receipt', 'رسید خارج از بازارگاه'),
                ('deliver', 'اسناد تحویلی'),
                ('extelaf_receipt', 'رسید اختلاف'),
                ('invoice', 'فاکتور')
            ])
            document_type_display = receipt_types_dict.get(document_type, document_type)
            
            # Create final filename: purchase_id_document-type_timestamp_unique-id.extension
            final_filename = f"{purchase.id}_{slugify(document_type_display)}_{timestamp}_{unique_id}{file_extension}"
            
            # Save file and create database record
            with transaction.atomic():
                # Create the PurchaseReceipts record
                receipt = PurchaseReceipts(
                    purchase=purchase,
                    user=request.user,
                    reciept_type=document_type
                )
                
                # Save the file directly to the FileField
                # Django will handle file storage internally
                receipt.reciept_file.save(final_filename, document_file, save=False)
                receipt.save()
                
                # Create history entry
                PurchaseHistory.objects.create(
                    purchase=purchase,
                    user=request.user,
                    changes=f"بارگذاری سند: {document_type_display}"
                )
                
                messages.success(request, 'سند با موفقیت بارگذاری شد')
        except Exception as e:
            messages.error(request, f'خطا در بارگذاری سند: {str(e)}')
    
    return redirect('purchase_CRUD', purchase_id=purchase_id)