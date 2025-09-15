from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
import json
import uuid
import pandas as pd
from .models import AutomaticCall, CallLog, CallQueue
from core.CustomerModel import Customer


@login_required
def automatic_calls_dashboard(request):
    """
    داشبورد تماس‌های اتوماتیک
    """
    # آمار کلی
    total_calls = AutomaticCall.objects.count()
    pending_calls = AutomaticCall.objects.filter(status='pending').count()
    in_progress_calls = AutomaticCall.objects.filter(status='in_progress').count()
    completed_calls = AutomaticCall.objects.filter(status='completed').count()
    
    # تماس‌های اخیر
    recent_calls = AutomaticCall.objects.order_by('-created_at')[:10]
    
    context = {
        'total_calls': total_calls,
        'pending_calls': pending_calls,
        'in_progress_calls': in_progress_calls,
        'completed_calls': completed_calls,
        'recent_calls': recent_calls,
    }
    return render(request, 'calls/automatic_calls_dashboard.html', context)


@login_required
def automatic_calls_list(request):
    """
    لیست تماس‌های اتوماتیک
    """
    calls = AutomaticCall.objects.all().order_by('-created_at')
    
    # فیلترها
    status_filter = request.GET.get('status')
    call_type_filter = request.GET.get('call_type')
    search_query = request.GET.get('search')
    
    if status_filter:
        calls = calls.filter(status=status_filter)
    
    if call_type_filter:
        calls = calls.filter(call_type=call_type_filter)
    
    if search_query:
        calls = calls.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # صفحه‌بندی
    paginator = Paginator(calls, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # انتخاب‌ها برای فیلترها
    status_choices = AutomaticCall.CALL_STATUS_CHOICES
    call_type_choices = AutomaticCall.CALL_TYPE_CHOICES
    
    context = {
        'page_obj': page_obj,
        'status_choices': status_choices,
        'call_type_choices': call_type_choices,
        'current_status': status_filter,
        'current_call_type': call_type_filter,
        'current_search': search_query,
    }
    return render(request, 'calls/automatic_calls_list.html', context)


@login_required
def create_automatic_call(request):
    """
    ایجاد تماس اتوماتیک جدید - بر اساس صف
    """
    # ایجاد session_id برای این جلسه اگر وجود نداشته باشد
    session_id = request.session.get('call_queue_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['call_queue_session_id'] = session_id
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create_call':
            # ایجاد تماس نهایی
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            call_type = request.POST.get('call_type')
            scheduled_time = request.POST.get('scheduled_time')
            priority = request.POST.get('priority', 1)
            message_template = request.POST.get('message_template', '')
            asterisk_api_url = request.POST.get('asterisk_api_url', 'http://192.168.100.128:5000/api/start-dialer')
            asterisk_api_key = request.POST.get('asterisk_api_key', '')
            calls_per_minute = request.POST.get('calls_per_minute', 10)
            
            # اعتبارسنجی
            if not all([title, call_type, scheduled_time, calls_per_minute]):
                messages.error(request, 'لطفا تمام فیلدهای ضروری را پر کنید.')
                return redirect('calls:create_automatic_call')
            
            # بررسی وجود شماره در صف
            queue_count = CallQueue.objects.filter(session_id=session_id).count()
            if queue_count == 0:
                messages.error(request, 'لطفا حداقل یک شماره تلفن به صف اضافه کنید.')
                return redirect('calls:create_automatic_call')
            
            try:
                call = AutomaticCall.objects.create(
                    title=title,
                    description=description,
                    call_type=call_type,
                    scheduled_time=scheduled_time,
                    priority=int(priority),
                    message_template=message_template,
                    asterisk_api_url=asterisk_api_url,
                    asterisk_api_key=asterisk_api_key,
                    queue_session_id=session_id,
                    created_by=request.user,
                    calls_per_minute=int(calls_per_minute)
                )
                
                # ثبت لاگ
                CallLog.objects.create(
                    call=call,
                    event_type='created',
                    message=f'تماس اتوماتیک "{title}" با {queue_count} شماره ایجاد شد.'
                )
                
                # پاک کردن session
                del request.session['call_queue_session_id']
                
                messages.success(request, f'تماس اتوماتیک با {queue_count} شماره با موفقیت ایجاد شد.')
                return redirect('calls:automatic_call_detail', call_id=call.id)
                
            except Exception as e:
                messages.error(request, f'خطا در ایجاد تماس: {str(e)}')
    
    # دریافت شماره‌های فعلی در صف
    queue_numbers = CallQueue.objects.filter(session_id=session_id).order_by('-created_at')
    
    # انتخاب‌ها برای فرم
    call_type_choices = AutomaticCall.CALL_TYPE_CHOICES
    
    context = {
        'call_type_choices': call_type_choices,
        'queue_numbers': queue_numbers,
        'queue_count': queue_numbers.count(),
        'session_id': session_id,
    }
    return render(request, 'calls/create_automatic_call.html', context)


@login_required
def automatic_call_detail(request, call_id):
    """
    جزئیات تماس اتوماتیک
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # لاگ‌های تماس
    logs = call.logs.order_by('-timestamp')[:20]
    
    context = {
        'call': call,
        'logs': logs,
    }
    return render(request, 'calls/automatic_call_detail.html', context)


@login_required
def edit_automatic_call(request, call_id):
    """
    ویرایش تماس اتوماتیک - فقط برای تماس‌های در انتظار
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # بررسی اینکه تماس در وضعیت pending باشد
    if call.status != 'pending':
        messages.error(request, 'فقط تماس‌های در انتظار قابل ویرایش هستند.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    # دریافت session_id موجود یا ایجاد جدید
    session_id = call.queue_session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        call.queue_session_id = session_id
        call.save()
    
    # تنظیم session برای کار با queue
    request.session['call_queue_session_id'] = session_id
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_call':
            # به‌روزرسانی تماس
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            call_type = request.POST.get('call_type')
            scheduled_time = request.POST.get('scheduled_time')
            priority = request.POST.get('priority', 1)
            message_template = request.POST.get('message_template', '')
            asterisk_api_url = request.POST.get('asterisk_api_url', 'http://192.168.100.128:5000/api/start-dialer')
            asterisk_api_key = request.POST.get('asterisk_api_key', '')
            calls_per_minute = request.POST.get('calls_per_minute', 10)
            
            # اعتبارسنجی
            if not all([title, call_type, scheduled_time, calls_per_minute]):
                messages.error(request, 'لطفا تمام فیلدهای ضروری را پر کنید.')
                return redirect('calls:edit_automatic_call', call_id=call.id)
            
            # بررسی وجود شماره در صف
            queue_count = CallQueue.objects.filter(session_id=session_id).count()
            if queue_count == 0:
                messages.error(request, 'لطفا حداقل یک شماره تلفن به صف اضافه کنید.')
                return redirect('calls:edit_automatic_call', call_id=call.id)
            
            try:
                # به‌روزرسانی فیلدها
                call.title = title
                call.description = description
                call.call_type = call_type
                call.scheduled_time = scheduled_time
                call.priority = int(priority)
                call.message_template = message_template
                call.asterisk_api_url = asterisk_api_url
                call.asterisk_api_key = asterisk_api_key
                call.calls_per_minute = int(calls_per_minute)
                call.save()
                
                # ثبت لاگ
                CallLog.objects.create(
                    call=call,
                    event_type='updated',
                    message=f'تماس اتوماتیک "{title}" با {queue_count} شماره به‌روزرسانی شد.'
                )
                
                # پاک کردن session
                if 'call_queue_session_id' in request.session:
                    del request.session['call_queue_session_id']
                
                messages.success(request, f'تماس اتوماتیک با {queue_count} شماره با موفقیت به‌روزرسانی شد.')
                return redirect('calls:automatic_call_detail', call_id=call.id)
                
            except Exception as e:
                messages.error(request, f'خطا در به‌روزرسانی تماس: {str(e)}')
                return redirect('calls:edit_automatic_call', call_id=call.id)
        
        elif action in ['add_customer', 'add_manual', 'upload_excel', 'add_suggestions', 'remove_number']:
            # این actions توسط AJAX API های جداگانه handle می‌شوند
            pass
    
    # دریافت شماره‌های موجود در صف
    queue_numbers = CallQueue.objects.filter(session_id=session_id).order_by('-created_at')
    queue_stats = {
        'total': queue_numbers.count(),
        'from_customers': queue_numbers.filter(source='customer').count(),
        'manual': queue_numbers.filter(source='manual').count(),
        'suggestions': queue_numbers.filter(source='suggestion').count(),
        'excel': queue_numbers.filter(source='excel').count(),
    }
    
    # لیست مشتریان برای پیشنهاد
    all_customers = Customer.objects.all()[:100]  # محدود کردن برای بهبود عملکرد
    
    context = {
        'call': call,
        'queue_numbers': queue_numbers[:50],  # فقط 50 تای اول برای نمایش
        'queue_stats': queue_stats,
        'all_customers': all_customers,
        'session_id': session_id,
        'is_edit_mode': True,
    }
    return render(request, 'calls/edit_automatic_call.html', context)


@login_required
def stop_automatic_call(request, call_id):
    """
    متوقف کردن تماس اتوماتیک
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    if call.status != 'in_progress':
        messages.error(request, 'این تماس در حال انجام نیست.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    try:
        call.status = 'completed'
        call.end_time = timezone.now()
        call.save()
        
        # ثبت لاگ
        CallLog.objects.create(
            call=call,
            event_type='stopped',
            message=f'تماس اتوماتیک "{call.title}" متوقف شد.'
        )
        
        messages.success(request, 'تماس اتوماتیک با موفقیت متوقف شد.')
        
    except Exception as e:
        messages.error(request, f'خطا در متوقف کردن تماس: {str(e)}')
    
    return redirect('calls:automatic_call_detail', call_id=call.id)


@login_required
def delete_automatic_call(request, call_id):
    """
    حذف تماس اتوماتیک
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    if request.method == 'POST':
        call_title = call.title
        queue_session_id = call.queue_session_id
        
        # حذف صف مربوطه اگر وجود داشت
        if queue_session_id:
            queue_count = CallQueue.objects.filter(session_id=queue_session_id).count()
            CallQueue.objects.filter(session_id=queue_session_id).delete()
            
            messages.success(request, f'تماس اتوماتیک "{call_title}" و {queue_count} شماره از صف با موفقیت حذف شد.')
        else:
            messages.success(request, f'تماس اتوماتیک "{call_title}" با موفقیت حذف شد.')
        
        call.delete()
        return redirect('calls:automatic_calls_list')
    
    return render(request, 'calls/delete_automatic_call.html', {'call': call})


@login_required
def get_call_stats_api(request):
    """
    API برای دریافت آمار تماس‌ها
    """
    stats = {
        'total': AutomaticCall.objects.count(),
        'pending': AutomaticCall.objects.filter(status='pending').count(),
        'in_progress': AutomaticCall.objects.filter(status='in_progress').count(),
        'completed': AutomaticCall.objects.filter(status='completed').count(),
        'failed': AutomaticCall.objects.filter(status='failed').count(),
    }
    
    return JsonResponse(stats)

# Queue Management Views

@login_required
@require_http_methods(["POST"])
def add_customer_to_queue(request):
    """
    اضافه کردن مشتری به صف تماس
    """
    # تشخیص session_id از session یا call_id
    session_id = request.session.get('call_queue_session_id')
    call_id = request.POST.get('call_id')
    
    if call_id:
        # استفاده از call_id برای پیدا کردن session_id
        try:
            call = AutomaticCall.objects.get(id=call_id)
            if not call.queue_session_id:
                call.queue_session_id = str(uuid.uuid4())
                call.save()
            session_id = call.queue_session_id
        except AutomaticCall.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'تماس پیدا نشد'})
    
    if not session_id:
        return JsonResponse({'success': False, 'error': 'Session not found'})
    
    customer_id = request.POST.get('customer_id')
    if not customer_id:
        return JsonResponse({'success': False, 'error': 'Customer ID required'})
    
    try:
        customer = Customer.objects.get(id=customer_id)
        # دریافت شماره اصلی مشتری
        primary_phone = customer.phone_numbers.filter(is_primary=True).first()
        if not primary_phone:
            primary_phone = customer.phone_numbers.first()
        
        if not primary_phone:
            return JsonResponse({'success': False, 'error': 'مشتری شماره تلفن ندارد'})
        
        # اضافه کردن به صف (یا به‌روزرسانی اگر وجود داشت)
        queue_item, created = CallQueue.objects.get_or_create(
            session_id=session_id,
            phone_number=primary_phone.number,
            defaults={
                'customer': customer,
                'source': 'customer',
                'added_by': request.user
            }
        )
        
        if created:
            return JsonResponse({
                'success': True, 
                'message': f'مشتری {customer.name} اضافه شد',
                'phone_number': primary_phone.number,
                'customer_name': customer.name
            })
        else:
            return JsonResponse({'success': False, 'error': 'این شماره قبلاً اضافه شده است'})
            
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'مشتری یافت نشد'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["POST"])
def add_manual_numbers_to_queue(request):
    """
    اضافه کردن شماره‌های دستی به صف
    """
    # تشخیص session_id از session یا call_id
    session_id = request.session.get('call_queue_session_id')
    call_id = request.POST.get('call_id')
    
    if call_id:
        # استفاده از call_id برای پیدا کردن session_id
        try:
            call = AutomaticCall.objects.get(id=call_id)
            if not call.queue_session_id:
                call.queue_session_id = str(uuid.uuid4())
                call.save()
            session_id = call.queue_session_id
        except AutomaticCall.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'تماس پیدا نشد'})
    
    if not session_id:
        return JsonResponse({'success': False, 'error': 'Session not found'})
    
    numbers_text = request.POST.get('numbers', '')
    if not numbers_text:
        return JsonResponse({'success': False, 'error': 'هیچ شماره‌ای وارد نشده'})
    
    # پاکسازی و تفکیک شماره‌ها
    numbers = []
    for line in numbers_text.split('\n'):
        line = line.strip()
        if line:
            # حذف کاراکترهای غیرعددی و تنظیم فرمت
            clean_number = ''.join(c for c in line if c.isdigit())
            if clean_number:
                # حذف صفر ابتدایی و کد کشور
                if clean_number.startswith('0'):
                    clean_number = clean_number[1:]
                if clean_number.startswith('98'):
                    clean_number = clean_number[2:]
                if len(clean_number) >= 9:  # حداقل طول معقول
                    numbers.append(clean_number)
    
    if not numbers:
        return JsonResponse({'success': False, 'error': 'هیچ شماره معتبری یافت نشد'})
    
    added_count = 0
    duplicate_count = 0
    
    for number in numbers:
        try:
            # Try to find existing customer with this phone number
            customer = Customer.get_customer_by_phone(number)
            
            queue_item, created = CallQueue.objects.get_or_create(
                session_id=session_id,
                phone_number=number,
                defaults={
                    'customer': customer,
                    'source': 'manual',
                    'added_by': request.user
                }
            )
            if created:
                added_count += 1
            else:
                duplicate_count += 1
        except Exception:
            continue
    
    return JsonResponse({
        'success': True,
        'message': f'{added_count} شماره جدید اضافه شد. {duplicate_count} شماره تکراری.',
        'added': added_count,
        'duplicates': duplicate_count
    })


