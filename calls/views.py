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
import requests
from .models import AutomaticCall, CallLog, CallQueue
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct


@login_required
def automatic_calls_dashboard(request):
    """
    داشبورد تماس‌های اتوماتیک
    """
    # آمار کلی
    total_calls = AutomaticCall.objects.count()
    pending_calls = AutomaticCall.objects.filter(status='pending').count()
    in_progress_calls = AutomaticCall.objects.filter(status='in_progress').count()
    paused_calls = AutomaticCall.objects.filter(status='paused').count()
    completed_calls = AutomaticCall.objects.filter(status='completed').count()
    
    # تماس‌های اخیر
    recent_calls = AutomaticCall.objects.order_by('-created_at')[:10]
    
    context = {
        'total_calls': total_calls,
        'pending_calls': pending_calls,
        'in_progress_calls': in_progress_calls,
        'paused_calls': paused_calls,
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
    
    # بررسی وجود تماس فعال (در حال انجام)
    has_active_calls = AutomaticCall.objects.filter(status='in_progress').exists()
    
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
        'has_active_calls': has_active_calls,
    }
    return render(request, 'calls/automatic_calls_list.html', context)


@login_required
def create_automatic_call(request):
    """
    ایجاد تماس اتوماتیک جدید - بر اساس صف
    """
    # Always create a fresh session_id for new call creation
    # Don't reuse existing session to avoid mixing queue numbers between different calls
    if request.method == 'GET':
        # Clean up orphaned queue sessions periodically
        try:
            cleanup_orphaned_queue_sessions()
        except Exception:
            pass  # Don't let cleanup errors affect the main functionality
            
        # For GET requests (loading the page), always create a new session
        session_id = str(uuid.uuid4())
        request.session['call_queue_session_id'] = session_id
    else:
        # For POST requests, use the existing session from the current form
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
            
            # پردازش محصولات انتخاب شده برای تماس‌های بازاریابی
            selected_products = []
            if call_type == 'marketing':
                products_data = request.POST.get('products_data', '[]')
                try:
                    products_json = json.loads(products_data)
                    # Validate and format product data
                    for product_data in products_json:
                        if 'id' in product_data:
                            selected_products.append({
                                'id': product_data['id'],
                                'price': product_data.get('price', 0),
                                'cottage': product_data.get('cottage', ''),
                            })
                except json.JSONDecodeError:
                    selected_products = []
            
            # اعتبارسنجی
            if not all([title, call_type, scheduled_time, calls_per_minute]):
                messages.error(request, 'لطفا تمام فیلدهای ضروری را پر کنید.')
                return redirect('calls:create_automatic_call')
            
            # بررسی محصولات برای تماس‌های بازاریابی
            if call_type == 'marketing' and len(selected_products) == 0:
                messages.error(request, 'برای تماس‌های بازاریابی باید حداقل یک محصول انتخاب کنید.')
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
                    calls_per_minute=int(calls_per_minute),
                    selected_products=selected_products
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
    
    # محاسبه آمار صف
    queue_count = queue_numbers.count()
    customer_count = queue_numbers.filter(source='customer').count()
    manual_count = queue_numbers.filter(source='manual').count()
    
    # انتخاب‌ها برای فرم
    call_type_choices = AutomaticCall.CALL_TYPE_CHOICES
    
    # دریافت محصولات فعال برای نوع تماس بازاریابی
    cargo_products = CargoProduct.get_active_products()
    
    context = {
        'call_type_choices': call_type_choices,
        'queue_numbers': queue_numbers,
        'queue_count': queue_count,
        'customer_count': customer_count,
        'manual_count': manual_count,
        'session_id': session_id,
        'cargo_products': cargo_products,
    }
    return render(request, 'calls/create_automatic_call.html', context)


