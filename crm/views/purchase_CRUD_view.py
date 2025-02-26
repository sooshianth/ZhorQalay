from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from core.models import CargoProduct
from core.PurchaseModel import Purchase, PurchaseHistory
from django.core.exceptions import ValidationError, PermissionDenied
from django.forms.models import model_to_dict

def determine_user_role(user):
    ROLE_ATTR_MAP = {
        'financial_manager': 'financial_manager',
        'logistics_manager': 'logistics_manager',
        'sales_agent': 'sales_agent'
    }
    for attr, role in ROLE_ATTR_MAP.items():
        if hasattr(user, attr):
            return role
    return None

class RoleBasedPurchaseForm(forms.ModelForm):
    FIELD_PERMISSIONS = {
        'sales_agent': {
            'fields': ['weight', 'address', 'tracking_number', 
                      'purchase_date', 'purchase_number', 
                      'amount_paid', 'cargo'],
            'defaults': {'amount_paid': 0, 'weight': 0}
        },
        'logistics_manager': {
            'fields': ['weight', 'address', 'tracking_number',
                      'purchase_number', 'amount_paid', 'cargo'],
            'defaults': {}
        },
        'financial_manager': {
            'fields': ['amount_paid', 'purchase_date', 'purchase_number',
                      'tracking_number', 'address'],
            'defaults': {}
        }
    }

    class Meta:
        model = Purchase
        fields = '__all__'

    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        config = self.FIELD_PERMISSIONS.get(user_role, {})
        allowed_fields = config.get('fields', [])
        
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]
        
        self.default_values = config.get('defaults', {})

    def clean(self):
        cleaned_data = super().clean()
        for field, value in self.default_values.items():
            if field not in self.fields:
                cleaned_data[field] = self.instance.__dict__.get(field, value)
        return cleaned_data