@login_required
@require_http_methods(["POST"])
def upload_excel_to_queue(request):
    """
    آپلود فایل اکسل یا CSV و اضافه کردن شماره‌ها به صف
    """
    # تشخیص session_id از session یا call_id
    session_id = request.session.get('call_queue_session_id')
    call_id = request.POST.get('call_id')
    
    if call_id:
        # استفاده از call_id برای پیدا کردن session_id
        try:
            call = AutomaticCall.objects.get(id=call_id)
            if not call.queue_session_id:
                call.queue_session_id = str(uuid.uuid4())
                call.save()
            session_id = call.queue_session_id
        except AutomaticCall.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'تماس پیدا نشد'})
    
    if not session_id:
        return JsonResponse({'success': False, 'error': 'Session not found'})

    if 'excel_file' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'فایل آپلود نشده'})

    excel_file = request.FILES['excel_file']

    try:
        # Check file extension to determine the format
        file_extension = excel_file.name.split('.')[-1].lower()
        if file_extension in ['xls', 'xlsx']:
            df = pd.read_excel(excel_file)
        elif file_extension == 'csv':
            df = pd.read_csv(excel_file)
        else:
            return JsonResponse({'success': False, 'error': 'فرمت فایل پشتیبانی نمی‌شود. فقط اکسل و CSV مجاز هستند.'})

        # جستجو برای ستون‌های احتمالی شماره تلفن
        phone_columns = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['phone', 'mobile', 'تلفن', 'موبایل', 'شماره']):
                phone_columns.append(col)

        if not phone_columns:
            # اگر ستون مشخصی پیدا نشد، از اولین ستون استفاده کن
            phone_columns = [df.columns[0]]

        numbers = []
        for col in phone_columns:
            for value in df[col].dropna():
                if pd.notna(value):
                    # تبدیل به رشته و پاکسازی
                    number_str = str(value).strip()
                    clean_number = ''.join(c for c in number_str if c.isdigit())
                    if clean_number:
                        # حذف صفر ابتدایی و کد کشور
                        if clean_number.startswith('0'):
                            clean_number = clean_number[1:]
                        if clean_number.startswith('98'):
                            clean_number = clean_number[2:]
                        if len(clean_number) >= 9:
                            numbers.append(clean_number)

        if not numbers:
            return JsonResponse({'success': False, 'error': 'هیچ شماره معتبری در فایل یافت نشد'})

        added_count = 0
        duplicate_count = 0

        for number in set(numbers):  # حذف تکراری‌ها
            try:
                # Try to find existing customer with this phone number
                customer = Customer.get_customer_by_phone(number)
                
                queue_item, created = CallQueue.objects.get_or_create(
                    session_id=session_id,
                    phone_number=number,
                    defaults={
                        'customer': customer,
                        'source': 'excel',
                        'added_by': request.user
                    }
                )
                if created:
                    added_count += 1
                else:
                    duplicate_count += 1
            except Exception:
                continue

        return JsonResponse({
            'success': True,
            'message': f'{added_count} شماره از فایل اضافه شد. {duplicate_count} شماره تکراری.',
            'added': added_count,
            'duplicates': duplicate_count
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'خطا در پردازش فایل: {str(e)}'})