@login_required
def automatic_call_detail(request, call_id):
    """
    جزئیات تماس اتوماتیک
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # بررسی وجود تماس فعال (در حال انجام) غیر از تماس فعلی
    has_active_calls = AutomaticCall.objects.filter(status='in_progress').exclude(id=call_id).exists()
    
    # لاگ‌های تماس
    logs = call.logs.order_by('-timestamp')[:20]
    
    # دریافت محصولات انتخاب شده با جزئیات کامل
    selected_products_details = []
    if call.call_type == 'marketing' and call.selected_products:
        for product_data in call.selected_products:
            try:
                product_id = product_data.get('id')
                if product_id:
                    product = CargoProduct.objects.get(id=product_id)
                    product_info = {
                        'product': product,
                        'custom_price': product_data.get('price', product.customer_price),
                        'custom_cottage': product_data.get('cottage', product.cottage),
                    }
                    selected_products_details.append(product_info)
            except CargoProduct.DoesNotExist:
                continue
    
    context = {
        'call': call,
        'logs': logs,
        'has_active_calls': has_active_calls,
        'selected_products_details': selected_products_details,
    }
    return render(request, 'calls/automatic_call_detail.html', context)


@login_required
def edit_automatic_call(request, call_id):
    """
    ویرایش تماس اتوماتیک - برای تماس‌های در انتظار یا mid-call editing
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # بررسی مجوز ویرایش
    is_mid_call_edit = request.session.get('edit_mid_call', False)
    
    if not is_mid_call_edit and call.status != 'pending':
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
            
            # پردازش محصولات انتخاب شده برای تماس‌های بازاریابی
            selected_products = []
            if call_type == 'marketing':
                products_data = request.POST.get('products_data', '[]')
                try:
                    products_json = json.loads(products_data)
                    # Validate and format product data
                    for product_data in products_json:
                        if 'id' in product_data:
                            selected_products.append({
                                'id': product_data['id'],
                                'price': product_data.get('price', 0),
                                'cottage': product_data.get('cottage', ''),
                            })
                except json.JSONDecodeError:
                    selected_products = []
            
            # اعتبارسنجی
            if not all([title, call_type, scheduled_time, calls_per_minute]):
                messages.error(request, 'لطفا تمام فیلدهای ضروری را پر کنید.')
                return redirect('calls:edit_automatic_call', call_id=call.id)
            
            # بررسی محصولات برای تماس‌های بازاریابی
            if call_type == 'marketing' and len(selected_products) == 0:
                messages.error(request, 'برای تماس‌های بازاریابی باید حداقل یک محصول انتخاب کنید.')
                return redirect('calls:edit_automatic_call', call_id=call.id)
            
            # بررسی وجود شماره در صف
            queue_count = CallQueue.objects.filter(session_id=session_id).count()
            if queue_count == 0:
                messages.error(request, 'لطفا حداقل یک شماره تلفن به صف اضافه کنید.')
                return redirect('calls:edit_automatic_call', call_id=call.id)
            
            try:
                # ذخیره وضعیت قبلی برای mid-call editing
                original_status = request.session.get('original_call_status', call.status)
                
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
                call.selected_products = selected_products
                
                # برای mid-call editing، وضعیت را تغییر نده و از API Asterisk استفاده کن
                if is_mid_call_edit:
                    # حفظ وضعیت اصلی
                    call.status = original_status
                    
                    # ارسال به‌روزرسانی به API Asterisk
                    try:
                        headers = {'Content-Type': 'application/json'}
                        if call.asterisk_api_key:
                            headers['X-API-KEY'] = call.asterisk_api_key
                        
                        # آماده‌سازی داده‌ها برای Asterisk API
                        api_data = {
                            'call_id': call.id,
                            'title': call.title,
                            'description': call.description,
                            'call_type': call.call_type,
                            'scheduled_time': call.scheduled_time.isoformat(),
                            'priority': call.priority,
                            'message_template': call.message_template,
                            'calls_per_minute': call.calls_per_minute
                        }
                        
                        # اضافه کردن محصولات برای تماس‌های بازاریابی
                        if call.call_type == 'marketing':
                            api_products = []
                            for product_data in selected_products:
                                try:
                                    product = CargoProduct.objects.get(id=product_data['id'])
                                    api_product = {
                                        'name': product.product_type,
                                        'price': product_data.get('price', product.customer_price),
                                        'cottage': product_data.get('cottage', product.cottage),
                                        'country': product.country
                                    }
                                    api_products.append(api_product)
                                except CargoProduct.DoesNotExist:
                                    continue
                            api_data['products'] = api_products
                        
                        # ارسال به‌روزرسانی به Asterisk
                        edit_api_url = call.asterisk_api_url.replace('/api/start-dialer', '/api/edit-call')
                        response = requests.post(
                            edit_api_url,
                            headers=headers,
                            json=api_data,
                            timeout=30
                        )
                        
                        if response.status_code != 200:
                            messages.warning(request, f'تماس به‌روزرسانی شد اما خطا در ارسال به Asterisk: {response.status_code}')
                            
                    except requests.RequestException as e:
                        messages.warning(request, f'تماس به‌روزرسانی شد اما خطا در ارتباط با Asterisk: {str(e)}')
                
                call.save()
                
                # ثبت لاگ
                log_message = f'تماس اتوماتیک "{title}" با {queue_count} شماره به‌روزرسانی شد.'
                if is_mid_call_edit:
                    log_message += ' (ویرایش در حین تماس)'
                
                CallLog.objects.create(
                    call=call,
                    event_type='updated' if not is_mid_call_edit else 'updated_mid_call',
                    message=log_message
                )
                
                # پاک کردن session های مربوط به mid-call editing
                if 'call_queue_session_id' in request.session:
                    del request.session['call_queue_session_id']
                if 'edit_mid_call' in request.session:
                    del request.session['edit_mid_call']
                if 'original_call_status' in request.session:
                    del request.session['original_call_status']
                
                success_message = f'تماس اتوماتیک با {queue_count} شماره با موفقیت به‌روزرسانی شد.'
                if is_mid_call_edit:
                    success_message += ' اکنون می‌توانید تماس را ادامه دهید.'
                
                messages.success(request, success_message)
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
    
    # دریافت محصولات فعال برای نوع تماس بازاریابی
    cargo_products = CargoProduct.get_active_products()
    
    # آماده‌سازی داده‌های محصولات انتخاب شده برای JavaScript
    selected_products_json = json.dumps(call.selected_products) if call.selected_products else '[]'
    
    context = {
        'call': call,
        'queue_numbers': queue_numbers[:50],  # فقط 50 تای اول برای نمایش
        'queue_stats': queue_stats,
        'all_customers': all_customers,
        'cargo_products': cargo_products,
        'session_id': session_id,
        'is_edit_mode': True,
        'is_mid_call_edit': is_mid_call_edit,
        'selected_products_json': selected_products_json,
    }
    return render(request, 'calls/edit_automatic_call.html', context)


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
        'paused': AutomaticCall.objects.filter(status='paused').count(),
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
        if line.isdigit():
            numbers.append(line)

    if not numbers:
        return JsonResponse({'success': False, 'error': 'هیچ شماره‌ای وارد نشده'})
    
    added_count = 0
    duplicate_count = 0
    customer_count = 0
    manual_count = 0
    
    for number in numbers:
        try:
            # Try to find existing customer with this phone number
            customer = Customer.get_customer_by_phone(number)
            
            # Determine source based on whether customer exists
            source = 'customer' if customer else 'manual'
            
            queue_item, created = CallQueue.objects.get_or_create(
                session_id=session_id,
                phone_number=number,
                defaults={
                    'customer': customer,
                    'source': source,
                    'added_by': request.user
                }
            )
            if created:
                added_count += 1
                if customer:
                    customer_count += 1
                else:
                    manual_count += 1
            else:
                duplicate_count += 1
        except Exception:
            continue
    
    return JsonResponse({
        'success': True,
        'message': f'{added_count} شماره جدید اضافه شد. {duplicate_count} شماره تکراری.',
        'added': added_count,
        'duplicates': duplicate_count,
        'customer_count': customer_count,
        'manual_count': manual_count
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
        customer_count = 0
        manual_count = 0

        for number in set(numbers):  # حذف تکراری‌ها
            try:
                # Try to find existing customer with this phone number
                customer = Customer.get_customer_by_phone(number)
                
                # Determine source based on whether customer exists
                source = 'customer' if customer else 'manual'
                
                queue_item, created = CallQueue.objects.get_or_create(
                    session_id=session_id,
                    phone_number=number,
                    defaults={
                        'customer': customer,
                        'source': source,
                        'added_by': request.user
                    }
                )
                if created:
                    added_count += 1
                    if customer:
                        customer_count += 1
                    else:
                        manual_count += 1
                else:
                    duplicate_count += 1
            except Exception:
                continue

        return JsonResponse({
            'success': True,
            'message': f'{added_count} شماره از فایل اضافه شد. {duplicate_count} شماره تکراری.',
            'added': added_count,
            'duplicates': duplicate_count,
            'customer_count': customer_count,
            'manual_count': manual_count
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
    customer_count = 0
    for phone in suggested_phones:
        if phone:
            try:
                customer = Customer.objects.filter(phone_numbers__number=phone).first()
                queue_item, created = CallQueue.objects.get_or_create(
                    session_id=session_id,
                    phone_number=phone,
                    defaults={
                        'customer': customer,
                        'source': 'customer',  # Since these are all existing customers
                        'added_by': request.user
                    }
                )
                if created:
                    added_count += 1
                    customer_count += 1
            except Exception:
                continue
    
    return JsonResponse({
        'success': True,
        'message': f'{added_count} شماره پیشنهادی اضافه شد',
        'added': added_count,
        'customer_count': customer_count,
        'manual_count': 0
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
def start_asterisk_call(request, call_id):
    """
    شروع تماس از طریق Asterisk
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # Check if call is in the right status
    if call.status != 'pending':
        messages.error(request, 'این تماس قبلاً شروع شده یا تکمیل شده است.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    # Check if there are any other active calls
    active_calls = AutomaticCall.objects.filter(status='in_progress').exclude(id=call_id)
    if active_calls.exists():
        active_call_titles = ', '.join([active_call.title for active_call in active_calls[:3]])
        if active_calls.count() > 3:
            active_call_titles += f' و {active_calls.count() - 3} تماس دیگر'
        messages.error(request, f'تماس دیگری در حال انجام است: {active_call_titles}. لطفاً منتظر اتمام آن باشید.')
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
    API برای دریافت شماره‌های صف یک تماس خاص یا session
    """
    call_id = request.GET.get('call_id')
    session_id = request.GET.get('session_id')
    
    if not call_id and not session_id:
        return JsonResponse({'success': False, 'error': 'call_id یا session_id مورد نیاز است'})
    
    try:
        # If call_id is provided, get session_id from call
        if call_id:
            call = AutomaticCall.objects.get(id=call_id)
            session_id = call.queue_session_id
        
        # دریافت شماره‌های صف مربوط به این session
        if session_id:
            queue_numbers = CallQueue.objects.filter(
                session_id=session_id
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


@login_required
@require_POST
def pause_call_api(request, call_id):
    """
    API برای متوقف کردن موقت تماس اتوماتیک
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    if call.status != 'in_progress':
        return JsonResponse({
            'success': False, 
            'error': 'فقط تماس‌های در حال انجام قابل متوقف کردن موقت هستند.'
        })
    
    try:
        # ارسال درخواست به API Asterisk
        headers = {'Content-Type': 'application/json'}
        if call.asterisk_api_key:
            headers['X-API-KEY'] = call.asterisk_api_key
            
        data = {
            'call_id': call.id,
            'title': call.title
        }
        
        response = requests.post(
            f"{call.asterisk_api_url.replace('/api/start-dialer', '/api/pause-call')}",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            # به‌روزرسانی وضعیت به paused
            if 'paused' not in dict(AutomaticCall.CALL_STATUS_CHOICES):
                # اگر paused در choices نیست، از pending استفاده می‌کنیم
                call.status = 'pending'
            else:
                call.status = 'paused'
            call.save()
            
            # ثبت لاگ
            CallLog.objects.create(
                call=call,
                event_type='paused',
                message=f'تماس "{call.title}" موقتاً متوقف شد.'
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'تماس با موفقیت متوقف شد.'
            })
        else:
            return JsonResponse({
                'success': False, 
                'error': f'خطا در API: {response.status_code} - {response.text[:100]}'
            })
            
    except requests.RequestException as e:
        CallLog.objects.create(
            call=call,
            event_type='pause_error',
            message=f'خطا در متوقف کردن تماس: {str(e)}'
        )
        return JsonResponse({
            'success': False, 
            'error': f'خطا در ارتباط با سرور: {str(e)}'
        })


@login_required
@require_POST
def resume_call_api(request, call_id):
    """
    API برای ادامه دادن تماس اتوماتیک متوقف شده
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    if call.status not in ['pending', 'paused']:
        return JsonResponse({
            'success': False, 
            'error': 'فقط تماس‌های متوقف شده قابل ادامه دادن هستند.'
        })
    
    # Check if there are any other active calls
    active_calls = AutomaticCall.objects.filter(status='in_progress').exclude(id=call_id)
    if active_calls.exists():
        active_call_titles = ', '.join([active_call.title for active_call in active_calls[:3]])
        if active_calls.count() > 3:
            active_call_titles += f' و {active_calls.count() - 3} تماس دیگر'
        return JsonResponse({
            'success': False, 
            'error': f'تماس دیگری در حال انجام است: {active_call_titles}. لطفاً منتظر اتمام آن باشید.'
        })
    
    try:
        # ارسال درخواست به API Asterisk
        headers = {'Content-Type': 'application/json'}
        if call.asterisk_api_key:
            headers['X-API-KEY'] = call.asterisk_api_key
            
        data = {
            'call_id': call.id,
            'title': call.title
        }
        
        response = requests.post(
            f"{call.asterisk_api_url.replace('/api/start-dialer', '/api/resume-call')}",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            # به‌روزرسانی وضعیت به in_progress
            call.status = 'in_progress'
            call.save()
            
            # ثبت لاگ
            CallLog.objects.create(
                call=call,
                event_type='resumed',
                message=f'تماس "{call.title}" از سر گرفته شد.'
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'تماس با موفقیت از سر گرفته شد.'
            })
        else:
            return JsonResponse({
                'success': False, 
                'error': f'خطا در API: {response.status_code} - {response.text[:100]}'
            })
            
    except requests.RequestException as e:
        CallLog.objects.create(
            call=call,
            event_type='resume_error',
            message=f'خطا در ادامه دادن تماس: {str(e)}'
        )
        return JsonResponse({
            'success': False, 
            'error': f'خطا در ارتباط با سرور: {str(e)}'
        })


@login_required
@require_POST
def cancel_call_api(request, call_id):
    """
    API برای لغو تماس اتوماتیک (متفاوت از حذف)
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    if call.status not in ['pending', 'in_progress', 'paused']:
        return JsonResponse({
            'success': False, 
            'error': 'این تماس قابل لغو نیست.'
        })
    
    try:
        # ارسال درخواست به API Asterisk
        headers = {'Content-Type': 'application/json'}
        if call.asterisk_api_key:
            headers['X-API-KEY'] = call.asterisk_api_key
            
        data = {
            'call_id': call.id,
            'title': call.title
        }
        
        response = requests.post(
            f"{call.asterisk_api_url.replace('/api/start-dialer', '/api/cancel-call')}",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            # به‌روزرسانی وضعیت به cancelled
            call.status = 'cancelled'
            call.end_time = timezone.now()
            call.save()
            
            # ثبت لاگ
            CallLog.objects.create(
                call=call,
                event_type='cancelled',
                message=f'تماس "{call.title}" لغو شد.'
            )
            
            return JsonResponse({
                'success': True, 
                'message': 'تماس با موفقیت لغو شد.'
            })
        else:
            return JsonResponse({
                'success': False, 
                'error': f'خطا در API: {response.status_code} - {response.text[:100]}'
            })
            
    except requests.RequestException as e:
        CallLog.objects.create(
            call=call,
            event_type='cancel_error',
            message=f'خطا در لغو تماس: {str(e)}'
        )
        return JsonResponse({
            'success': False, 
            'error': f'خطا در ارتباط با سرور: {str(e)}'
        })

def cleanup_orphaned_queue_sessions():
    """
    Clean up queue sessions that are not associated with any saved call
    This helps prevent accumulation of orphaned queue numbers from abandoned call creation sessions
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Get all session IDs that are associated with existing calls
    active_session_ids = set(AutomaticCall.objects.exclude(
        queue_session_id__isnull=True
    ).values_list('queue_session_id', flat=True))
    
    # Find queue items that are not associated with any call and are older than 1 hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    orphaned_queue_items = CallQueue.objects.filter(
        created_at__lt=one_hour_ago
    ).exclude(
        session_id__in=active_session_ids
    )
    
    deleted_count = orphaned_queue_items.count()
    if deleted_count > 0:
        orphaned_queue_items.delete()
        print(f"Cleaned up {deleted_count} orphaned queue items")
    
    return deleted_count

@login_required
@require_POST
def edit_mid_call(request, call_id):
    """
    ویرایش تماس در حین انجام - ابتدا تماس را متوقف می‌کند، سپس به صفحه ویرایش می‌رود
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # بررسی وضعیت تماس
    if call.status not in ['in_progress', 'paused']:
        messages.error(request, 'فقط تماس‌های در حال انجام یا متوقف شده قابل ویرایش هستند.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    # اگر تماس در حال انجام است، ابتدا آن را متوقف کنیم
    if call.status == 'in_progress':
        try:
            # ارسال درخواست pause به API Asterisk
            headers = {'Content-Type': 'application/json'}
            if call.asterisk_api_key:
                headers['X-API-KEY'] = call.asterisk_api_key
                
            data = {
                'call_id': call.id,
                'title': call.title
            }
            
            response = requests.post(
                f"{call.asterisk_api_url.replace('/api/start-dialer', '/api/pause-call')}",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                # به‌روزرسانی وضعیت به paused
                call.status = 'paused'
                call.save()
                
                # ثبت لاگ
                CallLog.objects.create(
                    call=call,
                    event_type='paused_for_edit',
                    message=f'تماس "{call.title}" برای ویرایش موقتاً متوقف شد.'
                )
                
                messages.success(request, 'تماس موقتاً متوقف شد. اکنون می‌توانید آن را ویرایش کنید.')
            else:
                # اگر pause نشد، مستقیماً به ویرایش برو (ممکن است Asterisk پاسخ ندهد)
                messages.warning(request, 'خطا در متوقف کردن تماس، اما می‌توانید ویرایش کنید.')
                
        except requests.RequestException as e:
            # اگر خطا در ارتباط با Asterisk، مستقیماً به ویرایش برو
            messages.warning(request, 'خطا در ارتباط با سرور، اما می‌توانید ویرایش کنید.')
    
    # تنظیم فلگ برای نشان دادن اینکه این یک edit mid-call است
    request.session['edit_mid_call'] = True
    request.session['original_call_status'] = call.status
    
    return redirect('calls:edit_automatic_call', call_id=call.id)
