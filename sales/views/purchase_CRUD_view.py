from django import forms
from core.PurchaseModel import Purchase

class PurchaseEditForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = [
            'weight', 'amount_paid', 'tracking_number', 'address', 
            'purchase_number', 'cargo',

            'is_paid', 'is_takhsised', 'is_sent_to_barbari', 
            'is_sent', 'is_delivered', 'is_canceled', 'is_archived',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }



from django.shortcuts import render, get_object_or_404, redirect
from core.models import CargoProduct
from core.PurchaseModel import Purchase
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.PurchaseModel import PurchaseHistory
from django.db import transaction

@login_required
def purchase_CRUD_view(request, purchase_id):
    purchase = get_object_or_404(Purchase, id=purchase_id)
    history_logs = PurchaseHistory.objects.filter(purchase=purchase).order_by('-timestamp')
    
    # نوار پیشرفت
    progress_steps = [
        {'name': 'پرداخت', 'status': purchase.is_paid},
        {'name': 'تخصیص', 'status': purchase.is_takhsised},
        {'name': 'ارسال به باربری', 'status': purchase.is_sent_to_barbari},
        {'name': 'ارسال شده', 'status': purchase.is_sent},
        {'name': 'تحویل', 'status': purchase.is_delivered},
    ]

    if request.method == 'POST':
        form = PurchaseEditForm(request.POST, instance=purchase)
        if form.is_valid():
            try:
                with transaction.atomic():
                    original_obj = Purchase.objects.get(id=purchase_id)
                    changed_fields = []
                    
                    # ثبت تغییرات
                    for field in form.changed_data:
                        old_value = getattr(original_obj, field)
                        new_value = form.cleaned_data.get(field)
                        changed_fields.append(f"{field} از {old_value} به {new_value}")

                    obj = form.save(commit=False)
                    obj.save()
                    
                    if changed_fields:
                        change_message = " - ".join(changed_fields)
                        PurchaseHistory.objects.create(
                            purchase=purchase,
                            user=request.user,
                            changes=change_message
                        )
                    
                    messages.success(request, 'تغییرات با موفقیت ذخیره شد')
                    return redirect('purchase_CRUD', purchase_id=purchase_id)
            except Exception as e:
                messages.error(request, f'خطا در ذخیره تغییرات: {str(e)}')
    else:
        form = PurchaseEditForm(instance=purchase)

    context = {
        'purchase': purchase,
        'form': form,
        'progress_steps': progress_steps,
        'history_logs': history_logs,
    }
    return render(request, 'purchase_CRUD_view.html', context)