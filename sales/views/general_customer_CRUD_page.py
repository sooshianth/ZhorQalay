from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from datetime import datetime
from core.CustomerModel import Customer, FIELD_OF_ACTIVITY
from core.CallSessionModel import CallSession
from core.TaskModel import Task
from core.PurchaseModel import Purchase  
from core.CargoProductModel import CargoProduct

# core/forms.py
from django import forms
from core.SalesAgentModel import SalesAgent

class CustomerForm(forms.ModelForm):
    field_of_activity = forms.ChoiceField(
        choices=FIELD_OF_ACTIVITY,
        label="حیطه فعالیت",
        required=False
    )

    def __init__(self, *args, **kwargs):
        sales_agent = kwargs.pop('sales_agent', None)
        super().__init__(*args, **kwargs)
        if sales_agent:
            self.fields['sales_agent'].initial = sales_agent
            self.fields['sales_agent'].disabled = True

    class Meta:
        model = Customer
        fields = '__all__'
        exclude = ['created_at', 'updated_at',  'contact_start_time', 'contact_end_time']
        widgets = {
            'contact_start_time': forms.TimeInput(attrs={'type': 'time'}),
            'contact_end_time': forms.TimeInput(attrs={'type': 'time'}),
            'added_description': forms.Textarea(attrs={'rows': 3}),
        }

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
    try:
        sales_agent = SalesAgent.objects.get(user=request.user)
    except SalesAgent.DoesNotExist:
        sales_agent = None

    form = None
    is_new_customer = False

    # بخش مدیریت فرم مشتری
    if request.method == "POST" and 'save_customer' in request.POST:
        phone = request.POST.get('phone_number')
        customer = Customer.get_customer_by_phone(phone)
        
        if customer:  # Update existing
            form = CustomerForm(request.POST, instance=customer, sales_agent=sales_agent)
        else:  # Create new
            form = CustomerForm(request.POST, sales_agent=sales_agent)
            is_new_customer = True
            
        if form.is_valid():
            saved_customer = form.save()
            msg = "مشتری با موفقیت بروزرسانی شد" if customer else "مشتری جدید ایجاد شد"
            messages.success(request, msg)
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={saved_customer.id}')
        else:
            messages.error(request, "خطا در فرم - لطفا مقادیر را بررسی کنید")

    # بخش جستجو
    elif request.method == "POST" and 'phone_search' in request.POST:
        phone_number = request.POST.get('phone_number')
        if phone_number:
            customer = Customer.get_customer_by_phone(phone_number)
            if customer:
                return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
            else:
                # Create a preliminary instance for a new customer
                customer = Customer(phone_number=phone_number)
                form = CustomerForm(instance=customer, sales_agent=sales_agent)
                is_new_customer = True

    # بارگیری مشتری موجود
    customer_id = request.GET.get('customer_id')
    if customer_id and not form:
        customer = get_object_or_404(Customer, id=customer_id)
        form = CustomerForm(instance=customer, sales_agent=sales_agent)
        tasks = customer.get_tasks_by_time()
        calls = customer.get_calls_by_time()
        purchases = customer.get_purchases_by_time()

    # بخش ثبت تماس
    if request.method == "POST" and 'create_call' in request.POST and customer:
        call_type = request.POST.get('call_type')
        call_status = request.POST.get('call_status')
        note = request.POST.get('note')
        
        new_call = CallSession(
            customer=customer,
            type=call_type,
            status='successful',
            note=note
        )
        try:
            new_call.full_clean()
            new_call.save()
            messages.success(request, "تماس جدید ثبت شد")
        except ValidationError as e:
            messages.error(request, f"خطا در تماس: {e}")
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

    # بخش ثبت تسک
    if request.method == "POST" and 'create_task' in request.POST and customer:
        task_description = request.POST.get('task_description')
        due_date_str = request.POST.get('due_date')
        
        new_task = Task(
            description=task_description,
            customer=customer,
            due_date=datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M') if due_date_str else None,  # توجه به فرمت datetime-local HTML
            status=False
        )
        try:
            new_task.full_clean()
            new_task.save()
            messages.success(request, "تسک جدید ثبت شد")
        except ValidationError as e:
            messages.error(request, f"خطا در تسک: {e}")
        return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')

    # بخش ثبت خرید
    if request.method == "POST" and 'create_purchase' in request.POST and customer:
        cottage_number = request.POST.get('cottage_number')
        weight = request.POST.get('weight')
        
        try:
            cargo = CargoProduct.objects.get(cottage=cottage_number) if cottage_number else None
        except CargoProduct.DoesNotExist:
            cargo = None

        new_purchase = Purchase(
            customer=customer,
            weight=weight,
            cargo=cargo
        )
        try:
            new_purchase.full_clean()
            new_purchase.save()
            messages.success(request, "خرید جدید ثبت شد")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
        except Exception as e:
            messages.error(request, f"خطا در خرید: {e}")
            return redirect(reverse('general_customer_CRUD') + f'?customer_id={customer.id}')
    active_products = CargoProduct.get_active_products()

    context = {
        'customer': customer,
        'form': form,
        'is_new_customer': is_new_customer,
        'tasks': tasks,
        'calls': calls,
        'purchases': purchases,
        'cargo_product': cargo_product,
        'active_products': active_products,
    }

    print( context )
    return render(request, 'general_customer_CRUD_view.html', context)
