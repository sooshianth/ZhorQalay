from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.core.exceptions import ValidationError
from core._models import Purchase
from core.PurchaseModel import PurchaseHistory, PurchaseStateChange

def determine_user_role(user):
    """
    تشخیص نقش کاربر براساس روابط او
    به جای بررسی مستقیم role که وجود ندارد، روابط بررسی می‌شود
    """
    if hasattr(user, 'financial_manager') and user.financial_manager is not None:
        return 'financial_manager'
    elif hasattr(user, 'logistics_manager') and user.logistics_manager is not None:
        return 'logistics_manager'
    elif hasattr(user, 'sales_agent') and user.sales_agent is not None:
        return 'sales_agent'
    elif user.is_superuser:
        # مدیر ارشد دسترسی کامل دارد
        return 'admin'
    return None

class RoleBasedPurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = '__all__'
    
    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user_role == 'sales_agent' or user_role == 'admin':
            allowed_fields = [
                'weight', 'description', 'tracking_number', 'purchase_date', 'purchase_number',
                'payment_method', 'customer_price','amount_paid', 'cargo', 'shenase_takhsis', 'code_melli_tahvil', 
                'bazaargah_phone_number', 'tahvil_phone_number',
            ]
        elif user_role == 'logistics_manager':
            allowed_fields = [
                'weight', 'description', 'tracking_number', 'purchase_number', 'amount_paid', 
                'customer_price', 'payment_method', 'cargo', 'shenase_takhsis', 'code_melli_tahvil', 
                'bazaargah_phone_number', 'tahvil_phone_number', 'address',
            ]
        elif user_role == 'financial_manager':
            allowed_fields = [
                'description', 'payment_method', 'company_price', 'customer_price', 'amount_paid', 
                'cargo', 'purchase_date', 'purchase_number', 'tracking_number', 'weight',
            ]
        else:
            allowed_fields = []
        
        # اگر بارنامه صادر شده باشد، فیلدهای اختلاف را نشان بده
        if self.instance.state == 'BARNAMEH_ISSUED':
            allowed_fields += ['extelaf_type', 'extelaf_weight', 'extelaf_amount']
            
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]
                
        # برای خریدهای خارج از بازارگاه، فیلدهای مرتبط با بازارگاه را حذف می‌کنیم
        if self.instance.type == 'non_bazaargah':
            if 'purchase_number' in self.fields:
                del self.fields['purchase_number']
            if 'tracking_number' in self.fields:
                del self.fields['tracking_number']
                
    def clean(self):
        cleaned_data = super().clean()
        # اعتبارسنجی اصلی در متد save مدل انجام می‌شود
        # این باعث می‌شود از تکرار پیام‌های خطا جلوگیری شود
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
        {'name': 'تأیید ثبت خرید در بازارگاه', 'status': purchase.state in ['BAZAARGAH_CONFIRMED', 'PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تأیید انجام پرداخت توسط واحد مالی', 'status': purchase.state in ['PAYMENT_VERIFIED', 'ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ثبت تخصیص توسط مشتری', 'status': purchase.state in ['ALLOCATION_REGISTERED', 'ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید تخصیص', 'status': purchase.state in ['ALLOCATION_APPROVED', 'VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تسویه با واردکننده', 'status': purchase.state in ['VENDOR_SETTLED', 'ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ارسال آدرس به واردکننده', 'status': purchase.state in ['ADDRESS_SENT', 'SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'ارسال آدرس به باربری', 'status': purchase.state in ['SENT_TO_SHIPPING', 'BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'بارنامه صادر شده', 'status': purchase.state in ['BARNAMEH_ISSUED', 'DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تحویل به مشتری', 'status': purchase.state in ['DELIVERED', 'DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'تایید اختلاف', 'status': purchase.state in ['DIFFERENCE_APPROVED', 'SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
        {'name': 'کسری/سرک واریز شده', 'status': purchase.state in ['SHORTAGE_DEPOSITED', 'SURPLUS_DEPOSITED', 'RECEIPT_SUBMITTED', 'INVOICE_ISSUED', 'SALES_APPROVED', 'LOGISTICS_APPROVED', 'FINANCIAL_APPROVED', 'COMPLETED']},
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
        form = RoleBasedPurchaseForm(request.POST, instance=purchase, user_role=user_role)
        if form.is_valid():
            try:
                with transaction.atomic():
                    original_obj = Purchase.objects.get(id=purchase_id)
                    changed_fields = []
                    
                    # پردازش اکشن‌های مبتنی بر نقش
                    action_taken = False
                    try:
                        # اکشن‌های مبتنی بر state machine
                        if 'approve_bazaargah' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.confirm_bazaargah(request.user)
                            action_taken = True
                        elif 'approve_payment' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.verify_payment(request.user)
                            action_taken = True
                        elif 'approve_allocation' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.register_allocation(request.user)
                            action_taken = True
                        elif 'approve_allocation_approval' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_allocation(request.user)
                            action_taken = True
                        elif 'approve_tasvied_with_vared_konandeh' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.settle_with_vendor(request.user)
                            action_taken = True
                        elif 'approve_address' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_address_to_vendor(request.user)
                            action_taken = True
                        elif 'approve_sent_to_barbari' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.send_to_shipping(request.user)
                            action_taken = True
                        elif 'approve_barnamed' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.issue_barnameh(request.user)
                            action_taken = True
                        elif 'approve_delivered' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.mark_as_delivered(request.user)
                            action_taken = True
                        elif 'approve_ekhtelaf' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.approve_difference(request.user)
                            action_taken = True
                        elif 'approve_kasri' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.deposit_shortage(request.user)
                            action_taken = True
                        elif 'approve_sarak' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.deposit_surplus(request.user)
                            action_taken = True
                        elif 'approve_kasri_reciept' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.submit_receipt(request.user)
                            action_taken = True
                        elif 'approve_factor' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
                            purchase.issue_invoice(request.user)
                            action_taken = True
                        elif 'approve_salesman' in request.POST and (user_role == 'sales_agent' or user_role == 'admin'):
                            purchase.approve_by_sales(request.user)
                            action_taken = True
                        elif 'approve_logistics' in request.POST and (user_role == 'logistics_manager' or user_role == 'admin'):
                            purchase.approve_by_logistics(request.user)
                            action_taken = True
                        elif 'approve_financial' in request.POST and (user_role == 'financial_manager' or user_role == 'admin'):
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
                            old_value = getattr(original_obj, field)
                            new_value = form.cleaned_data.get(field)
                            changed_fields.append(f"{field}: {old_value} → {new_value}")
                    
                    form.save()
                    if changed_fields:
                        PurchaseHistory.objects.create(
                            purchase=purchase,
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

    context = {
        'purchase': purchase,
        'form': form,
        'progress_steps': progress_steps,
        'history_logs': history_logs,
        'state_changes': state_changes,
        'user_role': user_role,
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