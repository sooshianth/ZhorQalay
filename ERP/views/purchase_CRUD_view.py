from webbrowser import get
from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import ValidationError
from core._models import Purchase
from core.PurchaseModel import PurchaseHistory, PurchaseStateChange, ShenaseTakhsis, PurchaseReceipts
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from django.utils import timezone
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
from core.SalesAgentModel import SalesAgent
import base64
from xhtml2pdf import pisa
from django.core.cache import cache
from django.db import transaction
import datetime
from bki_api.views import merge_purchases_view
from django.http import HttpRequest, QueryDict
import json
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from .managers_profile_view import get_client_ip

import logging

logger = logging.getLogger("erp_purchase_crude_view")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    BIDI_ENABLED = True
except ImportError:
    BIDI_ENABLED = False

class RoleBasedPurchaseForm(forms.ModelForm):
    # اضافه کردن فیلد برای بایپس اعتبارسنجی هنگام تغییر وضعیت
    bypass_validation = forms.BooleanField(required=False, widget=forms.HiddenInput())
    
    # فیلد چندگانه برای شناسه‌های تخصیص
    allocation_ids = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'هر شناسه تخصیص را در یک خط وارد کنید'}),
        help_text='هر شناسه تخصیص را در یک خط وارد کنید'
    )

    # اضافه کردن فیلد نام محصول به صورت readonly
    product_type = forms.CharField(
        required=False,
        label='نام محصول',
        widget=forms.TextInput(attrs={'readonly': 'readonly'})
    )

    importer = forms.CharField(
        required=False,
        label='واردکننده',
        widget=forms.TextInput(attrs={'readonly': 'readonly'})
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
        
        if user_role == 'sales_agent':
            allowed_fields = ['purchase_number', 'shenase_takhsis', 'date', 'weight', 'delivered_weight',
         'status', 'cargo', 'product_type', 'buyer_name', 'delivery_receiver_name' , 'bazaargah_phone_number',
          'tahvil_phone_number', 'buyer_national_id', 'address', 'tracking_number', 'buyer_user_type',
           'unique_delivery_id', 'delivery_address','delivery_postal_code', 'code_melli_tahvil', 'vehicle_type' ]

        elif user_role == 'support_agent':
            allowed_fields = ['purchase_number', 'shenase_takhsis', 'date', 'unique_sales_agent', 'weight',
         'delivered_weight', 'status',  'cargo', 'product_type', 'importer', 'barbary', 'barbary_confidential_number',
          'barbary_customer_number', 'buyer_name', 'delivery_receiver_name' ,
           'buyer_national_id', 'address', 'tracking_number', 'buyer_user_type',
           'unique_delivery_id', 'delivery_address','delivery_postal_code', 'code_melli_tahvil', 'vehicle_type'] 

        elif user_role == 'financial_manager':
            allowed_fields = ['purchase_number', 'shenase_takhsis', 'date', 'unique_sales_agent', 'customer_price', 'weight',
         'delivered_weight', 'status',
          'cargo', 'product_type', 'importer', 'buyer_name', 'delivery_receiver_name','buyer_national_id', 'address', 
          'tracking_number']  

        
        elif user_role == 'admin' or user_role == 'logistics_manager':
            allowed_fields = ['purchase_number', 'shenase_takhsis', 'date', 'unique_sales_agent', 'customer_price', 'weight',
         'delivered_weight', 'status',  'cargo', 'product_type', 'importer', 'barbary', 'barbary_confidential_number',
          'barbary_customer_number', 'buyer_name', 'delivery_receiver_name' , 'bazaargah_phone_number',
          'tahvil_phone_number',
           'buyer_national_id', 'address', 'tracking_number', 'buyer_user_type',
           'unique_delivery_id', 'delivery_address','delivery_postal_code', 'code_melli_tahvil', 'vehicle_type'] 

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
                                   'VENDOR_SETTLED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 
                                   'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 
                                   'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                   'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED', 'PAY_KASRI', 
                                   'RECIEVE_SARAK', 'FULLY_SETTLED']
        
        # 2. فیلدهای مربوط به تحویل از بعد تحویل غیرقابل ویرایش می‌شوند
        delivery_completed_states = ['PURCHASE_CLOSED', 'BARNAMEH_INCOMPLETE', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 
                                    'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                    'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                    'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED', 'PAY_KASRI',
                                    'RECIEVE_SARAK', 'FULLY_SETTLED']
        
        # 3. فیلدهای مربوط به اختلاف از بعد ثبت رسید غیرقابل ویرایش می‌شوند
        receipt_submitted_states = ['RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                   'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']
        
        # قفل کردن فیلدهای اختلاف پس از وضعیت بستن خرید
        purchase_closed_states = ['PAY_KASRI', 'RECIEVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 
                                'DIFFERENCE_APPROVED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 
                                'FINANCIAL_APPROVED', 'COMPLETED']
        
                # پر کردن فیلد product_type با مقدار از cargo
        if self.instance and self.instance.cargo:
            self.fields['product_type'].initial = self.instance.cargo.get_product_type_display()
        
        # توضیحات همیشه قابل ویرایش باشد
        if 'description' in self.fields:
            if 'readonly' in self.fields['description'].widget.attrs:
                del self.fields['description'].widget.attrs['readonly']
            if 'disabled' in self.fields['description'].widget.attrs:
                del self.fields['description'].widget.attrs['disabled']

        if 'address' in self.fields:
            self.fields['address'].widget.attrs['readonly'] = True
            self.fields['address'].widget.attrs['disabled'] = True

        # فی فروش
        if 'customer_price' in self.fields:
            self.fields['customer_price'].widget.attrs['readonly'] = True
            self.fields['customer_price'].widget.attrs['disabled'] = True

        if 'purchase_number' in self.fields:
            self.fields['purchase_number'].widget.attrs['readonly'] = True
            self.fields['purchase_number'].widget.attrs['disabled'] = True

        if 'tracking_number' in self.fields:
            self.fields['tracking_number'].widget.attrs['readonly'] = True
            self.fields['tracking_number'].widget.attrs['disabled'] = True

        if 'code_melli_tahvil' in self.fields:
            self.fields['code_melli_tahvil'].widget.attrs['readonly'] = True
            self.fields['code_melli_tahvil'].widget.attrs['disabled'] = True

        if 'bazaargah_phone_number' in self.fields:
            self.fields['bazaargah_phone_number'].widget.attrs['readonly'] = True
            self.fields['bazaargah_phone_number'].widget.attrs['disabled'] = True

        if 'buyer_name' in self.fields:
            self.fields['buyer_name'].widget.attrs['readonly'] = True
            self.fields['buyer_name'].widget.attrs['disabled'] = True

        if 'tahvil_phone_number' in self.fields:
            self.fields['tahvil_phone_number'].widget.attrs['readonly'] = True
            self.fields['tahvil_phone_number'].widget.attrs['disabled'] = True

        if 'unique_sales_agent' in self.fields:
            self.fields['unique_sales_agent'].widget.attrs['readonly'] = True
            self.fields['unique_sales_agent'].widget.attrs['disabled'] = True

        if 'delivered_weight' in self.fields:
            self.fields['delivered_weight'].widget.attrs['readonly'] = True
            self.fields['delivered_weight'].widget.attrs['disabled'] = True

        if 'cargo' in self.fields:
            self.fields['cargo'].widget.attrs['readonly'] = True
            self.fields['cargo'].widget.attrs['disabled'] = True

        if 'barbary_confidential_number' in self.fields:
            self.fields['barbary_confidential_number'].widget.attrs['readonly'] = True
            self.fields['barbary_confidential_number'].widget.attrs['disabled'] = True

        if 'barbary_customer_number' in self.fields:
            self.fields['barbary_customer_number'].widget.attrs['readonly'] = True
            self.fields['barbary_customer_number'].widget.attrs['disabled'] = True

        if 'delivery_receiver_name' in self.fields:
            self.fields['delivery_receiver_name'].widget.attrs['readonly'] = True
            self.fields['delivery_receiver_name'].widget.attrs['disabled'] = True

        if 'buyer_national_id' in self.fields:
            self.fields['buyer_national_id'].widget.attrs['readonly'] = True
            self.fields['buyer_national_id'].widget.attrs['disabled'] = True

        if 'buyer_user_type' in self.fields:
            self.fields['buyer_user_type'].widget.attrs['readonly'] = True
            self.fields['buyer_user_type'].widget.attrs['disabled'] = True

        if 'unique_delivery_id' in self.fields:
            self.fields['unique_delivery_id'].widget.attrs['readonly'] = True
            self.fields['unique_delivery_id'].widget.attrs['disabled'] = True

        if 'delivery_address' in self.fields:
            self.fields['delivery_address'].widget.attrs['readonly'] = True
            self.fields['delivery_address'].widget.attrs['disabled'] = True

        if 'delivery_postal_code' in self.fields:
            self.fields['delivery_postal_code'].widget.attrs['readonly'] = True
            self.fields['delivery_postal_code'].widget.attrs['disabled'] = True

        if 'vehicle_type' in self.fields:
            self.fields['vehicle_type'].widget.attrs['readonly'] = True
            self.fields['vehicle_type'].widget.attrs['disabled'] = True

        if 'extelaf_type' in self.fields:
            self.fields['extelaf_type'].widget.attrs['readonly'] = True
            self.fields['extelaf_type'].widget.attrs['disabled'] = True

        if 'extelaf_weight' in self.fields:
            self.fields['extelaf_weight'].widget.attrs['readonly'] = True
            self.fields['extelaf_weight'].widget.attrs['disabled'] = True

        if 'extelaf_amount' in self.fields:
            self.fields['extelaf_amount'].widget.attrs['readonly'] = True
            self.fields['extelaf_amount'].widget.attrs['disabled'] = True

        if 'product_type' in self.fields:
            self.fields['product_type'].widget.attrs['readonly'] = True
            self.fields['product_type'].widget.attrs['disabled'] = True
            
        if 'importer' in self.fields:
            self.fields['importer'].widget.attrs['readonly'] = True
            self.fields['importer'].widget.attrs['disabled'] = True

            
    
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
            
            # فیلدهای customer و buyer_name همیشه غیرقابل ویرایش هستند
            always_readonly_fields = ['customer', 'buyer_name']
            for field_name in always_readonly_fields:
                if field_name in cleaned_data:
                    cleaned_data[field_name] = getattr(instance, field_name)
            
            payment_verified_states = ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 
                                     'VENDOR_SETTLED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 
                                     'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 
                                     'DIFFERENCE_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                     'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED', 'PAY_KASRI', 
                                     'RECIEVE_SARAK', 'FULLY_SETTLED']
            
            if instance.state in payment_verified_states:
                read_only_fields_after_payment = ['order_weight', 'company_price', 'customer_price', 
                                                'amount_paid', 'purchase_number', 'tracking_number', 'cargo']
                for field_name in read_only_fields_after_payment:
                    if field_name in cleaned_data:
                        cleaned_data[field_name] = getattr(instance, field_name)
            
            delivery_completed_states = ['PURCHASE_CLOSED', 'BARNAMEH_INCOMPLETE', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 
                                        'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                                        'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                                        'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED', 'PAY_KASRI',
                                        'RECIEVE_SARAK', 'FULLY_SETTLED']
            
            if instance.state in delivery_completed_states:
                read_only_fields_after_delivery = ['delivered_weight', 'code_melli_tahvil', 
                                                'bazaargah_phone_number', 'tahvil_phone_number', 'address',
                                                'allocation_ids', 'customer_price', 'company_price',
                                                'order_weight', 'payment_method']
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
                        
            # قفل کردن فیلدهای اختلاف پس از وضعیت بستن خرید
            purchase_closed_states = ['PAY_KASRI', 'RECIEVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 
                                    'DIFFERENCE_APPROVED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 
                                    'FINANCIAL_APPROVED', 'COMPLETED']
            
            if instance.state in purchase_closed_states:
                read_only_fields_after_closed = ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
                for field_name in read_only_fields_after_closed:
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

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def purchase_CRUD_view(request, purchase_id):
    logger.warning(f"نمای خرید توسط: {request.user.username}, با آیپی IP: {get_client_ip(request)} باز شد")
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کارشناس فروش - فقط به خریدهای خودش دسترسی دارد
    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا (اولویت اول)
        if purchase.unique_sales_agent and purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # اگر unique_sales_agent تنظیم نشده، بررسی‌های قدیمی برای سازگاری
        if not has_access and not purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            # بررسی کارشناس فروش از طریق رابطه Many-to-Many قدیمی
            if purchase.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
            
            # بررسی کارشناس فروش مشتری (برای سازگاری با خریدهای قدیمی)
            elif purchase.customer and purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
        
        if not has_access:
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            logger.warning(f"مسئول فروش {request.user.username} به خرید غیر خود درخواست دسترسی داد: {purchase.purchase_number}.")
            return redirect('purchase_list')
    
    history_logs = PurchaseHistory.objects.filter(purchase=purchase).order_by('-timestamp')
    state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('-changed_at')
    
    # دریافت شناسه‌های تخصیص مرتبط با خرید
    shenase_takhsis_list = ShenaseTakhsis.objects.filter(purchase=purchase)
    
    # دریافت بارنامه‌های مرتبط با شناسه‌های تخصیص
    barnamehs = []
    
    # واردکردن ماژول بارنامه
    from bki_barnameh.models.BarnamehModel import Barnameh
    
    # بررسی کنیم آیا شناسه تخصیص‌ها وجود دارند
    if shenase_takhsis_list.exists():
        # برای هر شناسه تخصیص، بارنامه‌های مرتبط را پیدا کنیم
        for shenase in shenase_takhsis_list:
            # جستجو با حالت‌های مختلف احتمالی شناسه تخصیص
            # حالت اصلی
            related_barnamehs = Barnameh.objects.filter(shenase_takhsis_code=shenase.code)
            # حالت با اعشار .0
            if not related_barnamehs.exists() and shenase.code.isdigit():
                related_barnamehs = Barnameh.objects.filter(shenase_takhsis_code=f"{shenase.code}.0")
            # حالت بدون اعشار اگر در بارنامه با اعشار ذخیره شده باشد
            if not related_barnamehs.exists() and '.' in shenase.code:
                integer_code = shenase.code.split('.')[0]
                related_barnamehs = Barnameh.objects.filter(shenase_takhsis_code=integer_code)
            # انتساب شناسه تخصیص به بارنامه‌های مرتبط
            for barnameh in related_barnamehs:
                if barnameh not in barnamehs:
                    # اضافه کردن شناسه تخصیص به آبجکت بارنامه برای استفاده‌های بعدی
                    barnameh.shenase_takhsis_id = shenase.id
                    barnamehs.append(barnameh)
    
    # جستجوی بارنامه‌های مرتبط با شماره خرید نیز
    if purchase.purchase_number:
        purchase_number_barnamehs = Barnameh.objects.filter(purchase_number=purchase.purchase_number)
        for barnameh in purchase_number_barnamehs:
            if barnameh not in barnamehs:
                # تلاش برای یافتن شناسه تخصیص برای بارنامه‌هایی که با شماره خرید پیدا شده‌اند
                if hasattr(barnameh, 'shenase_takhsis_code') and barnameh.shenase_takhsis_code:
                    # جستجوی شناسه تخصیص متناظر
                    for shenase in shenase_takhsis_list:
                        # مقایسه با حالت‌های مختلف احتمالی
                        if (shenase.code == barnameh.shenase_takhsis_code or
                            (shenase.code + '.0') == barnameh.shenase_takhsis_code or
                            (barnameh.shenase_takhsis_code and '.' in barnameh.shenase_takhsis_code and 
                             shenase.code == barnameh.shenase_takhsis_code.split('.')[0])):
                            barnameh.shenase_takhsis_id = shenase.id
                            break
                barnamehs.append(barnameh)
    
    # جستجو بر اساس شناسه تخصیص قدیمی
    if purchase.shenase_takhsis:
        # چندین حالت ممکن برای شناسه تخصیص
        takhsis_variants = [
            purchase.shenase_takhsis,                    # حالت اصلی
            f"{purchase.shenase_takhsis}.0",             # با اعشار .0
        ]
        # اگر شناسه تخصیص اعشاری است، حالت بدون اعشار را هم اضافه کنیم
        if '.' in purchase.shenase_takhsis:
            takhsis_variants.append(purchase.shenase_takhsis.split('.')[0])
        
        # جستجو برای همه حالت‌های ممکن
        for variant in takhsis_variants:
            old_takhsis_barnamehs = Barnameh.objects.filter(shenase_takhsis_code=variant)
            for barnameh in old_takhsis_barnamehs:
                if barnameh not in barnamehs:
                    # تلاش برای یافتن شناسه تخصیص مرتبط
                    for shenase in shenase_takhsis_list:
                        if (variant == shenase.code or 
                            (variant + '.0') == shenase.code or
                            ('.' in variant and variant.split('.')[0] == shenase.code)):
                            barnameh.shenase_takhsis_id = shenase.id
                            break
                    barnamehs.append(barnameh)
                
    # بارنامه‌های فیلتر شده را از طریق رابطه مستقیم با خرید نیز بررسی کنیم
    if hasattr(purchase, 'barnamehs'):
        direct_barnamehs = purchase.barnamehs.all()
        for barnameh in direct_barnamehs:
            if barnameh not in barnamehs:
                # تلاش برای یافتن شناسه تخصیص
                if hasattr(barnameh, 'shenase_takhsis_code') and barnameh.shenase_takhsis_code:
                    for shenase in shenase_takhsis_list:
                        # مقایسه با حالت‌های مختلف احتمالی
                        if (shenase.code == barnameh.shenase_takhsis_code or
                            (shenase.code + '.0') == barnameh.shenase_takhsis_code or
                            (barnameh.shenase_takhsis_code and '.' in barnameh.shenase_takhsis_code and 
                             shenase.code == barnameh.shenase_takhsis_code.split('.')[0])):
                            barnameh.shenase_takhsis_id = shenase.id
                            break
                barnamehs.append(barnameh)
                
    # اطمینان از نمایش فیلدهای بارنامه به صورت مناسب
    for barnameh in barnamehs:
        # تنظیم فیلدهای نمایشی
        if not hasattr(barnameh, 'barnameh_number') and hasattr(barnameh, 'number'):
            barnameh.barnameh_number = barnameh.number
        if not hasattr(barnameh, 'serial_number') and hasattr(barnameh, 'serial'):
            barnameh.serial_number = barnameh.serial
        if not hasattr(barnameh, 'weight') and hasattr(barnameh, 'tonnage'):
            barnameh.weight = barnameh.tonnage
        if not hasattr(barnameh, 'vehicle_plate_number') and hasattr(barnameh, 'vehicle_plate'):
            barnameh.vehicle_plate_number = barnameh.vehicle_plate
        if not hasattr(barnameh, 'receiver') and hasattr(barnameh, 'receiver_name'):
            barnameh.receiver = barnameh.receiver_name
        if not hasattr(barnameh, 'issue_date') and hasattr(barnameh, 'barnameh_date'):
            barnameh.issue_date = barnameh.barnameh_date
        
        # تنظیم فیلد shenase_takhsis_id اگر وجود ندارد
        if not hasattr(barnameh, 'shenase_takhsis_id') and hasattr(barnameh, 'shenase_takhsis_code'):
            # تلاش برای پیدا کردن شناسه تخصیص مرتبط
            for shenase in shenase_takhsis_list:
                if (shenase.code == barnameh.shenase_takhsis_code or
                    (shenase.code + '.0') == barnameh.shenase_takhsis_code or
                    (barnameh.shenase_takhsis_code and '.' in barnameh.shenase_takhsis_code and 
                     shenase.code == barnameh.shenase_takhsis_code.split('.')[0])):
                    barnameh.shenase_takhsis_id = shenase.id
                    break
    
    # ساخت مراحل پیشرفت بر اساس state (وضعیت فعلی)
    progress_steps = [
        {'name': 'شروع شده', 'status': True},  # همیشه شروع شده
        {'name': 'پیامک ارسال شده', 'status': purchase.state != 'INITIATED'},
        {'name': 'ثبت خرید در بازارگاه', 'status': purchase.state in ['PAYMENT_VERIFIED', 'ALLOCATION_APPROVED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'تایید تخصیص', 'status': purchase.state in ['ALLOCATION_APPROVED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'ارسال آدرس به واردکننده', 'status': purchase.state in ['ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'در انتظار بارنامه', 'status': purchase.state in ['WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'بارنامه صادر شده', 'status': purchase.state in ['BARNAMEH_ISSUED', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'بارنامه ناقص', 'status': purchase.state in ['BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'بستن خرید در بازارگاه', 'status': purchase.state in ['PURCHASE_CLOSED', 'DIFFERENCE_APPROVED', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED', 'PAY_KASRI', 'RECIEVE_SARAK']},
        {'name': 'پرداخت کسری', 'status': purchase.state in ['PAY_KASRI', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED']},
        {'name': 'دریافت سرک', 'status': purchase.state in ['RECIEVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED']},
        {'name': 'تسویه کامل', 'status': purchase.state in ['FULLY_SETTLED', 'INVOICE_ISSUED', 'CANCELED']},
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
        post_data['customer_phones'] = purchase.customer.phone_numbers
        
        # بررسی اینکه آیا یک دکمه اکشن فشرده شده است
        action_buttons = [
            'approve_payment', 'approve_allocation', 
            'approve_allocation_approval', 'approve_address',
            'approve_wait_for_barnameh', 'approve_barnameh',
            'approve_mark_barnameh_incomplete', 'approve_close_purchase',
            'approve_ekhtelaf', 'approve_fully_settle', 'approve_factor',
            'cancel_purchase', 'archive_purchase'
        ]
        
        is_action_button_pressed = any(action in request.POST for action in action_buttons)
        
        # اگر دکمه اکشن فشرده شده، بایپس اعتبارسنجی را فعال کن
        if is_action_button_pressed:
            post_data['bypass_validation'] = 'true'
        
        # اینجا می توانیم فیلدهای غیرقابل ویرایش را بر اساس وضعیت خرید به مقادیر اصلی برگردانیم
        if purchase.state in ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 
                            'VENDOR_SETTLED', 'ADDRESS_SENT', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED', 
                            'BARNAMEH_INCOMPLETE', 'PURCHASE_CLOSED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                            'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                            'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED', 'PAY_KASRI', 'RECIEVE_SARAK', 'FULLY_SETTLED']:
            # فیلدهای پایه بعد از تایید پرداخت غیرقابل ویرایش هستند
            readonly_fields_after_payment = ['order_weight', 'company_price', 'customer_price', 
                                          'amount_paid', 'purchase_number', 'tracking_number', 'cargo']
            for field in readonly_fields_after_payment:
                if field in post_data and hasattr(purchase, field):
                    post_data[field] = getattr(purchase, field)
        
        if purchase.state in ['PURCHASE_CLOSED', 'BARNAMEH_INCOMPLETE', 'WAITING_FOR_BARNAMEH', 'BARNAMEH_ISSUED',
                            'DELIVERED', 'DIFFERENCE_APPROVED', 'DIFFERENCE_DEPOSITED', 
                            'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 
                            'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED', 'PAY_KASRI', 'RECIEVE_SARAK', 'FULLY_SETTLED']:
            # فیلدهای مربوط به تحویل بعد از تحویل غیرقابل ویرایش هستند
            readonly_fields_after_delivery = ['delivered_weight', 'code_melli_tahvil', 
                                           'bazaargah_phone_number', 'tahvil_phone_number', 'address',
                                           'allocation_ids', 'customer_price', 'company_price',
                                           'order_weight', 'payment_method']
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
        
        # قفل کردن فیلدهای اختلاف پس از بستن خرید و در وضعیت‌های اختلاف
        if purchase.state in ['PAY_KASRI', 'RECIEVE_SARAK', 'FULLY_SETTLED', 'INVOICE_ISSUED', 
                            'DIFFERENCE_APPROVED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 
                            'FINANCIAL_APPROVED', 'COMPLETED']:
            readonly_fields_after_closed = ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
            for field in readonly_fields_after_closed:
                if field in post_data and hasattr(purchase, field):
                    post_data[field] = getattr(purchase, field)
                    
        # همیشه اجازه ویرایش توضیحات را بده
        if 'description' in post_data and request.POST.get('description'):
            post_data['description'] = request.POST.get('description')
        
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
                        if purchase.state == 'SMS_SENT' and 'approve_payment' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.verify_payment(request.user)
                            action_taken = True
                        elif purchase.state == 'PAYMENT_VERIFIED' and 'approve_allocation' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.register_allocation(request.user)
                            action_taken = True
                        elif purchase.state == 'PAYMENT_VERIFIED' and 'approve_allocation_approval' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_allocation(request.user)
                            action_taken = True
                        elif purchase.state == 'ALLOCATION_APPROVED' and 'approve_address' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_address_to_vendor(request.user)
                            action_taken = True
                        elif purchase.state == 'ADDRESS_SENT' and 'approve_wait_for_barnameh' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.wait_for_barnameh(request.user)
                            action_taken = True
                        elif purchase.state == 'WAITING_FOR_BARNAMEH' and 'approve_barnameh' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.issue_barnameh(request.user)
                            action_taken = True
                        elif (purchase.state == 'WAITING_FOR_BARNAMEH' or purchase.state == 'BARNAMEH_ISSUED') and 'approve_mark_barnameh_incomplete' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.mark_barnameh_incomplete(request.user)
                            action_taken = True
                        elif (purchase.state == 'BARNAMEH_ISSUED' or purchase.state == 'BARNAMEH_INCOMPLETE') and 'approve_close_purchase' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.close_purchase(request.user)
                            action_taken = True
                        elif purchase.state == 'PURCHASE_CLOSED' and 'approve_ekhtelaf' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.approve_difference(request.user)
                            action_taken = True
                        elif (purchase.state == 'DIFFERENCE_APPROVED' or purchase.state == 'PURCHASE_CLOSED') and 'approve_fully_settle' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.fully_settle(request.user)
                            action_taken = True
                        elif purchase.state == 'FULLY_SETTLED' and 'approve_factor' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.issue_invoice(request.user)
                            action_taken = True
                        elif 'cancel_purchase' in request.POST and user_role == 'admin':
                            purchase.cancel_purchase(request.user)
                            action_taken = True
                        elif 'archive_purchase' in request.POST and user_role == 'admin':
                            purchase.archive_purchase(request.user)
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
        'notifications': notifications,
        'barnamehs': barnamehs,
        'shenase_takhsis_list': shenase_takhsis_list,
    }
    return render(request, 'purchase_CRUD_view.html', context)

@login_required
@role_required('admin', 'logistics_manager', 'sales_agent')
def delete_purchase_view(request, purchase_id):
    logger.warning(f"خرید {purchase_id} پاک شد توسط {request.user.username} with ip {get_client_ip(request)}")
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    # بررسی دسترسی کارشناس فروش - فقط به خریدهای خودش دسترسی دارد
    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا (اولویت اول)
        if purchase.unique_sales_agent and purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # اگر unique_sales_agent تنظیم نشده، بررسی‌های قدیمی برای سازگاری
        if not has_access and not purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            # بررسی کارشناس فروش از طریق رابطه Many-to-Many قدیمی
            if purchase.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
            
            # بررسی کارشناس فروش مشتری (برای سازگاری با خریدهای قدیمی)
            elif purchase.customer and purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
        
        if not has_access:
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            logger.warning(f"مسئول فروش {request.user.username} به خرید غیر خود درخواست پاک کردن داد: {purchase.purchase_number}.")
            return redirect('purchase_list')
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, 'خرید با موفقیت حذف شد')
        return redirect('purchase_list')  # مسیر redirect را بر اساس نیاز خود تنظیم کنید

    context = {
        'purchase': purchase,
    }
    return render(request, 'confirm_delete.html', context)

@login_required
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
def generate_purchase_pdf(request, purchase_id):
    logger.warning(f"پی دی اف خرید {purchase_id} توسط {request.user.username} با آیپی {get_client_ip(request)} ایجاد شد")
    user_role = determine_user_role(request.user)
    if user_role == 'support_agent':
        logger.warning(f"مسئول پیگیری {request.user.username} به خرید {purchase_id} درخواست خلاف پی دی اف داد")
        messages.error(request, 'شما اجازه ایجاد گزارش خرید را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)

    purchase = get_object_or_404(Purchase, id=purchase_id)
    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا (اولویت اول)
        if purchase.unique_sales_agent and purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # اگر unique_sales_agent تنظیم نشده، بررسی‌های قدیمی برای سازگاری
        if not has_access and not purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            # بررسی کارشناس فروش از طریق رابطه Many-to-Many قدیمی
            if purchase.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
            
            # بررسی کارشناس فروش مشتری (برای سازگاری با خریدهای قدیمی)
            elif purchase.customer and purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
        
        if not has_access:
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            logger.warning(f"مسئول فروش {request.user.username} به خرید غیر خود درخواست گزارش پی دی اف داد: {purchase.purchase_number}.")
            return redirect('purchase_list')
    
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
        [Paragraph(safe_text(getattr(purchase, 'barnameh', None)), styles['Right']), Paragraph(process_persian_text('شماره بارنامه:'), styles['Right'])],
        [Paragraph(safe_text(purchase.address), styles['Right']), Paragraph(process_persian_text('آدرس تحویل:'), styles['Right'])],
    ]
    
    # اگر بارنامه ندارد، سعی کنیم از رابطه barnamehs استفاده کنیم
    if hasattr(purchase, 'barnamehs') and purchase.barnamehs.exists():
        barnameh_numbers = [b.number for b in purchase.barnamehs.all() if b.number]
        if barnameh_numbers:
            shipping_data[0] = [Paragraph(safe_text(", ".join(barnameh_numbers)), styles['Right']), Paragraph(process_persian_text('شماره بارنامه:'), styles['Right'])]
    
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
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent')
def upload_purchase_document(request, purchase_id):
    logger.warning(f"دسترسی به آپلود اسناد {purchase_id} توسط {request.user.username} با آیپی {get_client_ip(request)}")
    """
    View for handling document uploads for purchases
    """
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # Check if user has permission to upload documents
    if user_role not in ['sales_agent', 'financial_manager', 'logistics_manager', 'admin']:
        logger.warning(f"کاربر {request.user.username} به خرید {purchase_id} غیر قانونی درخواست آپلود اسناد داد. {get_client_ip(request)}")
        messages.error(request, 'شما اجازه بارگذاری اسناد را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا (اولویت اول)
        if purchase.unique_sales_agent and purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # اگر unique_sales_agent تنظیم نشده، بررسی‌های قدیمی برای سازگاری
        if not has_access and not purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            # بررسی کارشناس فروش از طریق رابطه Many-to-Many قدیمی
            if purchase.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
            
            # بررسی کارشناس فروش مشتری (برای سازگاری با خریدهای قدیمی)
            elif purchase.customer and purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
        
        if not has_access:
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            logger.warning(f"مسئول فروش {request.user.username} به خرید غیر خود درخواست اپلود اسناد داد: {purchase.purchase_number}.")
            return redirect('purchase_list')

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
            logger.warning(f"کاربر {request.user.username} فایل {document_type} را که مجاز به آن نیز درخواست آپلود داد. {get_client_ip(request)}")
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

@login_required
@role_required('admin', 'sales_agent')
def link_bazaargah_purchase(request, purchase_id):
    """
    ارتباط دادن خرید موجود با خرید بازارگاه از طریق شماره خرید
    
    این تابع به کارشناس فروش اجازه می‌دهد تا خرید دستی را که ایجاد کرده،
    با خرید بازارگاه که توسط API ایجاد شده است ادغام کند.
    مشتری، شناسه فاکتور و کارشناس فروش از خرید دستی حفظ می‌شود،
    اما سایر اطلاعات از خرید API می‌آید.
    """
    logger.warning(f"لینک بازارگاه با خرید توسط {request.user.username} با خرید {purchase_id} درخواست شد. {get_client_ip(request)}")
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کاربر
    if user_role not in ['sales_agent', 'admin']:
        messages.error(request, 'شما اجازه انجام این عملیات را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)

    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا (اولویت اول)
        if purchase.unique_sales_agent and purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # اگر unique_sales_agent تنظیم نشده، بررسی‌های قدیمی برای سازگاری
        if not has_access and not purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            # بررسی کارشناس فروش از طریق رابطه Many-to-Many قدیمی
            if purchase.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
            
            # بررسی کارشناس فروش مشتری (برای سازگاری با خریدهای قدیمی)
            elif purchase.customer and purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
        
        if not has_access:
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            logger.warning(f"مسئول فروش {request.user.username} به خرید غیر خود درخواست لینک بازارگاه داد: {purchase.purchase_number}.")
            return redirect('purchase_list')
    
    # بررسی دسترسی کارشناس فروش به خرید - برداشته شد برای رفع مشکل محدودیت دسترسی
    # اجازه ادغام به همه کارشناسان فروش و مدیران داده می‌شود
    
    # بررسی نوع درخواست
    if request.method != 'POST':
        logger.warning(f"درخواست نامعتبر برای لینک خرید بازارگاه توسط {request.user.username}. not POST")
        messages.error(request, 'درخواست نامعتبر')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
        
    purchase_number = request.POST.get('purchase_number')
    
    if not purchase_number:
        messages.error(request, 'شماره خرید بازارگاه الزامی است')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # اطمینان از اینکه شماره خرید 7 رقمی است
    if not purchase_number.isdigit() or len(purchase_number) != 7:
        messages.error(request, 'شماره خرید بازارگاه باید دقیقاً 7 رقم باشد')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی اینکه آیا خرید مورد نظر قبلا شماره خرید دارد یا خیر
    if purchase.purchase_number:
        messages.error(request, 'این خرید قبلا به خرید بازارگاه متصل شده است')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # ملاک تشخیص خرید دستی نداشتن شماره خرید است نه نوع آن
    # بنابراین بررسی type را حذف می‌کنیم و فقط بررسی می‌کنیم شماره خرید نداشته باشد
    # که این بررسی قبلاً انجام شده است
    
    # جستجوی خرید بازارگاه با شماره خرید داده شده
    api_purchase = Purchase.objects.filter(purchase_number=purchase_number).first()
    
    if not api_purchase:
        messages.error(request, f'خریدی با شماره {purchase_number} در سیستم یافت نشد. ممکن است هنوز توسط API بازارگاه دریافت نشده باشد.')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی اینکه آیا خرید API قبلاً ادغام شده است یا نه
    if api_purchase.is_merged_purchase():
        messages.error(request, f'خرید با شماره {purchase_number} قبلاً با خرید دیگری ادغام شده است و امکان ادغام مجدد وجود ندارد.')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی محدودیت زمانی 24 ساعت
    time_threshold = timezone.now() - datetime.timedelta(hours=24)
    if api_purchase.created_at < time_threshold:
        logger.warning(f"ادغام خرید بازارگاه با عمر بیش از 24 ساعت توسط {request.user.username} (خرید دستی: {purchase.id})")
        messages.error(request, 'امکان ادغام خرید‌های بازارگاه با عمر بیشتر از 24 ساعت وجود ندارد.')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی که خرید انتخاب شده توسط خود کاربر ایجاد نشده باشد - این بررسی نیز برداشته شد
    # به کارشناسان فروش اجازه می‌دهیم خریدها را بدون محدودیت ادغام کنند

    # ارسال درخواست به API برای ادغام خریدها
    try:
        # به جای ایجاد HttpRequest جدید، مستقیماً دیکشنری داده‌ها را می‌سازیم
        # و تابع merge_purchases_view را فراخوانی می‌کنیم
        from django.test.client import RequestFactory
        
        # ایجاد یک درخواست ساختگی با RequestFactory
        factory = RequestFactory()
        data = {
            'agent_purchase_id': purchase.id,
            'api_purchase_id': api_purchase.id
        }
        
        # ایجاد یک درخواست POST جدید
        merge_request = factory.post('/api/merge-purchases/', data=data, content_type='application/json')
        
        # افزودن اطلاعات کاربر
        merge_request.user = request.user
        
        # فراخوانی تابع merge_purchases_view با درخواست ساختگی
        from bki_api.views import merge_purchases_view
        merge_response = merge_purchases_view(merge_request)
        
        # بررسی پاسخ
        response_data = json.loads(merge_response.content)
        
        if merge_response.status_code == 200 and response_data.get('success'):
            # ارجاع به صفحه خرید ادغام شده
            merged_purchase_id = response_data.get('merged_purchase_id')
            messages.success(request, 'خرید با موفقیت با خرید بازارگاه ادغام شد')
            if merged_purchase_id:
                return redirect('purchase_CRUD', purchase_id=merged_purchase_id)
        else:
            error_message = response_data.get('error', 'خطای نامشخص در ادغام خریدها')
            messages.error(request, f'خطا در ادغام خریدها: {error_message}')
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"خطا در ارتباط با سرور: {str(e)}\n{error_details}")
        messages.error(request, f'خطا در ارتباط با سرور: ')
    
    return redirect('purchase_CRUD', purchase_id=purchase_id)

@login_required
@role_required('admin', 'sales_agent')
def link_manual_purchase(request, purchase_id):
    """
    ارتباط دادن خرید API (که دارای شماره خرید است) با خرید دستی
    
    این تابع برعکس link_bazaargah_purchase کار می‌کند و خرید API را که توسط API ایجاد شده
    با خرید دستی که کارشناس فروش ایجاد کرده ادغام می‌کند.
    """
    logger.warning(f"لینک خرید دستی با بازارگاه توسط {request.user.username} با خرید {purchase_id} درخواست شد. {get_client_ip(request)}")
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی دسترسی کاربر
    if user_role not in ['sales_agent', 'admin']:
        messages.error(request, 'شما اجازه انجام این عملیات را ندارید')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا (اولویت اول)
        if purchase.unique_sales_agent and purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # اگر unique_sales_agent تنظیم نشده، بررسی‌های قدیمی برای سازگاری
        if not has_access and not purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            # بررسی کارشناس فروش از طریق رابطه Many-to-Many قدیمی
            if purchase.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
            
            # بررسی کارشناس فروش مشتری (برای سازگاری با خریدهای قدیمی)
            elif purchase.customer and purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists():
                has_access = True
        
        if not has_access:
            messages.error(request, 'شما اجازه دسترسی به این خرید را ندارید.')
            logger.warning(f"مسئول فروش {request.user.username} به خرید غیر خود درخواست لینک خرید دستی داد: {purchase.purchase_number}.")
            return redirect('purchase_list')
    
    # بررسی که این خرید API باشد (دارای شماره خرید)
    if not purchase.purchase_number:
        messages.error(request, 'این خرید دارای شماره خرید بازارگاه نیست')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی که قبلاً ادغام نشده باشد
    if purchase.is_merged_purchase():
        messages.error(request, 'این خرید قبلاً ادغام شده است')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی نوع درخواست
    if request.method != 'POST':
        logger.warning(f"درخواست نامعتبر برای لینک خرید ذستی توسط {request.user.username}. not POST")
        messages.error(request, 'درخواست نامعتبر')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
        
    manual_purchase_id = request.POST.get('manual_purchase_id')
    
    if not manual_purchase_id:
        messages.error(request, 'شناسه خرید دستی الزامی است')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # یافتن خرید دستی
    try:
        manual_purchase = Purchase.objects.get(id=manual_purchase_id)
    except Purchase.DoesNotExist:
        messages.error(request, f'خرید دستی با شناسه {manual_purchase_id} یافت نشد')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی که خرید دستی واقعاً دستی باشد (بدون شماره خرید)
    if manual_purchase.purchase_number:
        messages.error(request, 'خرید انتخاب شده دارای شماره خرید بازارگاه است و خرید دستی نیست')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی دسترسی کارشناس فروش به خرید دستی
    if user_role == 'sales_agent':
        has_access = False
        
        # بررسی کارشناس فروش یکتا
        if manual_purchase.unique_sales_agent and manual_purchase.unique_sales_agent.user == request.user:
            has_access = True
        
        # بررسی‌های قدیمی برای سازگاری
        if not has_access and not manual_purchase.unique_sales_agent and hasattr(request.user, 'sales_agent'):
            if (manual_purchase.sales_agent.filter(id=request.user.sales_agent.id).exists() or
                (manual_purchase.customer and manual_purchase.customer.sales_agent.filter(id=request.user.sales_agent.id).exists())):
                has_access = True
        
        if not has_access:
            logger.warning(f"کارشناس فروش {request.user.username} تلاش برای دسترسی به خرید دستی شخص دیگر را داشت. ایدی خرید: {purchase_id}")
            messages.error(request, 'شما اجازه دسترسی به خرید دستی انتخاب شده را ندارید')
            return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # بررسی محدودیت زمانی 49 ساعت
    time_threshold = timezone.now() - datetime.timedelta(hours=49)
    if purchase.created_at < time_threshold:
        messages.error(request, 'امکان ادغام خرید‌های بازارگاه با عمر بیشتر از 49 ساعت وجود ندارد')
        return redirect('purchase_CRUD', purchase_id=purchase_id)
    
    # ارسال درخواست به API برای ادغام خریدها
    try:
        from django.test.client import RequestFactory
        
        # ایجاد یک درخواست ساختگی با RequestFactory
        factory = RequestFactory()
        data = {
            'agent_purchase_id': manual_purchase.id,
            'api_purchase_id': purchase.id
        }
        
        # ایجاد یک درخواست POST جدید
        merge_request = factory.post('/api/merge-purchases/', data=data, content_type='application/json')
        
        # افزودن اطلاعات کاربر
        merge_request.user = request.user
        
        # فراخوانی تابع merge_purchases_view با درخواست ساختگی
        from bki_api.views import merge_purchases_view
        merge_response = merge_purchases_view(merge_request)
        
        # بررسی پاسخ
        response_data = json.loads(merge_response.content)
        
        if merge_response.status_code == 200 and response_data.get('success'):
            # ارجاع به صفحه خرید ادغام شده
            merged_purchase_id = response_data.get('merged_purchase_id')
            messages.success(request, 'خرید API با موفقیت با خرید دستی ادغام شد')
            if merged_purchase_id:
                return redirect('purchase_CRUD', purchase_id=merged_purchase_id)
        else:
            error_message = response_data.get('error', 'خطای نامشخص در ادغام خریدها')
            messages.error(request, f'خطا در ادغام خریدها: {error_message}')
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"خطا در ارتباط با سرور: {str(e)}\n{error_details}")
        messages.error(request, f'خطا در ارتباط با سرور:')
    
    return redirect('purchase_CRUD', purchase_id=purchase_id)