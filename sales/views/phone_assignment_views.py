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
        import_method = request.POST.get('import_method')

        if import_method == 'paste':
            # بررسی نوع درخواست: کپی/پیست یا آپلود فایل
            try:
                with transaction.atomic():
                    sales_agent_id = request.POST.get('sales_agent')
                    phone_numbers_text = request.POST.get('phone_numbers', '')
                    
                    if not sales_agent_id:
                        return JsonResponse({'success': False, 'error': 'لطفا یک کارشناس فروش انتخاب کنید'})
                    
                    sales_agent = get_object_or_404(SalesAgent, id=sales_agent_id)
                    
                    # استخراج شماره‌ها از متن
                    phone_data = []
                    for line in phone_numbers_text.strip().split('\n'):
                        number = ''.join(c for c in line.strip() if c.isdigit())
                        if number:
                            # اعمال فرمت استاندارد (حذف صفر ابتدایی)
                            if number.startswith('0'):
                                number = number[1:]
                            # اطمینان از اینکه شماره با 9 شروع می‌شود و 10 رقم است
                            if number.startswith('9') and len(number) == 10:
                                phone_data.append({
                                    'phone_number': number,
                                    'customer_name': '',
                                    'sub_branch': '',
                                    'sub_branch_phone': '',
                                    'city': '',
                                    'user_type': ''
                                })
                    
                    if not phone_data:
                        return JsonResponse({'success': False, 'error': 'هیچ شماره معتبری یافت نشد'})
                    
                    # بررسی تکراری نبودن شماره‌ها
                    existing_numbers = set(PhoneAssignment.objects.filter(
                        phone_number__in=[item['phone_number'] for item in phone_data],
                        status='pending'
                    ).values_list('phone_number', flat=True))
                    
                    # بررسی مشتری بودن شماره‌ها
                    customer_numbers = set()
                    for item in phone_data:
                        if Customer.get_customer_by_phone(item['phone_number']):
                            customer_numbers.add(item['phone_number'])
                    
                    # تخصیص شماره‌های غیرتکراری و غیرمشتری
                    new_count = 0
                    for item in phone_data:
                        if item['phone_number'] not in existing_numbers and item['phone_number'] not in customer_numbers:
                            PhoneAssignment.objects.create(
                                phone_number=item['phone_number'],
                                sales_agent=sales_agent,
                                status='pending',
                                customer_name=item['customer_name'],
                                sub_branch=item['sub_branch'],
                                sub_branch_phone=item['sub_branch_phone'],
                                city=item['city'],
                                user_type=item['user_type']
                            )
                            new_count += 1
                    
                    return JsonResponse({
                        'success': True, 
                        'message': f"{new_count} شماره جدید به {sales_agent.name} تخصیص داده شد.",
                        'total': len(phone_data),
                        'new': new_count,
                        'existing': len(existing_numbers),
                        'customers': len(customer_numbers)
                    })
                    
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)})

        # اگر متد فایل بود یا متد مشخص نشده بود (برای سازگاری با فرم قبلی)
        else:
            form = PhoneImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        sales_agent = form.cleaned_data['sales_agent']
                        phone_data = form.extract_phone_numbers()
                        
                        if not phone_data:
                            messages.error(request, "هیچ شماره معتبری در فایل یا متن ورودی یافت نشد.")
                            return redirect('admin_import_phone_numbers')

                        # تمیز کردن داده‌ها
                        cleaned_phone_data = form.clean_phone_data(phone_data)
                        
                        if not cleaned_phone_data:
                            messages.error(request, "هیچ شماره معتبری پس از تمیز کردن یافت نشد.")
                            return redirect('admin_import_phone_numbers')

                        # بررسی تکراری نبودن شماره‌ها
                        existing_numbers = set(PhoneAssignment.objects.filter(
                            phone_number__in=[item['phone_number'] for item in cleaned_phone_data],
                            status='pending'
                        ).values_list('phone_number', flat=True))
                        
                        # بررسی مشتری بودن شماره‌ها
                        customer_numbers = set()
                        for item in cleaned_phone_data:
                            if Customer.get_customer_by_phone(item['phone_number']):
                                customer_numbers.add(item['phone_number'])
                        
                        # تخصیص شماره‌های غیرتکراری و غیرمشتری
                        new_count = 0
                        for item in cleaned_phone_data:
                            if item['phone_number'] not in existing_numbers and item['phone_number'] not in customer_numbers:
                                PhoneAssignment.objects.create(
                                    phone_number=item['phone_number'],
                                    sales_agent=sales_agent,
                                    status='pending',
                                    customer_name=item['customer_name'],
                                    sub_branch=item['sub_branch'],
                                    sub_branch_phone=item['sub_branch_phone'],
                                    city=item['city'],
                                    user_type=item['user_type']
                                )
                                new_count += 1
                        
                        # پیام موفقیت
                        messages.success(
                            request, 
                            f"{new_count} شماره جدید به {sales_agent.name} تخصیص داده شد. "
                            f"({len(existing_numbers)} شماره تکراری و {len(customer_numbers)} شماره مشتری یافت شد)."
                        )
                        return redirect('admin_phone_assignment_list')
                        
                except Exception as e:
                    messages.error(request, f"خطا در پردازش شماره‌ها: {str(e)}")
            else:
                # اگر فرم معتبر نبود، خطاها را نمایش بده
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"خطا در فیلد '{form.fields[field].label}': {error}")

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
def archive_phone_assignment(request, pk):
    """بایگانی کردن شماره تلفن از لیست"""
    phone_assignment = get_object_or_404(PhoneAssignment, id=pk)
    
    # بررسی دسترسی (فقط کارشناس مسئول یا ادمین)
    if not (request.user.is_staff or request.user.is_superuser or 
            hasattr(request.user, 'sales_agent') and request.user.sales_agent == phone_assignment.sales_agent):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'شما اجازه بایگانی این شماره را ندارید.'})
        messages.error(request, "شما اجازه بایگانی این شماره را ندارید.")
        return redirect('home')
    
    # بایگانی کردن شماره
    phone_assignment.archive()
    
    # اگر درخواست AJAX بود، JSON برگردان
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response = JsonResponse({
            'success': True, 
            'message': f'شماره {phone_assignment.phone_number} بایگانی شد.'
        })
        # اضافه کردن هدر برای حفظ موقعیت اسکرول
        response['X-Scroll-Position'] = 'preserved'
        return response
    
    # برای درخواست‌های عادی
    messages.success(request, f"شماره {phone_assignment.phone_number} بایگانی شد.")
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
    
    # حذف وابستگی به session
    # request.session['phone_assignment_id'] = pk
    
    # هدایت به صفحه ایجاد مشتری با پر کردن شماره تلفن و ارسال آیدی تخصیص
    base_url = reverse('general_customer_CRUD')
    query_params = f'?search_query={phone_assignment.phone_number}&assignment_id={pk}'
    return redirect(base_url + query_params)

