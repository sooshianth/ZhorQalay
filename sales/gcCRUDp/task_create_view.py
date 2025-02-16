from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct


def task_create_view(request, customer_id):
    """
    ویو ثبت تسک جدید برای مشتری.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == 'POST':
        task_description = request.POST.get('task_description')
        purchase_id = request.POST.get('purchase_id')
        purchase_obj = None
        if purchase_id:
            try:
                purchase_obj = Purchase.objects.get(id=purchase_id)
            except Purchase.DoesNotExist:
                messages.warning(request, "آبجکت خرید مورد نظر یافت نشد. ثبت تسک بدون لینک خرید انجام می‌شود.")
        
        due_date_str = request.POST.get('due_date')
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M')
            except ValueError:
                messages.warning(request, "فرمت تاریخ نادرست است، تاریخ نادیده گرفته می‌شود.")
        
        new_task = Task(
            decription=task_description,
            customer=customer,
            purchase=purchase_obj,
            due_date=due_date,
            status=False
        )
        try:
            new_task.full_clean()
            new_task.save()
            messages.success(request, "تسک مربوط به مشتری با موفقیت ثبت شد.")
        except ValidationError as e:
            messages.error(request, "خطا در ثبت تسک: " + str(e.message_dict))
        return redirect('customer_profile', customer_id=customer.id)
    
    return render(request, 'task_create.html', {'customer': customer})
 