@login_required
@require_http_methods(["POST"])
def add_suggested_numbers_to_queue(request):
    """
    اضافه کردن شماره‌های پیشنهادی به صف
    """
    # تشخیص session_id از session یا call_id
    session_id = request.session.get('call_queue_session_id')
    call_id = request.POST.get('call_id')
    
    if call_id:
        # استفاده از call_id برای پیدا کردن session_id
        try:
            call = AutomaticCall.objects.get(id=call_id)
            if not call.queue_session_id:
                call.queue_session_id = str(uuid.uuid4())
                call.save()
            session_id = call.queue_session_id
        except AutomaticCall.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'تماس پیدا نشد'})
    
    if not session_id:
        return JsonResponse({'success': False, 'error': 'Session not found'})
    
    # در اینجا می‌توانید منطق پیشنهاد شماره‌ها را پیاده‌سازی کنید
    # برای مثال، مشتریانی که اخیراً فعالیت داشته‌اند
    suggested_phones = Customer.objects.filter(
        phone_numbers__isnull=False
    ).exclude(
        phone_numbers__number__in=CallQueue.objects.filter(
            session_id=session_id
        ).values_list('phone_number', flat=True)
    ).values_list('phone_numbers__number', flat=True)[:50]
    
    added_count = 0
    for phone in suggested_phones:
        if phone:
            try:
                customer = Customer.objects.filter(phone_numbers__number=phone).first()
                queue_item, created = CallQueue.objects.get_or_create(
                    session_id=session_id,
                    phone_number=phone,
                    defaults={
                        'customer': customer,
                        'source': 'suggestion',
                        'added_by': request.user
                    }
                )
                if created:
                    added_count += 1
            except Exception:
                continue
    
    return JsonResponse({
        'success': True,
        'message': f'{added_count} شماره پیشنهادی اضافه شد',
        'added': added_count
    })


