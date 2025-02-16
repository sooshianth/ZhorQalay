from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct



def customer_profile_view(request, customer_id):
    """
    ویو کلی نمایش پروفایل مشتری.
    این ویو قابلیت نمایش اطلاعات مشتری، تاریخچه تسک‌ها 
    و همچنین لینک‌های دسترسی به فرم‌های ثبت تماس، ثبت تسک و خرید را فراهم می‌کند.
    """
    customer = get_object_or_404(Customer, id=customer_id)
    tasks = customer.get_tasks_by_time()
    return render(request, 'customer_profile.html', {
        'customer': customer,
        'tasks': tasks
    })
 