# sales_main_page.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from core.CustomerModel import Customer
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from datetime import datetime
# در صورت استفاده از آبجکت Purchase باید آن را هم ایمپورت کنید (در صورتی که PurchaseModel موجود است)

def sales_main_page(request):
    """
    این view هم قابلیت جستجوی مشتری، ثبت تماس و ثبت تسک مربوط به مشتری را فراهم می‌کند.
    """
    customer = None

    if request.method == 'POST':
        # ثبت تماس جدید
        if 'record_call' in request.POST:
            phone_number = request.POST.get('phone_number')
            if not phone_number:
                messages.error(request, "شماره تلفن مشتری مشخص نشده است.")
                return render(request, 'customer_search_profile.html', {})

            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
                return render(request, 'customer_search_profile.html', {})

            # دریافت اطلاعات تماس
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
                new_call.full_clean()  # اعتبارسنجی اطلاعات
                new_call.save()
                messages.success(request, "تماس جدید با موفقیت ثبت شد.")
            except ValidationError as e:
                messages.error(request, "خطا در ثبت تماس: " + str(e.message_dict))

        # ثبت تسک جدید
        elif 'create_task' in request.POST:
            phone_number = request.POST.get('phone_number')
            if not phone_number:
                messages.error(request, "شماره تلفن مشتری مشخص نشده است.")
                return render(request, 'customer_search_profile.html', {})

            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")
                return render(request, 'customer_search_profile.html', {})

            # دریافت اطلاعات تسک از فرم
            task_description = request.POST.get('task_description')
            # دریافت به صورت اختیاری آبجکت Purchase (شناسه آن)
            purchase_id = request.POST.get('purchase_id')
            purchase = None
            if purchase_id:
                try:
                    purchase = Purchase.objects.get(id=purchase_id)
                except Purchase.DoesNotExist:
                    messages.warning(request, "آبجکت خرید (Purchase) مورد نظر یافت نشد. تسک بدون لینک کردن به خرید ثبت می‌شود.")

            # دریافت زمان مورد انتظار پیگیری در صورت وجود
            due_date_str = request.POST.get('due_date')
            due_date = None
            if due_date_str:
                # فرض بر این است که فرمت تاریخ به صورت "YYYY-MM-DD HH:MM" ارسال می‌شود
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%d %H:%M')
                except ValueError:
                    messages.warning(request, "فرمت تاریخ نادرست است، تاریخ مورد انتظار پیگیری نادیده گرفته می‌شود.")

            # ایجاد تسک جدید
            new_task = Task(
                decription=task_description,
                customer=customer,
                purchase=purchase,  # مقدار None در صورت نداشتن انتخاب
                due_date=due_date,
                status=False  # به عنوان پیش‌فرض به عنوان "انجام نشده"
            )
            # در صورتی که در مدل، sales_agent به صورت اتوماتیک (مثلاً از customer) تعریف نشده باشد، می‌توانید مقدار آن را به صورت دستی تنظیم کنید
            try:
                new_task.full_clean()
                new_task.save()
                messages.success(request, "تسک مربوط به مشتری با موفقیت ثبت شد.")
            except ValidationError as e:
                messages.error(request, "خطا در ثبت تسک: " + str(e.message_dict))

        # جستجوی مشتری (بدون ثبت تماس یا تسک)
        elif 'phone_number' in request.POST:
            phone_number = request.POST.get('phone_number')
            customer = Customer.objects.filter(phone_number__contains=phone_number).first()
            if not customer:
                messages.error(request, "مشتری با این شماره تلفن یافت نشد.")

    return render(request, 'customer_search_profile.html', {'customer': customer})