@login_required
def purchase_CRUD_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    user_role = determine_user_role(request.user)
    
    # بررسی مجوز دسترسی
    if user_role == 'sales_agent' and purchase.customer.sales_agent != request.user.sales_agent:
        raise PermissionDenied('شما اجازه دسترسی به این صفحه خرید را ندارید')

    # تنظیم مراحل پیشرفت
    PROGRESS_STEPS = [
        ('is_bazaargahed', 'بازارگاه'),
        ('is_paid', 'پرداخت'),
        ('is_takhsised', 'تخصیص'),
        ('is_takhsised_approved', 'تایید تخصیص'),
        ('is_tasvied_with_varedkonandeh', 'تسویه با واردکننده'),
        ('is_address_sent_to_varedkonandeh', 'آدرس'),
        ('is_sent_to_barbari', 'ارسال به باربری'),
        ('is_barnamed', 'برنامه'),
        ('is_factorated', 'فاکتور'),
        ('is_ekhtelaf_approved', 'تایید اختلاف'),
        ('is_kasri_varized', 'کسری واریز شده'),
        ('is_sarak_varized', 'سرک واریز شده'),
        ('is_kasri_reciept_submited', 'تایید رسید کسری'),
        ('does_salesman_approve', 'تایید واحد فروش'),
        ('does_logistics_approve', 'تایید واحد لجستیک'),
        ('does_financial_approve', 'تایید واحد مالی'),
    ]

    # تنظیمات مراحل تأیید
    APPROVAL_FLOW = [
        ('approve_bazaargahed', 'logistics_manager', 'is_sms_sent', 'is_bazaargahed', 'تایید بازارگاه'),
        ('approve_paid', 'financial_manager', 'is_bazaargahed', 'is_paid', 'تایید پرداخت'),
        ('approve_takhsised', 'sales_agent', 'is_paid', 'is_takhsised', 'تایید تخصیص'),
        ('approve_takhsised_approved', 'logistics_manager', 'is_takhsised', 'is_takhsised_approved', 'تایید تخصیص'),
        ('approve_tasvied_with_varedkonandeh', 'financial_manager', 'is_takhsised_approved', 'is_tasvied_with_varedkonandeh', 'تایید تسویه با واردکننده'),
        ('approve_address_sent_to_varedkonandeh', 'logistics_manager', 'is_tasvied_with_varedkonandeh', 'is_address_sent_to_varedkonandeh', 'تایید آدرس'),
        ('approve_sent_to_barbari', 'logistics_manager', 'is_address_sent_to_varedkonandeh', 'is_sent_to_barbari', 'تایید ارسال به باربری'),
        ('approve_barnamed', 'logistics_manager', 'is_sent_to_barbari', 'is_barnamed', 'تایید برنامه'),
        ('approve_factorated', 'financial_manager', 'is_barnamed', 'is_factorated', 'تایید فاکتور'),
        ('approve_ekhtelaf_approved', 'financial_manager', 'is_factorated', 'is_ekhtelaf_approved', 'تایید اختلاف'),
        ('approve_kasri_varized', 'financial_manager', 'is_ekhtelaf_approved', 'is_kasri_varized', 'تایید کسری واریز شده'),
        ('approve_sarak_varized', 'sales_agent', 'is_kasri_varized', 'is_sarak_varized', 'تایید سرک واریز شده'),
        ('approve_kasri_reciept_submited', 'financial_manager', 'is_sarak_varized', 'is_kasri_reciept_submited', 'تایید رسید کسری'),
        ('approve_salesman_approve', 'sales_agent', 'is_kasri_reciept_submited', 'does_salesman_approve', 'تایید واحد فروش'),
        ('approve_logistics_approve', 'logistics_manager', 'does_salesman_approve', 'does_logistics_approve', 'تایید واحد لجستیک'),
        ('approve_financial_approve', 'financial_manager', 'does_logistics_approve', 'does_financial_approve', 'تایید واحد مالی'),
    ]

    if request.method == 'POST':
        form = RoleBasedPurchaseForm(request.POST, instance=purchase, user_role=user_role)
        
    if form.is_valid():
        try:
            with transaction.atomic():
                original_state = model_to_dict(purchase)
                purchase = form.save(commit=False)
                purchase.full_clean()  # اعتبارسنجی مدل
                purchase.save()

                for post_key, role, prereq, field, lbl in APPROVAL_FLOW:
                    if post_key in request.POST and user_role == role:
                        if prereq and not getattr(purchase, prereq, False):
                            raise ValidationError(f'پیشنیاز {lbl} برقرار نیست')
                        
                        approval_method = f'check_{field}'
                        if hasattr(purchase, approval_method):
                            result = getattr(purchase, approval_method)(user_role)
                            if isinstance(result, ValidationError):
                                raise result
                
                # ثبت تاریخچه تغییرات
                changes = [
                    f"{f.verbose_name}: {original_state.get(f.name)} → {getattr(purchase, f.name)}"
                    for f in purchase._meta.fields
                    if original_state.get(f.name) != getattr(purchase, f.name)
                ]
                if changes:
                    PurchaseHistory.objects.create(...)

        except ValidationError as e:
            messages.error(request, f'خطا: {", ".join(e.messages)}')                
        else:
            messages.error(request, 'لطفاً اطلاعات فرم را اصلاح کنید')

    # آماده سازی داده برای نمایش
    progress_steps = [{'name': name, 'status': getattr(purchase, field)} for field, name in PROGRESS_STEPS]
    available_approvals = [
        {'post_key': pk, 'label': lbl} 
        for pk, role, prereq, field, lbl in APPROVAL_FLOW 
        if user_role == role 
        and (not prereq or getattr(purchase, prereq)) 
        and not getattr(purchase, field)
    ]

    context = {
        'purchase': purchase,
        'form': RoleBasedPurchaseForm(instance=purchase, user_role=user_role),
        'progress_steps': progress_steps,
        'history_logs': PurchaseHistory.objects.filter(purchase=purchase).order_by('-timestamp'),
        'available_approvals': available_approvals,
        'user_role': user_role
    }
    
    return render(request, 'purchase_CRUD_view.html', context)
