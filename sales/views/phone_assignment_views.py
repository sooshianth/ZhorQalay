from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from core.SalesAgentModel import PhoneAssignment
from ..forms import PhoneImportForm, PhoneAssignmentForm
from core.SalesAgentModel import SalesAgent
from core.CustomerModel import Customer, PhoneNumber
from core._models import Customer as CustomerAlias
from core.decorators.decorators import role_required
def is_admin(user):
    """بررسی دسترسی ادمین"""
    return user.is_superuser or user.is_staff

@role_required('admin')
@login_required
@user_passes_test(is_admin)
def admin_import_phone_numbers(request):
    """ویو مدیریت آپلود شماره تلفن‌ها توسط ادمین"""
    form = PhoneImportForm()
    
    if request.method == 'POST':
        form = PhoneImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    sales_agent = form.cleaned_data['sales_agent']
                    phone_numbers = form.extract_phone_numbers()
                    
                    # بررسی تکراری نبودن شماره‌ها
                    existing_numbers = set(PhoneAssignment.objects.filter(
                        phone_number__in=phone_numbers,
                        status='pending'
                    ).values_list('phone_number', flat=True))
                    
                    # بررسی مشتری بودن شماره‌ها
                    customer_numbers = set()
                    for number in phone_numbers:
                        if Customer.get_customer_by_phone(number):
                            customer_numbers.add(number)
                    
                    # تخصیص شماره‌های غیرتکراری و غیرمشتری
                    new_count = 0
                    for number in phone_numbers:
                        if number not in existing_numbers and number not in customer_numbers:
                            PhoneAssignment.objects.create(
                                phone_number=number,
                                sales_agent=sales_agent,
                                status='pending'
                            )
                            new_count += 1
                    
                    # پیام موفقیت
                    messages.success(
                        request, 
                        f"{new_count} شماره جدید به {sales_agent.name} تخصیص داده شد. "
                        f"{len(existing_numbers)} شماره قبلاً تخصیص داده شده و "
                        f"{len(customer_numbers)} شماره قبلاً به عنوان مشتری ثبت شده‌اند."
                    )
                    return redirect('admin_phone_assignment_list')
                    
            except Exception as e:
                messages.error(request, f"خطا در پردازش شماره‌ها: {str(e)}")
    
    # لیست همه کارشناسان فروش برای نمایش در فرم
    sales_agents = SalesAgent.objects.all()
    
    context = {
        'form': form,
        'sales_agents': sales_agents,
    }
    
    return render(request, 'phone_assignment/admin_import.html', context)

@role_required('admin')
@login_required
def admin_phone_assignment_list(request):
    """ویو مدیریت لیست شماره تلفن‌های تخصیص داده شده توسط ادمین"""
    # فیلترها
    sales_agent_id = request.GET.get('sales_agent')
    status = request.GET.get('status', 'pending')
    
    phone_assignments = PhoneAssignment.objects.all().order_by('-created_at')
    
    if sales_agent_id:
        phone_assignments = phone_assignments.filter(sales_agent_id=sales_agent_id)
    
    if status:
        phone_assignments = phone_assignments.filter(status=status)
    
    # صفحه‌بندی
    paginator = Paginator(phone_assignments, 50)
    page = request.GET.get('page', 1)
    
    try:
        phone_assignments = paginator.page(page)
    except PageNotAnInteger:
        phone_assignments = paginator.page(1)
    except EmptyPage:
        phone_assignments = paginator.page(paginator.num_pages)
    
    # لیست کارشناسان فروش برای فیلتر
    sales_agents = SalesAgent.objects.all()
    
    context = {
        'phone_assignments': phone_assignments,
        'sales_agents': sales_agents,
        'selected_agent': sales_agent_id,
        'selected_status': status,
    }
    
    return render(request, 'phone_assignment/admin_list.html', context)

@role_required('sales_agent', 'admin')
@login_required
def sales_phone_assignment_list(request):
    """ویو نمایش شماره تلفن‌های تخصیص داده شده به کارشناس فروش"""
    try:
        sales_agent = SalesAgent.objects.get(user=request.user)
    except SalesAgent.DoesNotExist:
        messages.error(request, "شما به عنوان کارشناس فروش ثبت نشده‌اید.")
        return redirect('home')
    
    # فیلتر وضعیت (فقط شماره‌های در انتظار)
    phone_assignments = PhoneAssignment.objects.filter(
        sales_agent=sales_agent,
        status='pending'
    ).order_by('-created_at')
    
    # صفحه‌بندی
    paginator = Paginator(phone_assignments, 20)
    page = request.GET.get('page', 1)
    
    try:
        phone_assignments = paginator.page(page)
    except PageNotAnInteger:
        phone_assignments = paginator.page(1)
    except EmptyPage:
        phone_assignments = paginator.page(paginator.num_pages)
    
    context = {
        'phone_assignments': phone_assignments,
        'sales_agent': sales_agent,
    }
    
    return render(request, 'phone_assignment/sales_list.html', context)

@role_required('sales_agent', 'admin')
@login_required
def delete_phone_assignment(request, pk):
    """حذف شماره تلفن از لیست"""
    phone_assignment = get_object_or_404(PhoneAssignment, id=pk)
    
    # بررسی دسترسی (فقط کارشناس مسئول یا ادمین)
    if not (request.user.is_staff or request.user.is_superuser or 
            hasattr(request.user, 'sales_agent') and request.user.sales_agent == phone_assignment.sales_agent):
        messages.error(request, "شما اجازه حذف این شماره را ندارید.")
        return redirect('home')
    
    # علامت‌گذاری به عنوان حذف شده
    phone_assignment.mark_as_deleted()
    messages.success(request, f"شماره {phone_assignment.phone_number} حذف شد.")
    
    # بازگشت به صفحه قبل
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('sales_phone_assignment_list')))

@role_required('sales_agent', 'admin')
@login_required
def add_customer_from_assignment(request, pk):
    """تبدیل به مشتری جدید"""
    phone_assignment = get_object_or_404(PhoneAssignment, id=pk)
    
    # بررسی دسترسی (فقط کارشناس مسئول یا ادمین)
    if not (request.user.is_staff or request.user.is_superuser or 
            hasattr(request.user, 'sales_agent') and request.user.sales_agent == phone_assignment.sales_agent):
        messages.error(request, "شما اجازه تبدیل این شماره به مشتری را ندارید.")
        return redirect('home')
    
    # حذف کد تغییر وضعیت - این بخش در زمان ذخیره مشتری انجام خواهد شد
    # phone_assignment.mark_as_converted()
    
    # به session اضافه کردن شناسه شماره تلفن برای استفاده در زمان ایجاد مشتری
    request.session['phone_assignment_id'] = pk
    
    # هدایت به صفحه ایجاد مشتری با پر کردن شماره تلفن
    return redirect(reverse('general_customer_CRUD') + f'?search_query={phone_assignment.phone_number}') 