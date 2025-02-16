from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct


def customer_search_view(request):
    """
    ویو جستجوی مشتری بر اساس شماره تلفن.
    """
    customer = None
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')
        if not phone_number:
            messages.error(request, "شماره تلفن مشتری مشخص نشده است.")
        else:
            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
        # در اینجا می‌توانید بسته به نتیجه جستجو، یا مستقیماً به پروفایل مشتری هدایت کنید
        return render(request, 'customer_search_profile.html', {'customer': customer})
    return render(request, 'customer_search_profile.html')
 