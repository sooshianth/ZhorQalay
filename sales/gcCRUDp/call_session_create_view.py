from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct


def call_session_create_view(request, customer_id):
    """
    ویو ثبت تماس جدید برای مشتری.
    برای این ویو، ما مشتری را از طریق customer_id دریافت می‌کنیم.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        call_type = request.POST.get('call_type')
        call_status = request.POST.get('call_status')
        note = request.POST.get('note')
        
        new_call = CallSession(
            customer=customer,
            type=call_type,
            status=call_status,
            note=note
        )
        try:
            new_call.full_clean()
            new_call.save()
            messages.success(request, "تماس جدید با موفقیت ثبت شد.")
        except ValidationError as e:
            messages.error(request, "خطا در ثبت تماس: " + str(e.message_dict))
        return redirect('customer_profile', customer_id=customer.id)
    
    return render(request, 'call_session_create.html', {'customer': customer})
 