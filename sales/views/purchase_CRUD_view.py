from django import forms
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from core.models import CargoProduct
from core.PurchaseModel import Purchase, PurchaseHistory

def determine_user_role(user):
    if hasattr(user, 'financial_manager'):
        return 'financial_manager'
    elif hasattr(user, 'logistics_manager'):
        return 'logistics_manager'
    elif hasattr(user, 'sales_agent'):
        return 'sales_agent'
    return None

# فرم مخصوص با فیلدهای مجاز برای هر نقش
class RoleBasedPurchaseForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = '__all__'
    
    
    def __init__(self, *args, user_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        # محدودسازی فیلدها بر اساس نقش کاربر
        if user_role == 'sales_agent':
            allowed_fields = [
                'weight', 'address', 'tracking_number',
                'is_takhsised', 'is_address_sent_to_varedkonandeh'
            ]
        elif user_role == 'logistics_manager':
            allowed_fields = [
                'tracking_number', 'is_bazaargahed',
                'is_sent_to_barbari', 'is_barnamed', 'is_sent'
            ]
        elif user_role == 'financial_manager':
            allowed_fields = [
                'amount_paid', 'is_paid', 'is_takhsised_approved',
                'is_factorated', 'is_ekhtelaf_approved'
            ]
        else:
            allowed_fields = []
        
        for field in list(self.fields):
            if field not in allowed_fields:
                del self.fields[field]

@login_required
def purchase_CRUD_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    history_logs = PurchaseHistory.objects.filter(purchase=purchase).order_by('-timestamp')
    user_role = determine_user_role(request.user)  # تابع تشخیص نقش کاربر
    
    # نوار پیشرفت
    progress_steps = [
        {'name': 'بازارگاه', 'status': purchase.is_bazaargahed},
        {'name': 'پرداخت', 'status': purchase.is_paid},
        {'name': 'تخصیص', 'status': purchase.is_takhsised},
        {'name': 'تایید تخصیص', 'status': purchase.is_takhsised_approved},
        {'name': 'تسویه با واردکننده', 'status': purchase.is_tasvied_with_varedkonandeh},
        {'name': 'آدرس', 'status': purchase.is_address_sent_to_varedkonandeh},
        {'name': 'ارسال به باربری', 'status': purchase.is_sent_to_barbari},
        {'name': 'برنامه', 'status': purchase.is_barnamed},
        {'name': 'فاکتور', 'status': purchase.is_factorated},
        {'name': 'تایید اختلاف', 'status': purchase.is_ekhtelaf_approved},
        {'name': 'کسری واریز شده', 'status': purchase.is_kasri_varized},
        {'name': 'سرک واریز شده', 'status': purchase.is_sarak_varized},
        {'name': 'تایید مبلغ اختلاف', 'status': purchase.is_kasri_reciept_submited},

        {'name': 'تایید واحد فروش', 'status': purchase.does_salesman_approve},
        {'name': 'تایید واحد لجستیک', 'status': purchase.does_logistics_approve},
        {'name': 'تایید واحد مالی', 'status': purchase.does_financial_approve},

    ]

    if request.method == 'POST':
        form = RoleBasedPurchaseForm(
            request.POST, 
            instance=purchase,
            user_role=user_role
        )
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    original_obj = Purchase.objects.get(id=purchase_id)
                    changed_fields = []
                    
                    # پردازش دکمه‌های خاص
                    if 'approve_bazaargah' in request.POST:
                        purchase.check_is_bazaargahed(user_role)
                    elif 'approve_payment' in request.POST:
                        purchase.check_is_paid(user_role)
                    elif 'approve_allocation' in request.POST:
                        purchase.check_is_takhsised(user_role)
                    elif 'approve_allocation_approval' in request.POST:
                        purchase.check_is_takhsised_approved(user_role)
                    elif 'approve_address' in request.POST:
                        purchase.check_is_address_sent_to_varedkonandeh(user_role)
                    elif 'approve_sent_to_barbari' in request.POST:
                        purchase.check_is_sent_to_barbari(user_role)
                    elif 'approve_barnamed' in request.POST:
                        purchase.check_is_barnamed(user_role)
                    elif 'approve_factor' in request.POST:
                        purchase.check_is_factorated(user_role)
                    elif 'approve_ekhtelaf' in request.POST:
                        purchase.check_is_ekhtelaf_approved(user_role)
                    elif 'approve_kasri' in request.POST:
                        purchase.check_is_kasri_varized(user_role)
                    elif 'approve_sarak' in request.POST:
                        purchase.check_is_sarak_varized(user_role)
                    elif 'approve_kasri_reciept' in request.POST:
                        purchase.check_is_kasri_reciept_submited(user_role)
                    elif 'approve_salesman' in request.POST:
                        purchase.check_does_salesman_approve(user_role)
                    elif 'approve_logistics' in request.POST:
                        purchase.check_does_logistics_approve(user_role)
                    elif 'approve_financial' in request.POST:
                        purchase.check_does_financial_approve(user_role)
                    
                    
                    # ذخیره تغییرات و ثبت تاریخچه
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
            
            except Exception as e:
                messages.error(request, f'خطا: {str(e)}')

    else:
        form = RoleBasedPurchaseForm(instance=purchase, user_role=user_role)

    context = {
        'purchase': purchase,
        'form': form,
        'progress_steps': progress_steps,
        'history_logs': history_logs,
        'user_role': user_role,
    }
    return render(request, 'purchase_CRUD_view.html', context)