@role_required('sales_agent', 'admin')
@login_required
def update_phone_notes(request, pk):
    """به‌روزرسانی یادداشت‌های مربوط به شماره تلفن"""
    phone_assignment = get_object_or_404(PhoneAssignment, id=pk)
    
    # بررسی دسترسی (فقط کارشناس مسئول یا ادمین)
    if not (request.user.is_staff or request.user.is_superuser or 
            hasattr(request.user, 'sales_agent') and request.user.sales_agent == phone_assignment.sales_agent):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'شما اجازه ویرایش این شماره را ندارید.'})
        messages.error(request, "شما اجازه ویرایش این شماره را ندارید.")
        return redirect('home')
    
    # فقط درخواست‌های POST پذیرفته می‌شوند
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        
        # ذخیره یادداشت جدید
        phone_assignment.notes = notes
        phone_assignment.save(update_fields=['notes'])
        
        # اگر درخواست AJAX بود، JSON برگردان
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': 'یادداشت با موفقیت ذخیره شد.'
            })
        
        # برای درخواست‌های عادی
        messages.success(request, "یادداشت با موفقیت ذخیره شد.")
        
        # بازگشت به صفحه قبل
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        
        # اگر referer موجود نبود، بسته به نقش کاربر به صفحه مناسب هدایت می‌شود
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_phone_assignment_list')
        else:
            return redirect('sales_phone_assignment_list')
    
    # درخواست‌های غیر POST پذیرفته نمی‌شوند
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'درخواست نامعتبر.'})
    messages.error(request, "درخواست نامعتبر.")
    return redirect('home')

@role_required('admin')
@login_required
@user_passes_test(is_admin)
def delete_phone_assignment(request, pk):
    """حذف کامل شماره تلفن تخصیص داده شده (فقط ادمین)"""
    phone_assignment = get_object_or_404(PhoneAssignment, id=pk)
    
    if request.method == 'POST':
        try:
            phone_number = phone_assignment.phone_number
            phone_assignment.delete()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'message': f'شماره {phone_number} با موفقیت حذف شد.'
                })
            
            messages.success(request, f"شماره {phone_number} با موفقیت حذف شد.")
            return redirect('admin_phone_assignment_list')
            
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'error': f'خطا در حذف شماره: {str(e)}'
                })
            
            messages.error(request, f"خطا در حذف شماره: {str(e)}")
            return redirect('admin_phone_assignment_list')
    
    # اگر درخواست GET بود، صفحه تأیید نمایش داده می‌شود
    context = {
        'phone_assignment': phone_assignment,
    }
    return render(request, 'phone_assignment/delete_confirm.html', context) 

@role_required('admin')
@login_required
@user_passes_test(is_admin)
def bulk_delete_phone_assignments(request):
    """حذف چندتایی شماره‌های تلفن تخصیص داده شده (فقط ادمین)"""
    if request.method == 'POST':
        try:
            assignment_ids = request.POST.getlist('selected_assignments')
            
            if not assignment_ids:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': 'هیچ شماره‌ای انتخاب نشده است.'
                    })
                messages.error(request, "هیچ شماره‌ای انتخاب نشده است.")
                return redirect('admin_phone_assignment_list')
            
            # تبدیل به عدد
            assignment_ids = [int(id) for id in assignment_ids if id.isdigit()]
            
            if not assignment_ids:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': 'شناسه‌های نامعتبر.'
                    })
                messages.error(request, "شناسه‌های نامعتبر.")
                return redirect('admin_phone_assignment_list')
            
            # حذف شماره‌ها
            deleted_count = 0
            phone_numbers = []
            
            with transaction.atomic():
                assignments = PhoneAssignment.objects.filter(id__in=assignment_ids)
                for assignment in assignments:
                    phone_numbers.append(assignment.phone_number)
                    assignment.delete()
                    deleted_count += 1
            
            success_message = f"{deleted_count} شماره تلفن با موفقیت حذف شد."
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'message': success_message,
                    'deleted_count': deleted_count
                })
            
            messages.success(request, success_message)
            return redirect('admin_phone_assignment_list')
            
        except Exception as e:
            error_message = f"خطا در حذف شماره‌ها: {str(e)}"
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 
                    'error': error_message
                })
            
            messages.error(request, error_message)
            return redirect('admin_phone_assignment_list')
    
    # درخواست‌های GET پذیرفته نمی‌شوند
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'درخواست نامعتبر.'})
    
    messages.error(request, "درخواست نامعتبر.")
    return redirect('admin_phone_assignment_list') 