from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct


def general_customer_CRUD_view(request):
    """
    ویو جامع مدیریت مشتری شامل:
    - جستجو با شماره تلفن
    - نمایش پروفایل و تاریخچه‌ها
    - ثبت تماس/تسک/خرید
    """
    customer = None
    tasks = []
    calls = []
    purchases = []
    cargo_product = None

    # بخش جستجوی مشتری
    if 'phone_search' in request.POST:
        phone_number = request.POST.get('phone_number')
        if phone_number:
            customer = Customer.get_customer_by_phone(phone_number)
            if not customer:
                messages.error(request, "مشتری یافت نشد")
            else:
                return redirect('general_customer_CRUD_view', customer_id=customer.id)

    # اگر customer_id وجود دارد (پروفایل بارگذاری شده)
    customer_id = request.GET.get('customer_id')
    if customer_id:
        customer = get_object_or_404(Customer, id=customer_id)
        
        # بارگیری داده‌های مرتبط
        tasks = customer.get_tasks_by_time
        calls = customer.get_calls_by_time
        purchases = customer.get_purchases_by_time

    # بخش ثبت تماس
    if 'create_call' in request.POST:
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
            messages.success(request, "تماس جدید ثبت شد")
        except ValidationError as e:
            messages.error(request, f"خطا در تماس: {e}")

    # بخش ثبت تسک
    if 'create_task' in request.POST:
        task_description = request.POST.get('task_description')
        due_date_str = request.POST.get('due_date')
        
        new_task = Task(
            description=task_description,
            customer=customer,
            due_date=datetime.strptime(due_date_str, '%Y-%m-%d %H:%M') if due_date_str else None,
            status=False
        )
        try:
            new_task.full_clean()
            new_task.save()
            messages.success(request, "تسک جدید ثبت شد")
        except ValidationError as e:
            messages.error(request, f"خطا در تسک: {e}")

    # بخش ثبت خرید
    if 'create_purchase' in request.POST:
        cottage_number = request.POST.get('cottage_number')
        weight = request.POST.get('weight')
        
        new_purchase = Purchase(
            customer=customer,
            weight=weight,
            cargo=CargoProduct.objects.get(cottage=cottage_number) if cottage_number else None
        )
        try:
            new_purchase.full_clean()
            new_purchase.save()
            messages.success(request, "خرید جدید ثبت شد")
        except Exception as e:
            messages.error(request, f"خطا در خرید: {e}")

    context = {
        'customer': customer,
        'tasks': tasks,
        'calls': calls,
        'purchases': purchases,
        'cargo_product': cargo_product,
    }
    return render(request, 'general_customer_CRUD_view.html', context)