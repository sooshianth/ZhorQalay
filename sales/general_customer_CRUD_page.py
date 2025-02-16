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
    customer = None
    tasks = []
    call_sessions = []
    purchases = []

    if request.method == 'POST' and 'phone_number' in request.POST:
        # جستجوی مشتری
        phone_number = request.POST.get('phone_number')
        customer = Customer.objects.filter(phone_number__contains=phone_number).first()
        if not customer:
            messages.error(request, "مشتری یافت نشد!")
        else:
            # دریافت داده‌های مرتبط
            tasks = Task.objects.filter(customer=customer).order_by('-due_date')
            call_sessions = CallSession.objects.filter(customer=customer)
            purchases = Purchase.objects.filter(customer=customer)

    context = {
        'customer': customer,
        'tasks': tasks,
        'call_sessions': call_sessions,
        'purchases': purchases
    }
    return render(request, 'dashboard.html', context)