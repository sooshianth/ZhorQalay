from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct




def purchase_register_view(request, customer_id):
    """
    ویو ثبت خرید جدید برای مشتری.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    cargo_product = None
    purchase = None
    if request.method == 'POST':
        # ابتدا از طریق شماره Cottage جستجو می‌کنیم
        cottage_number = request.POST.get('cottage_number')
        if cottage_number:
            try:
                cargo_product = CargoProduct.objects.get(cottage=cottage_number)
            except CargoProduct.DoesNotExist:
                messages.error(request, "کوتاژ با این شماره یافت نشد.")
                cargo_product = None
        
        # چک می‌کنیم آیا فرم خرید به صورت کامل ارسال شده است یا خیر
        if request.POST.get('purchase_form'):
            weight = request.POST.get('weight')
            amount_paid = request.POST.get('amount_paid')
            purchase_number = request.POST.get('purchase_number')
            tracking_number = request.POST.get('tracking_number')
            
            purchase = Purchase(
                customer=customer,
                weight=weight,
                amount_paid=amount_paid,
                purchase_number=purchase_number,
                tracking_number=tracking_number,
                cargo=cargo_product  # در صورت موجود بودن
            )
            try:
                purchase.full_clean()
                purchase.save()
                messages.success(request, "خرید جدید با موفقیت ثبت شد.")
            except ValidationError as e:
                messages.error(request, "خطا در ثبت خرید: " + str(e.message_dict))
            return redirect('customer_profile', customer_id=customer.id)
    
    return render(request, 'purchase_register.html', {
        'customer': customer,
        'cargo_product': cargo_product,
        'purchase': purchase
    })
 