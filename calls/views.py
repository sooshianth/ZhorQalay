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
import logging
from datetime import datetime, timedelta
from .models import AutomaticCall, CallLog, CallQueue
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct

# Set up logger for webhook events
logger = logging.getLogger('calls_webhook')


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
    
    # بررسی وجود تماس فعال (در حال انجام یا متوقف شده)
    has_active_calls = AutomaticCall.objects.filter(status__in=['in_progress', 'paused']).exists()
    
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
            cpm = request.POST.get('cpm', 10)
            
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
            if not all([title, call_type, scheduled_time, cpm]):
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
                # پارس کردن scheduled_time اگر string باشد
                if isinstance(scheduled_time, str):
                    scheduled_time_obj = parse_datetime(scheduled_time)
                    if not scheduled_time_obj:
                        # اگر parse نشد، سعی کن با فرمت‌های مختلف
                        try:
                            scheduled_time_obj = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                        except ValueError:
                            # اگر باز هم نشد، از زمان فعلی استفاده کن
                            scheduled_time_obj = timezone.now()
                else:
                    scheduled_time_obj = scheduled_time
                
                call = AutomaticCall.objects.create(
                    title=title,
                    description=description,
                    call_type=call_type,
                    scheduled_time=scheduled_time_obj,
                    priority=int(priority),
                    message_template=message_template,
                    asterisk_api_url=asterisk_api_url,
                    asterisk_api_key=asterisk_api_key,
                    queue_session_id=session_id,
                    created_by=request.user,
                    calls_per_minute=int(cpm),
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
    
    # بررسی وجود تماس فعال (در حال انجام یا متوقف شده) غیر از تماس فعلی
    has_active_calls = AutomaticCall.objects.filter(status__in=['in_progress', 'paused']).exclude(id=call_id).exists()
    
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
            cpm = request.POST.get('cpm', 10)
            
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
            if not all([title, call_type, scheduled_time, cpm]):
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
                
                # پارس کردن scheduled_time اگر string باشد
                if isinstance(scheduled_time, str):
                    scheduled_time_obj = parse_datetime(scheduled_time)
                    if not scheduled_time_obj:
                        # اگر parse نشد، سعی کن با فرمت‌های مختلف
                        try:
                            scheduled_time_obj = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                        except ValueError:
                            # اگر باز هم نشد، از زمان فعلی استفاده کن
                            scheduled_time_obj = timezone.now()
                else:
                    scheduled_time_obj = scheduled_time
                
                # به‌روزرسانی فیلدها
                call.title = title
                call.description = description
                call.call_type = call_type
                call.scheduled_time = scheduled_time_obj
                call.priority = int(priority)
                call.message_template = message_template
                call.asterisk_api_url = asterisk_api_url
                call.asterisk_api_key = asterisk_api_key
                call.calls_per_minute = int(cpm)
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
                        
                        # دریافت شماره‌های صف برای ارسال به API
                        queue_numbers = CallQueue.objects.filter(session_id=session_id).values_list('phone_number', flat=True)
                        numbers_list = list(queue_numbers)
                        
                        # آماده‌سازی داده‌ها برای Asterisk API
                        api_data = {
                            'numbers': numbers_list,  # Required field for edit-call API
                            'session_id': call.queue_session_id,  # Use queue_session_id as the unique identifier
                            # Removing call.id since we'll consistently use queue_session_id as the unique identifier
                            'title': call.title,
                            'description': call.description,
                            'call_type': call.call_type,
                            'scheduled_time': call.scheduled_time.strftime('%Y-%m-%dT%H:%M:%S'),
                            'priority': call.priority,
                            'message_template': call.message_template,
                            'cpm': call.calls_per_minute  # Use 'cpm' to match Flask API
                        }
                        
                        # اضافه کردن محصولات برای تماس‌های بازاریابی
                        if call.call_type == 'marketing' and selected_products:
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
    # در mid-call edit فقط شماره‌های با وضعیت 'waiting' قابل ویرایش هستند
    if is_mid_call_edit:
        queue_numbers = CallQueue.objects.filter(session_id=session_id, status='waiting').order_by('-created_at')
        messages.info(request, 'در حالت ویرایش حین تماس، فقط شماره‌های با وضعیت "در انتظار" قابل ویرایش هستند.')
    else:
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
    active_calls = AutomaticCall.objects.filter(status__in=['in_progress', 'paused']).exclude(id=call_id)
    if active_calls.exists():
        active_call_titles = ', '.join([active_call.title for active_call in active_calls[:3]])
        if active_calls.count() > 3:
            active_call_titles += f' و {active_calls.count() - 3} تماس دیگر'
        messages.error(request, f'تماس دیگری در حال انجام یا متوقف شده است: {active_call_titles}. لطفاً منتظر اتمام آن باشید.')
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
def asterisk_call_event_webhook(request):
    """
    Webhook for Asterisk to notify about various call events
    
    Expected data format from Asterisk API Notifier:
    {
        "event_type": "call_initiated|customer_answer|customer_hung_up_pre_ivr|customer_dtmf|
                       customer_entered_queue|customer_hung_up_in_queue|agent_answer|call_end|
                       customer_busy|customer_no_answer|call_rejected|call_failed",
        "timestamp": 1600000000,
        "call_data": {
            "uniqueid": "unique-call-id",
            "customer_number": "09123456789",
            "agent_number": "1001",             # Only for some events
            "digit_pressed": "1",               # Only for DTMF events
            "queue_extension": "2000",          # Only for queue events
            "duration": "45",                   # Only for call_end and hung up events
            "call_direction": "inbound|outbound" # Only for call_initiated
        }
    }
    """
    logger.warning("Webhook called with method: %s, content_type: %s", request.method, request.content_type)
    
    try:
        # Parse incoming JSON data
        data = json.loads(request.body)
        event_type = data.get('event_type')
        timestamp = data.get('timestamp')
        call_data = data.get('call_data', {})
        
        # Log received data
        logger.info("Received webhook event: %s for call %s", 
                   event_type, call_data.get('uniqueid', 'unknown'))
        
        # Get required fields
        uniqueid = call_data.get('uniqueid')
        customer_number = call_data.get('customer_number')
        
        # Validate basic required fields
        if not all([event_type, uniqueid, customer_number]):
            error_msg = "Missing required fields in webhook data"
            logger.error(error_msg + ": %s", data)
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        
        # Convert timestamp if needed
        event_time = datetime.fromtimestamp(timestamp) if timestamp else timezone.now()
        
        # Find the queue item
        try:
            # Use uniqueid as session_id to find the call
            call = AutomaticCall.objects.get(queue_session_id=uniqueid)
            # Find the queue item
            queue_item = CallQueue.objects.filter(
                session_id=uniqueid, 
                phone_number=customer_number
            ).first()
            
            if not queue_item:
                error_msg = f"Queue item not found for call {uniqueid}, customer {customer_number}"
                logger.error(error_msg)
                return JsonResponse({'success': False, 'error': error_msg}, status=404)
                
        except AutomaticCall.DoesNotExist:
            error_msg = f"Call not found with session_id {uniqueid}"
            logger.error(error_msg)
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        
        # Ensure customer_number is stored consistently in webhook data for better searching
        if 'call_data' in data:
            data['call_data']['customer_number'] = customer_number
        
        # Log processing information
        logger.info("Processing %s event for call %s, customer %s", 
                   event_type, uniqueid, customer_number)
        
        # Process different event types
        if event_type == 'call_initiated':
            logger.info("Call initiated for %s, setting status to 'calling'", customer_number)
            queue_item.status = 'calling'
            queue_item.call_started_at = event_time
            queue_item.save()
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='call_initiated',
                message=f'تماس با {customer_number} شروع شد',
                details=data
            )
            
        elif event_type == 'customer_answer':
            logger.info("Customer %s answered the call, setting status to 'answered'", customer_number)
            queue_item.status = 'answered'
            queue_item.call_started_at = event_time  # Update call start time
            queue_item.save()
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='customer_answer',
                message=f'مشتری {customer_number} به تماس پاسخ داد',
                details=data
            )
            
        elif event_type == 'customer_hung_up_pre_ivr':
            queue_item.status = 'answered_no_ivr'
            queue_item.call_ended_at = event_time
            queue_item.save()
            
            # Update call statistics
            call.successful_calls += 1
            call.save()
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='customer_hung_up_pre_ivr',
                message=f'مشتری {customer_number} قبل از IVR قطع کرد',
                details=data
            )
            
        elif event_type == 'customer_dtmf':
            digit = call_data.get('digit_pressed', 'نامشخص')
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='customer_dtmf',
                message=f'مشتری {customer_number} کلید {digit} را فشرد',
                details=data
            )
            
        elif event_type == 'customer_entered_queue':
            queue_extension = call_data.get('queue_extension', 'نامشخص')
            
            logger.info("Customer %s entered queue %s", customer_number, queue_extension)
            
            # Update status to in_queue
            queue_item.status = 'in_queue'
            queue_item.save()
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='customer_entered_queue',
                message=f'مشتری {customer_number} وارد صف {queue_extension} شد',
                details=data
            )
            
        elif event_type == 'customer_hung_up_in_queue':
            duration = call_data.get('duration')
            
            queue_item.status = 'hung_up_in_queue'
            if duration:
                queue_item.call_duration = duration
            queue_item.call_ended_at = event_time
            queue_item.save()
            
            # Update call statistics
            call.successful_calls += 1
            call.save()
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='customer_hung_up_in_queue',
                message=f'مشتری {customer_number} در صف قطع کرد',
                details=data
            )
            
        elif event_type == 'agent_answer':
            agent_number = call_data.get('agent_number')
            
            # Try to find the agent by extension
            if agent_number:
                # This is an example - you would need to map agent_number to actual User
                # For example if you store extension in user profile or other field
                try:
                    # This is a placeholder - implement based on your actual User model
                    # For example: agent = User.objects.get(profile__extension=agent_number)
                    # Or using filter + first() if it's not unique
                    agent = None
                    if agent:
                        queue_item.assigned_agent = agent
                        queue_item.save()
                except Exception:
                    pass
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='agent_answer',
                message=f'کارشناس با شماره {agent_number} به تماس با {customer_number} پاسخ داد',
                details=data
            )
            
        elif event_type == 'call_end':
            agent_number = call_data.get('agent_number')
            duration = call_data.get('duration')
            
            queue_item.status = 'answered_ivr'  # Assuming full call completion
            if duration:
                queue_item.call_duration = duration
            queue_item.call_ended_at = event_time
            queue_item.save()
            
            # Update call statistics
            call.successful_calls += 1
            
            # Check if all calls are completed
            total_queue_items = CallQueue.objects.filter(session_id=uniqueid).count()
            completed_items = CallQueue.objects.filter(
                session_id=uniqueid, 
                status__in=['answered_ivr', 'answered_no_ivr', 'not_answered', 'busy', 'failed', 'rejected', 'hung_up_in_queue']
            ).count()
            
            if completed_items >= total_queue_items:
                call.status = 'completed'
                call.end_time = event_time
            
            call.save()
            
            # Log event
            CallLog.objects.create(
                call=call,
                event_type='call_end',
                message=f'تماس با {customer_number} پایان یافت. مدت: {duration} ثانیه',
                details=data
            )
            
        # Handle failure cases
        elif event_type in ['customer_busy', 'customer_no_answer', 'call_rejected', 'call_failed']:
            # Map event types to queue statuses
            status_map = {
                'customer_busy': 'busy',
                'customer_no_answer': 'not_answered',
                'call_rejected': 'rejected',
                'call_failed': 'failed'
            }
            
            logger.info("Call failure event: %s for customer %s", event_type, customer_number)
            
            # Set call start time if not already set
            if not queue_item.call_started_at:
                queue_item.call_started_at = event_time
            
            queue_item.status = status_map.get(event_type, 'failed')
            queue_item.call_ended_at = event_time
            queue_item.save()
            
            # Update call statistics
            call.failed_calls += 1
            
            # Check if all calls are completed
            total_queue_items = CallQueue.objects.filter(session_id=uniqueid).count()
            completed_items = CallQueue.objects.filter(
                session_id=uniqueid, 
                status__in=['answered_ivr', 'answered_no_ivr', 'not_answered', 'busy', 'failed', 'rejected', 'hung_up_in_queue']
            ).count()
            
            if completed_items >= total_queue_items:
                call.status = 'completed'
                call.end_time = event_time
            
            call.save()
            
            # Log event
            message_map = {
                'customer_busy': f'مشتری {customer_number} مشغول بود',
                'customer_no_answer': f'مشتری {customer_number} پاسخ نداد',
                'call_rejected': f'تماس با {customer_number} رد شد',
                'call_failed': f'تماس با {customer_number} با خطا مواجه شد'
            }
            
            CallLog.objects.create(
                call=call,
                event_type=event_type,
                message=message_map.get(event_type, f'تماس با {customer_number} ناموفق بود'),
                details=data
            )
        
        else:
            # Unknown event type
            logger.warning("Unknown event type '%s' received for call %s, customer %s", 
                          event_type, uniqueid, customer_number)
            
            CallLog.objects.create(
                call=call,
                event_type='unknown_event',
                message=f'رویداد ناشناخته {event_type} برای تماس با {customer_number}',
                details=data
            )
        
        logger.info("Successfully processed %s event for call %s", event_type, uniqueid)
        return JsonResponse({'success': True, 'message': f'{event_type} event processed'})
        
    except json.JSONDecodeError:
        error_msg = "Invalid JSON in webhook request"
        logger.error("%s: %s", error_msg, request.body)
        return JsonResponse({'success': False, 'error': error_msg}, status=400)
    except Exception as e:
        logger.exception("Webhook processing error: %s", str(e))
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
                'failed': status_counts.get('failed', 0),
                'rejected': status_counts.get('rejected', 0),
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
            'session_id': call.queue_session_id,  # Use queue_session_id instead of call.id for consistency
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
    active_calls = AutomaticCall.objects.filter(status__in=['in_progress', 'paused']).exclude(id=call_id)
    if active_calls.exists():
        active_call_titles = ', '.join([active_call.title for active_call in active_calls[:3]])
        if active_calls.count() > 3:
            active_call_titles += f' و {active_calls.count() - 3} تماس دیگر'
        return JsonResponse({
            'success': False, 
            'error': f'تماس دیگری در حال انجام یا متوقف شده است: {active_call_titles}. لطفاً منتظر اتمام آن باشید.'
        })
    
    try:
        # ارسال درخواست به API Asterisk
        headers = {'Content-Type': 'application/json'}
        if call.asterisk_api_key:
            headers['X-API-KEY'] = call.asterisk_api_key
            
        data = {
            'session_id': call.queue_session_id,  # Use queue_session_id instead of call.id for consistency
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
            'session_id': call.queue_session_id,  # Use queue_session_id instead of call.id for consistency
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
    فقط شماره‌های با وضعیت 'waiting' قابل ویرایش هستند
    """
    call = get_object_or_404(AutomaticCall, id=call_id)
    
    # بررسی وضعیت تماس
    if call.status not in ['in_progress', 'paused']:
        messages.error(request, 'فقط تماس‌های در حال انجام یا متوقف شده قابل ویرایش هستند.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    # بررسی تعداد شماره‌های با وضعیت 'waiting' در صف
    waiting_numbers = CallQueue.objects.filter(session_id=call.queue_session_id, status='waiting').count()
    
    if waiting_numbers == 0:
        messages.error(request, 'هیچ شماره‌ای با وضعیت انتظار برای ویرایش وجود ندارد.')
        return redirect('calls:automatic_call_detail', call_id=call.id)
    
    # اگر تماس در حال انجام است، ابتدا آن را متوقف کنیم
    if call.status == 'in_progress':
        try:
            # ارسال درخواست pause به API Asterisk
            headers = {'Content-Type': 'application/json'}
            if call.asterisk_api_key:
                headers['X-API-KEY'] = call.asterisk_api_key
                
            data = {
                'session_id': call.queue_session_id,  # Use queue_session_id instead of call.id for consistency
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
                
                messages.success(request, f'تماس موقتاً متوقف شد. اکنون می‌توانید {waiting_numbers} شماره با وضعیت انتظار را ویرایش کنید.')
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

@login_required
@require_POST
def retry_automatic_call(request, call_id):
    """
    تکرار تماس اتوماتیک - ایجاد تماس جدید با تنظیمات مشابه اما session ID متفاوت
    """
    original_call = get_object_or_404(AutomaticCall, id=call_id)
    
    # بررسی وضعیت تماس - فقط تماس‌های تکمیل شده، لغو شده یا ناموفق قابل تکرار هستند
    if original_call.status not in ['completed', 'cancelled', 'failed']:
        messages.error(request, 'فقط تماس‌های تکمیل شده، لغو شده یا ناموفق قابل تکرار هستند.')
        return redirect('calls:automatic_call_detail', call_id=call_id)
    
    # بررسی وجود تماس فعال
    active_calls = AutomaticCall.objects.filter(status__in=['in_progress', 'paused'])
    if active_calls.exists():
        active_call_titles = ', '.join([active_call.title for active_call in active_calls[:3]])
        if active_calls.count() > 3:
            active_call_titles += f' و {active_calls.count() - 3} تماس دیگر'
        messages.error(request, f'تماس دیگری در حال انجام یا متوقف شده است: {active_call_titles}. لطفاً منتظر اتمام آن باشید.')
        return redirect('calls:automatic_call_detail', call_id=call_id)
    
    try:
        # ایجاد session ID جدید
        new_session_id = str(uuid.uuid4())
        
        # کپی کردن شماره‌های قدیمی به session جدید
        if original_call.queue_session_id:
            old_queue_numbers = CallQueue.objects.filter(session_id=original_call.queue_session_id)
            copied_count = 0
            
            for old_queue_item in old_queue_numbers:
                # ایجاد شماره جدید در صف جدید
                CallQueue.objects.create(
                    session_id=new_session_id,
                    phone_number=old_queue_item.phone_number,
                    customer=old_queue_item.customer,
                    source=old_queue_item.source,
                    added_by=request.user,
                    status='waiting'  # همه شماره‌ها در وضعیت انتظار
                )
                copied_count += 1
            
            if copied_count == 0:
                messages.error(request, 'هیچ شماره‌ای برای کپی کردن یافت نشد.')
                return redirect('calls:automatic_call_detail', call_id=call_id)
        else:
            messages.error(request, 'تماس اصلی فاقد شماره‌های صف است.')
            return redirect('calls:automatic_call_detail', call_id=call_id)
        
        # ایجاد تماس جدید با تنظیمات مشابه
        new_call = AutomaticCall.objects.create(
            title=f"{original_call.title} (تکرار)",
            description=original_call.description,
            call_type=original_call.call_type,
            scheduled_time=timezone.now(),  # زمان فعلی
            priority=original_call.priority,
            message_template=original_call.message_template,
            asterisk_api_url=original_call.asterisk_api_url,
            asterisk_api_key=original_call.asterisk_api_key,
            queue_session_id=new_session_id,
            created_by=request.user,
            calls_per_minute=original_call.calls_per_minute,
            selected_products=original_call.selected_products,
            status='pending'  # وضعیت در انتظار
        )
        
        # ثبت لاگ برای تماس جدید
        CallLog.objects.create(
            call=new_call,
            event_type='retried',
            message=f'تماس از "{original_call.title}" (ID: {original_call.id}) تکرار شد با {copied_count} شماره.'
        )
        
        # ثبت لاگ برای تماس اصلی
        CallLog.objects.create(
            call=original_call,
            event_type='retry_created',
            message=f'تماس جدید با ID {new_call.id} از این تماس ایجاد شد.'
        )
        
        messages.success(request, f'تماس با موفقیت تکرار شد. تماس جدید با {copied_count} شماره ایجاد شد.')
        return redirect('calls:automatic_call_detail', call_id=new_call.id)
        
    except Exception as e:
        messages.error(request, f'خطا در تکرار تماس: {str(e)}')
        return redirect('calls:automatic_call_detail', call_id=call_id)

@login_required
def get_queue_item_details(request):
    """
    API برای دریافت جزئیات کامل یک آیتم خاص از صف تماس
    """
    session_id = request.GET.get('session_id')
    phone_number = request.GET.get('phone_number')
    
    if not session_id or not phone_number:
        return JsonResponse({'success': False, 'error': 'session_id و phone_number مورد نیاز است'})
    
    try:
        queue_item = CallQueue.objects.get(session_id=session_id, phone_number=phone_number)
        
        # Get all logs related to this phone number from CallLog (created by asterisk webhook)
        call_logs = []
        timeline_events = []
        
        try:
            call = AutomaticCall.objects.get(queue_session_id=session_id)
            
            # Get logs that mention this phone number
            logs = CallLog.objects.filter(call=call).filter(
                Q(message__icontains=phone_number) | 
                Q(details__call_data__customer_number=phone_number) |
                Q(details__call_data__customer_phone=phone_number) |
                Q(details__call_data__phone_number=phone_number)
            ).order_by('timestamp')
            
            # Event type mapping for icons and colors
            event_map = {
                'call_initiated': {
                    'title': 'شروع تماس',
                    'icon': 'fas fa-phone',
                    'color': '#3B82F6'
                },
                'customer_answer': {
                    'title': 'پاسخ مشتری',
                    'icon': 'fas fa-phone-volume',
                    'color': '#10B981'
                },
                'customer_hung_up_pre_ivr': {
                    'title': 'قطع قبل از IVR',
                    'icon': 'fas fa-phone-slash',
                    'color': '#F59E0B'
                },
                'customer_dtmf': {
                    'title': 'فشردن کلید',
                    'icon': 'fas fa-keyboard',
                    'color': '#8B5CF6'
                },
                'customer_entered_queue': {
                    'title': 'ورود به صف',
                    'icon': 'fas fa-clock',
                    'color': '#06B6D4'
                },
                'customer_hung_up_in_queue': {
                    'title': 'قطع در صف',
                    'icon': 'fas fa-phone-slash',
                    'color': '#F59E0B'
                },
                'agent_answer': {
                    'title': 'پاسخ کارشناس',
                    'icon': 'fas fa-user-check',
                    'color': '#10B981'
                },
                'call_end': {
                    'title': 'پایان تماس',
                    'icon': 'fas fa-phone-slash',
                    'color': '#EF4444'
                },
                'customer_busy': {
                    'title': 'مشغول',
                    'icon': 'fas fa-phone-busy',
                    'color': '#F59E0B'
                },
                'customer_no_answer': {
                    'title': 'بی‌پاسخ',
                    'icon': 'fas fa-phone-times',
                    'color': '#EF4444'
                },
                'call_rejected': {
                    'title': 'تماس رد شده',
                    'icon': 'fas fa-ban',
                    'color': '#EF4444'
                },
                'call_failed': {
                    'title': 'خطا در تماس',
                    'icon': 'fas fa-exclamation-triangle',
                    'color': '#EF4444'
                }
            }
            
            # Process each log entry to create timeline events
            for log in logs:
                call_logs.append({
                    'timestamp': log.timestamp.isoformat(),
                    'event_type': log.event_type,
                    'message': log.message,
                    'details': log.details
                })
                
                # Create timeline event from webhook log
                event_info = event_map.get(log.event_type, {
                    'title': log.event_type.replace('_', ' ').title(),
                    'icon': 'fas fa-info-circle',
                    'color': '#6B7280'
                })
                
                # Extract additional details from webhook data
                description = log.message
                additional_info = []
                
                if log.details and isinstance(log.details, dict):
                    call_data = log.details.get('call_data', {})
                    
                    # Add DTMF digit info
                    if log.event_type == 'customer_dtmf' and 'digit_pressed' in call_data:
                        additional_info.append(f"کلید فشرده شده: {call_data['digit_pressed']}")
                    
                    # Add queue extension info
                    if log.event_type == 'customer_entered_queue' and 'queue_extension' in call_data:
                        additional_info.append(f"صف: {call_data['queue_extension']}")
                    
                    # Add agent info
                    if log.event_type == 'agent_answer' and 'agent_number' in call_data:
                        additional_info.append(f"کارشناس: {call_data['agent_number']}")
                    
                    # Add duration info
                    if log.event_type in ['call_end', 'customer_hung_up_in_queue', 'customer_hung_up_pre_ivr'] and 'duration' in call_data:
                        duration = call_data['duration']
                        if duration:
                            additional_info.append(f"مدت: {duration} ثانیه")
                
                if additional_info:
                    description += f" ({', '.join(additional_info)})"
                
                timeline_events.append({
                    'timestamp': log.timestamp.isoformat(),
                    'event': log.event_type,
                    'title': event_info['title'],
                    'description': description,
                    'icon': event_info['icon'],
                    'color': event_info['color'],
                    'raw_data': log.details
                })
                
        except AutomaticCall.DoesNotExist:
            pass
        
        # Add initial queue creation event (not from webhook)
        timeline_events.insert(0, {
            'timestamp': queue_item.created_at.isoformat(),
            'event': 'queue_added',
            'title': 'اضافه به صف',
            'description': f'شماره {phone_number} به صف تماس اضافه شد',
            'icon': 'fas fa-plus-circle',
            'color': '#10B981'
        })
        
        # Sort timeline events by timestamp
        timeline_events.sort(key=lambda x: x['timestamp'])
        
        # Calculate call statistics from timeline events
        call_duration_from_logs = None
        call_started_from_logs = None
        call_ended_from_logs = None
        
        for event in timeline_events:
            if event['event'] == 'call_initiated':
                call_started_from_logs = event['timestamp']
            elif event['event'] in ['call_end', 'customer_hung_up_pre_ivr', 'customer_hung_up_in_queue']:
                call_ended_from_logs = event['timestamp']
                # Try to extract duration from the event description
                if 'raw_data' in event and event['raw_data']:
                    call_data = event['raw_data'].get('call_data', {})
                    if 'duration' in call_data:
                        call_duration_from_logs = call_data['duration']
        
        item_details = {
            'phone_number': queue_item.phone_number,
            'customer_name': queue_item.customer.name if queue_item.customer else None,
            'customer_id': queue_item.customer.id if queue_item.customer else None,
            'source': queue_item.source,
            'source_display': queue_item.get_source_display(),
            'status': queue_item.status,
            'status_display': queue_item.get_status_display(),
            'call_duration': call_duration_from_logs or queue_item.call_duration,
            'assigned_agent': {
                'id': queue_item.assigned_agent.id,
                'name': queue_item.assigned_agent.get_full_name() or queue_item.assigned_agent.username
            } if queue_item.assigned_agent else None,
            'created_at': queue_item.created_at.isoformat(),
            'call_started_at': call_started_from_logs or (queue_item.call_started_at.isoformat() if queue_item.call_started_at else None),
            'call_ended_at': call_ended_from_logs or (queue_item.call_ended_at.isoformat() if queue_item.call_ended_at else None),
            'timeline_events': timeline_events,
            'call_logs': call_logs,
            'total_events': len(timeline_events)
        }
        
        return JsonResponse({
            'success': True,
            'details': item_details
        })
        
    except CallQueue.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'آیتم صف پیدا نشد'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def extract_customer_phone_from_webhook_data(call_data):
    """
    Helper function to extract customer phone number from webhook call_data
    """
    if not call_data:
        return None
    
    # Try different possible keys for customer phone number
    phone_keys = ['customer_number', 'customer_phone', 'phone_number', 'callerid', 'from_number']
    
    for key in phone_keys:
        if key in call_data and call_data[key]:
            return call_data[key]
    
    return None


def get_call_logs_for_phone(call, phone_number):
    """
    Helper function to get all call logs related to a specific phone number
    """
    if not phone_number:
        return []
    
    # Search in both message and details JSON field
    logs = CallLog.objects.filter(call=call).filter(
        Q(message__icontains=phone_number) | 
        Q(details__call_data__customer_number=phone_number) |
        Q(details__call_data__customer_phone=phone_number) |
        Q(details__call_data__phone_number=phone_number)
    ).order_by('timestamp')
    
    return logs