@login_required
@require_http_methods(["POST"])
def remove_from_queue(request):
    """
    حذف شماره یا شماره‌ها از صف
    """
    # تشخیص session_id از session یا call_id
    session_id = request.session.get('call_queue_session_id')
    call_id = request.POST.get('call_id')
    
    if call_id:
        # استفاده از call_id برای پیدا کردن session_id
        try:
            call = AutomaticCall.objects.get(id=call_id)
            session_id = call.queue_session_id
        except AutomaticCall.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'تماس پیدا نشد'})
    
    if not session_id:
        return JsonResponse({'success': False, 'error': 'Session not found'})
    
    # برای حذف چندتایی
    phone_numbers_json = request.POST.get('phone_numbers')
    if phone_numbers_json:
        try:
            import json
            phone_numbers = json.loads(phone_numbers_json)
            deleted_count = 0
            for phone_number in phone_numbers:
                try:
                    queue_item = CallQueue.objects.get(session_id=session_id, phone_number=phone_number)
                    queue_item.delete()
                    deleted_count += 1
                except CallQueue.DoesNotExist:
                    pass
            return JsonResponse({'success': True, 'message': f'{deleted_count} شماره از صف حذف شد'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    # برای حذف تکی
    phone_number = request.POST.get('phone_number')
    if not phone_number:
        return JsonResponse({'success': False, 'error': 'شماره تلفن مشخص نشده'})
    
    try:
        queue_item = CallQueue.objects.get(session_id=session_id, phone_number=phone_number)
        queue_item.delete()
        return JsonResponse({'success': True, 'message': 'شماره از صف حذف شد'})
    except CallQueue.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'شماره در صف یافت نشد'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def search_customers_api(request):
    """
    API برای جستجوی مشتریان
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    customers = Customer.objects.filter(
        Q(name__icontains=query) | 
        Q(phone_numbers__number__icontains=query)
    ).distinct()[:20]
    
    results = []
    for customer in customers:
        primary_phone = customer.phone_numbers.filter(is_primary=True).first()
        if not primary_phone:
            primary_phone = customer.phone_numbers.first()
        
        results.append({
            'id': customer.id,
            'name': customer.name,
            'phone': primary_phone.number if primary_phone else 'بدون شماره',
            'display': f"{customer.name} - {primary_phone.number if primary_phone else 'بدون شماره'}"
        })
    
    return JsonResponse({'results': results})


@login_required 
@require_http_methods(["POST"])
@login_required 
@require_http_methods(["POST"])
def start_asterisk_call(request, call_id):
    """
    شروع تماس از طریق Asterisk
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # Check if call is in the right status
    if call.status != 'pending':
        messages.error(request, 'این تماس قبلاً شروع شده یا تکمیل شده است.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    result = call.start_asterisk_call()
    
    if result['success']:
        messages.success(request, result['message'])
    else:
        messages.error(request, result['error'])
    
    return redirect('calls:automatic_call_detail', call_id=call.id)


@login_required
def get_queue_numbers(request):
    """
    API برای دریافت شماره‌های صف یک تماس خاص
    """
    call_id = request.GET.get('call_id')
    if not call_id:
        return JsonResponse({'success': False, 'error': 'call_id مورد نیاز است'})
    
    try:
        call = AutomaticCall.objects.get(id=call_id)
        
        # دریافت شماره‌های صف مربوط به این تماس
        if call.queue_session_id:
            queue_numbers = CallQueue.objects.filter(
                session_id=call.queue_session_id
            ).order_by('-created_at')
            
            numbers_data = []
            for item in queue_numbers:
                numbers_data.append({
                    'phone_number': item.phone_number,
                    'customer_name': item.customer.name if item.customer else None,
                    'source': item.source,
                    'source_display': item.get_source_display(),
                    'status': item.status,
                    'status_display': item.get_status_display(),
                    'call_duration': item.call_duration,
                    'assigned_agent': {
                        'id': item.assigned_agent.id,
                        'name': item.assigned_agent.get_full_name() or item.assigned_agent.username
                    } if item.assigned_agent else None,
                    'call_started_at': item.call_started_at.isoformat() if item.call_started_at else None,
                    'call_ended_at': item.call_ended_at.isoformat() if item.call_ended_at else None,
                })
            
            return JsonResponse({
                'success': True,
                'numbers': numbers_data
            })
        else:
            return JsonResponse({
                'success': True,
                'numbers': []
            })
    
    except AutomaticCall.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'تماس پیدا نشد'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# API endpoints for Asterisk integration
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
import json
from django.utils.dateparse import parse_datetime

@csrf_exempt
@require_POST
def asterisk_webhook_call_start(request):
    """
    Webhook for Asterisk to notify when a call starts
    Expected data:
    {
        "session_id": "uuid",
        "phone_number": "09123456789",
        "agent_id": 123,
        "timestamp": "2025-09-15T10:30:00Z"
    }
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        phone_number = data.get('phone_number')
        agent_id = data.get('agent_id')
        timestamp = data.get('timestamp')
        
        if not all([session_id, phone_number]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        # Find the queue item
        try:
            queue_item = CallQueue.objects.get(session_id=session_id, phone_number=phone_number)
        except CallQueue.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Queue item not found'}, status=404)
        
        # Update queue item status
        queue_item.status = 'calling'
        if timestamp:
            queue_item.call_started_at = parse_datetime(timestamp)
        else:
            queue_item.call_started_at = timezone.now()
        
        # Assign agent if provided
        if agent_id:
            try:
                agent = User.objects.get(id=agent_id)
                queue_item.assigned_agent = agent
            except User.DoesNotExist:
                pass
        
        queue_item.save()
        
        # Log the event
        try:
            call = AutomaticCall.objects.get(queue_session_id=session_id)
            CallLog.objects.create(
                call=call,
                event_type='call_start',
                message=f'تماس با {phone_number} شروع شد',
                details=data
            )
        except AutomaticCall.DoesNotExist:
            pass
        
        return JsonResponse({'success': True, 'message': 'Call start recorded'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def asterisk_webhook_call_end(request):
    """
    Webhook for Asterisk to notify when a call ends
    Expected data:
    {
        "session_id": "uuid",
        "phone_number": "09123456789",
        "status": "answered_ivr|answered_no_ivr|not_answered|busy",
        "duration": 45,
        "timestamp": "2025-09-15T10:32:30Z"
    }
    Note: 
    - answered_ivr: Call was answered and customer went through IVR (call ended)
    - answered_no_ivr: Call was answered but customer did not go through IVR (call ended)
    - not_answered: Call was not answered
    - busy: Line was busy
    """
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        phone_number = data.get('phone_number')
        status = data.get('status')
        duration = data.get('duration')
        timestamp = data.get('timestamp')
        
        if not all([session_id, phone_number, status]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'}, status=400)
        
        # Validate status
        valid_statuses = ['answered_ivr', 'answered_no_ivr', 'not_answered', 'busy']
        if status not in valid_statuses:
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        
        # Find the queue item
        try:
            queue_item = CallQueue.objects.get(session_id=session_id, phone_number=phone_number)
        except CallQueue.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Queue item not found'}, status=404)
        
        # Update queue item
        queue_item.status = status
        if duration is not None:
            queue_item.call_duration = duration
        if timestamp:
            queue_item.call_ended_at = parse_datetime(timestamp)
        else:
            queue_item.call_ended_at = timezone.now()
        
        queue_item.save()
        
        # Update AutomaticCall statistics
        try:
            call = AutomaticCall.objects.get(queue_session_id=session_id)
            
            # Update counters based on status
            if status in ['answered_ivr', 'answered_no_ivr']:
                call.successful_calls += 1
            elif status in ['not_answered', 'busy']:
                call.failed_calls += 1
            
            # Check if all calls are completed
            total_queue_items = CallQueue.objects.filter(session_id=session_id).count()
            completed_items = CallQueue.objects.filter(
                session_id=session_id, 
                status__in=['answered_ivr', 'answered_no_ivr', 'not_answered', 'busy']
            ).count()
            
            if completed_items >= total_queue_items:
                call.status = 'completed'
                call.end_time = timezone.now()
            
            call.save()
            
            # Log the event
            CallLog.objects.create(
                call=call,
                event_type='call_end',
                message=f'تماس با {phone_number} به پایان رسید. وضعیت: {status}',
                details=data
            )
            
        except AutomaticCall.DoesNotExist:
            pass
        
        return JsonResponse({'success': True, 'message': 'Call end recorded'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def get_call_queue_status(request, call_id):
    """
    API to get real-time status of all numbers in a call queue
    """
    try:
        call = AutomaticCall.objects.get(id=call_id)
        
        if not call.queue_session_id:
            return JsonResponse({'success': False, 'error': 'No queue session found'})
        
        queue_items = CallQueue.objects.filter(session_id=call.queue_session_id).select_related('assigned_agent', 'customer')
        
        queue_data = []
        for item in queue_items:
            queue_data.append({
                'phone_number': item.phone_number,
                'customer_name': item.customer.name if item.customer else None,
                'status': item.status,
                'status_display': item.get_status_display(),
                'call_duration': item.call_duration,
                'assigned_agent': {
                    'id': item.assigned_agent.id,
                    'name': item.assigned_agent.get_full_name() or item.assigned_agent.username
                } if item.assigned_agent else None,
                'call_started_at': item.call_started_at.isoformat() if item.call_started_at else None,
                'call_ended_at': item.call_ended_at.isoformat() if item.call_ended_at else None,
                'source': item.source,
                'source_display': item.get_source_display(),
            })
        
        # Calculate statistics
        total_count = len(queue_data)
        status_counts = {}
        for item in queue_items:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
        
        return JsonResponse({
            'success': True,
            'queue_data': queue_data,
            'statistics': {
                'total': total_count,
                'waiting': status_counts.get('waiting', 0),
                'calling': status_counts.get('calling', 0),
                'answered_ivr': status_counts.get('answered_ivr', 0),
                'answered_no_ivr': status_counts.get('answered_no_ivr', 0),
                'not_answered': status_counts.get('not_answered', 0),
                'busy': status_counts.get('busy', 0),
            }
        })
        
    except AutomaticCall.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Call not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
