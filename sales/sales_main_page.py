# sales_main_page.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from datetime import datetime
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct

def sales_main_page(request):
    """
    این view قابلیت‌های جستجوی مشتری، ثبت تماس، ثبت تسک، مشاهده تاریخچه تسک‌ها و ثبت خرید جدید را فراهم می‌کند.
    """
    customer = None
    tasks = None           # تاریخچه تسک‌ها
    cargo_product = None   # جزئیات CargoProduct در بخش خرید
    purchase = None        # آبجکت خرید جهت نمایش نتیجه نهایی
    
    if request.method == 'POST':
        
        # ------------------------ ثبت تماس ------------------------
        if 'record_call' in request.POST:
            phone_number = request.POST.get('phone_number')
            if not phone_number:
                messages.error(request, "شماره تلفن مشتری مشخص نشده است.")
                return render(request, 'customer_search_profile.html', {})
            
            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
                return render(request, 'customer_search_profile.html', {})
            
            # دریافت سایر اطلاعات تماس
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
        
        # ------------------------ ثبت تسک ------------------------
        elif 'create_task' in request.POST:
            phone_number = request.POST.get('phone_number')
            if not phone_number:
                messages.error(request, "شماره تلفن مشتری مشخص نشده است.")
                return render(request, 'customer_search_profile.html', {})
            
            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
                return render(request, 'customer_search_profile.html', {})
            
            task_description = request.POST.get('task_description')
            # دریافت شناسه خرید در صورت موجود بودن
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
        
        # ------------------------ مشاهده تاریخچه تسک‌ها ------------------------
        elif 'view_task_history' in request.POST:
            phone_number = request.POST.get('phone_number')
            if not phone_number:
                messages.error(request, "شماره تلفن مشتری مشخص نشده است.")
            else:
                customer = Customer.objects.filter(phone_number__contains=phone_number).first()
                if not customer:
                    messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
                else:
                    tasks = customer.get_tasks_by_time()  # دریافت تسک‌ها به ترتیب due_date
        
        # ------------------------ ثبت خرید جدید ------------------------
        elif 'register_purchase' in request.POST:
            # ابتدا شماره cottage جهت جستجوی CargoProduct دریافت می‌شود
            cottage_number = request.POST.get('cottage_number')
            if cottage_number:
                try:
                    cargo_product = CargoProduct.objects.get(cottage=cottage_number)
                except CargoProduct.DoesNotExist:
                    messages.error(request, "کوتاژ با این شماره یافت نشد.")
                    cargo_product = None
            
            # اگر فرم کامل خرید ارسال شده باشد
            if request.POST.get('purchase_form'):
                # فرض بر این است که مشتری قبل از این عملیات جستجو شده و شناسه او در فرم مخفی ارسال می‌شود
                customer_id = request.POST.get('customer_id')
                weight = request.POST.get('weight')
                amount_paid = request.POST.get('amount_paid')
                purchase_number = request.POST.get('purchase_number')
                tracking_number = request.POST.get('tracking_number')
                
                try:
                    customer = Customer.objects.get(id=customer_id)
                except Customer.DoesNotExist:
                    messages.error(request, "مشتری یافت نشد.")
                    customer = None
                
                # ثبت خرید جدید و لینك دادن به CargoProduct بدست آمده (در صورت موجود بودن)
                purchase = Purchase(
                    customer=customer,
                    weight=weight,
                    amount_paid=amount_paid,
                    purchase_number=purchase_number,
                    tracking_number=tracking_number,
                    cargo=cargo_product  # در صورتی که cargo_product معتبر است
                )
                try:
                    purchase.full_clean()
                    purchase.save()
                    messages.success(request, "خرید جدید با موفقیت ثبت شد.")
                except ValidationError as e:
                    messages.error(request, "خطا در ثبت خرید: " + str(e.message_dict))
        
        # ------------------------ جستجوی مشتری ------------------------
        elif 'phone_number' in request.POST:
            phone_number = request.POST.get('phone_number')
            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
    
    return render(request, 'customer_search_profile.html', {
        'customer': customer,
        'tasks': tasks,
        'cargo_product': cargo_product,
        'purchase': purchase
    })
