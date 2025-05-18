import os
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from dotenv import load_dotenv
from .models import BKILog
from django.views.decorators.csrf import csrf_exempt
from core.decorators.decorators import role_required
from .bki_api_utils.api_client import test_api_connection, get_all_bazaargah_purchases
from .bki_api_utils.api_client import analyze_api_response
from .bki_kharid_list_by_date import send_kharid_list_by_date_request, get_all_purchases_by_date_range
from core.PurchaseModel import Purchase
from jdatetime import datetime as jdatetime
from django.db import transaction
from django.utils import timezone
import datetime
import json
import traceback  # For detailed error logging

def update_env_file(key, value):
    """به‌روزرسانی یک کلید مشخص در فایل .env"""
    env_path = os.path.join(settings.BASE_DIR, '.env')
    
    # خواندن فایل .env موجود
    with open(env_path, 'r') as file:
        lines = file.readlines()
    
    # به‌روزرسانی کلید مشخص شده
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break
    
    # اگر کلید وجود ندارد، آن را اضافه کنید
    if not updated:
        lines.append(f"{key}={value}\n")
    
    # نوشتن محتوای به‌روزشده به فایل .env
    with open(env_path, 'w') as file:
        file.writelines(lines)
    
    # بارگذاری مجدد متغیرهای محیطی
    load_dotenv()

@role_required('admin')
def credentials_view(request):
    """نمایش برای مدیریت اعتبارنامه‌های API بازارگاه"""
    # دریافت اطلاعات اعتباری فعلی از متغیرهای محیطی
    current_username = os.environ.get('BKI_USERNAME', '')
    current_password = os.environ.get('BKI_PASSWORD', '')
    
    context = {
        'current_username': current_username,
        'current_password': current_password,
    }
    
    if request.method == 'POST':
        # بررسی نوع عملیات درخواستی
        if 'test_connection' in request.POST:
            # تست اتصال به سرویس BKI
            test_kharid_id = request.POST.get('test_kharid_id', '')
            if not test_kharid_id:
                messages.error(request, 'لطفاً یک شناسه خرید برای تست وارد کنید.')
                return redirect('bki_api:credentials')
            
            # تلاش برای ارتباط با API بازارگاه
            is_successful, error_message = test_api_connection()
            
            # اضافه کردن نتیجه تست به context
            context['test_connection'] = True
            context['success'] = is_successful
            context['error_message'] = error_message
            
            if is_successful:
                messages.success(request, 'اتصال با سرویس BKI با موفقیت برقرار شد.')
            else:
                messages.error(request, f'خطا در اتصال به سرویس BKI: {error_message}')
        else:
            # به‌روزرسانی اطلاعات اعتباری
            username = request.POST.get('username')
            password = request.POST.get('password')
            
            # به‌روزرسانی فایل .env با اطلاعات اعتباری جدید
            if username:
                update_env_file('BKI_USERNAME', username)
            if password:
                update_env_file('BKI_PASSWORD', password)
            
            messages.success(request, 'تنظیمات BKI با موفقیت به‌روزرسانی شد.')
            return redirect('bki_api:credentials')
    
    return render(request, 'bki_api/credentials_form.html', context)

@role_required('admin')
def test_kharid_info(request):
    """نمایش برای تست API getKharidInfo"""
    if request.method != 'POST':
        return redirect('bki_api:credentials')
    
    kharid_id = request.POST.get('kharid_id')
    if not kharid_id:
        messages.error(request, 'لطفاً شناسه خرید را وارد کنید.')
        return redirect('bki_api:credentials')
    
    # دریافت اطلاعات اعتباری از متغیرهای محیطی
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است.')
        return redirect('bki_api:credentials')
    
    # تست API
    is_successful, error_message = test_api_connection()
    
    context = {
        'kharid_id': kharid_id,
        'success': is_successful,
        'error_message': error_message
    }
    
    return render(request, 'bki_api/test_result.html', context)

@role_required('admin')
@csrf_exempt
def update_purchase_info(request):
    """تابع برای تست دریافت اطلاعات خرید از API بازارگاه (فقط برای تست)"""
    # دریافت اطلاعات اعتباری
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        return JsonResponse({'error': 'اطلاعات کاربری BKI تنظیم نشده است.'}, status=400)
    
    # دریافت شناسه خرید
    kharid_id = None
    if request.method == 'POST':
        try:
            # تلاش برای دریافت شناسه خرید از بدنه JSON
            data = request.json()
            kharid_id = data.get('kharid_id')
        except:
            # اگر JSON نبود، ممکن است فرم POST باشد
            kharid_id = request.POST.get('kharid_id')
    else:
        # پشتیبانی از درخواست GET
        kharid_id = request.GET.get('kharid_id')
    
    if not kharid_id:
        return JsonResponse({'error': 'شناسه خرید الزامی است.'}, status=400)
    
    # تست اتصال به API
    is_successful, message = test_api_connection()
    if not is_successful:
        return JsonResponse({'success': False, 'error': message}, status=400)
    
    # این تابع صرفاً برای تست است و عملیات واقعی انجام نمی‌دهد
    return JsonResponse({
        'success': True,
        'message': 'این یک تابع تست است. برای عملیات واقعی، از API دریافت خریدها بر اساس تاریخ استفاده کنید.',
        'kharid_id': kharid_id
    })

@role_required('admin')
def bulk_update_purchases(request):
    """نمایش برای به‌روزرسانی دسته‌ای خریدها از API بازارگاه"""
    context = {
        'purchase_ids': '',
        'results': None
    }
    
    if request.method == 'POST':
        purchase_ids = request.POST.get('purchase_ids', '').strip()
        if not purchase_ids:
            messages.error(request, 'لطفاً حداقل یک شماره خرید وارد کنید.')
            return render(request, 'bki_api/bulk_update.html', context)
        
        # ذخیره شناسه‌های خرید در context برای نمایش مجدد پس از پردازش
        context['purchase_ids'] = purchase_ids
        
        # استفاده از API جدید برای به‌روزرسانی دسته‌ای
        today_jalali = jdatetime.now().strftime("%Y/%m/%d")
        from_date = (jdatetime.now() - datetime.timedelta(days=30)).strftime("%Y/%m/%d")
        to_date = today_jalali
        
        # دریافت لیست خریدها
        purchases_data, log_entry, error = send_kharid_list_by_date_request(from_date, to_date)
        
        if error:
            messages.error(request, f'خطا در دریافت اطلاعات خرید: {error}')
            return render(request, 'bki_api/bulk_update.html', context)
        
        # تبدیل رشته شناسه‌ها به لیست
        import re
        purchase_ids_list = re.split(r'[,\s]+', purchase_ids)
        purchase_ids_list = [kid.strip() for kid in purchase_ids_list if kid.strip()]
        
        # این بخش فقط برای نمایش نتایج تست است
        results = []
        for kharid_id in purchase_ids_list:
            results.append({
                'kharid_id': kharid_id,
                'success': True,
                'message': 'این یک تابع تست است. برای عملیات واقعی، از API دریافت خریدها بر اساس تاریخ استفاده کنید.'
            })
        
        context['results'] = results
        messages.info(request, 'این صفحه فقط برای تست است. برای عملکرد واقعی از بخش "دریافت همه خریدها" استفاده کنید.')
    
    return render(request, 'bki_api/bulk_update.html', context)

@role_required('admin')
def update_all_purchases(request):
    """تابع برای به‌روزرسانی تمام خریدهای موجود در دیتابیس از API بازارگاه"""
    # بررسی اگر درخواست POST نیست، نمایش فرم تایید
    if request.method != 'POST':
        return render(request, 'bki_api/update_all_confirm.html')
    
    # بررسی اعتبارنامه‌های API
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است.')
        return redirect('bki_api:credentials')
    
    # استفاده از API جدید برای به‌روزرسانی همه خریدها
    # استفاده از تاریخ امروز به جای تاریخ ثابت
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    from_date = (jdatetime.now() - datetime.timedelta(days=180)).strftime("%Y/%m/%d")  # 6 ماه گذشته
    to_date = today_jalali     # تاریخ امروز
    
    # دریافت لیست خریدها از API
    total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(from_date, to_date)
    
    # نمایش پیام‌های مناسب
    if success_count > 0:
        messages.success(
            request,
            f'عملیات با موفقیت انجام شد. از {total_count} خرید، {success_count} مورد با موفقیت به‌روزرسانی شد. '
            f'({created_count} خرید جدید ایجاد شد، {updated_count} خرید موجود به‌روزرسانی شد)'
        )
    
    if failed_count > 0:
        messages.warning(
            request,
            f'{failed_count} خرید با خطا مواجه شد.'
        )
    
    # ارسال به صفحه نتایج
    context = {
        'total': total_count,
        'successes': success_count,
        'failures': failed_count,
        'updated': updated_count,
        'created': created_count,
        'errors': errors
    }
    
    return render(request, 'bki_api/update_all_results.html', context)

@role_required('admin')
def get_all_bazaargah_purchases_view(request):
    """تابع برای دریافت و ثبت تمام خریدهای موجود در بازارگاه"""
    # بررسی اگر درخواست POST نیست، نمایش فرم تایید
    if request.method != 'POST':
        return render(request, 'bki_api/get_all_purchases_confirm.html')
    
    # بررسی اعتبارنامه‌های API
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است.')
        return redirect('bki_api:credentials')
    
    # تست اتصال به API بازارگاه
    is_connected, connection_message = test_api_connection()
    if not is_connected:
        messages.error(request, f'خطا در اتصال به API بازارگاه: {connection_message}')
        return redirect('bki_api:credentials')
    
    # استفاده از API برای دریافت تمام خریدها
    try:
        # استفاده از تاریخ امروز به جای تاریخ ثابت
        today_jalali = jdatetime.now().strftime("%Y/%m/%d")
        from_date = (jdatetime.now() - datetime.timedelta(days=180)).strftime("%Y/%m/%d")  # 6 ماه گذشته
        to_date = today_jalali     # تاریخ امروز
        
        # فراخوانی تابع برای دریافت و پردازش تمام خریدها
        total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(from_date, to_date)
        
        # ارسال به صفحه نتایج
        context = {
            'total': total_count,
            'successes': success_count,
            'failures': failed_count,
            'updated': updated_count,
            'created': created_count,
            'errors': errors
        }
        
        # نمایش پیام‌های مناسب
        if success_count > 0:
            messages.success(
                request,
                f'عملیات با موفقیت انجام شد. از {total_count} خرید، {success_count} مورد با موفقیت پردازش شد. '
                f'({created_count} خرید جدید ایجاد شد، {updated_count} خرید موجود به‌روزرسانی شد)'
            )
        else:
            messages.warning(
                request,
                'هیچ خرید جدیدی ثبت نشد و هیچ خریدی به‌روزرسانی نشد.'
            )
        
        if failed_count > 0:
            messages.warning(
                request,
                f'{failed_count} خرید با خطا مواجه شد. جزئیات را در جدول نتایج ببینید.'
            )
        
        return render(request, 'bki_api/get_all_purchases_results.html', context)
        
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"خطا در اجرای تابع دریافت خریدها: {str(e)}"
        messages.error(request, error_message)
        
        # ثبت خطا در لاگ
        log_entry = BKILog(
            request_type='getAllKharidInfo',
            is_successful=False,
            error_message=f"خطا در اجرای تابع: {str(e)}\n{error_details}"
        )
        log_entry.save()
        
        return redirect('bki_api:credentials')

@role_required('sales_agent', 'admin')
@csrf_exempt
def merge_purchases_view(request):
    """
    ادغام خرید ایجاد شده توسط کارشناس فروش با خرید ایجاد شده توسط API بازارگاه
    
    این تابع خرید ایجاد شده به صورت دستی توسط کارشناس فروش را با خرید ایجاد شده توسط API بازارگاه ادغام می‌کند.
    از خرید دستی، فقط شناسه invoice_id، مشتری و کارشناسان فروش منتقل می‌شوند و بقیه اطلاعات از خرید API استفاده می‌شود.
    
    ملاک تشخیص خرید دستی، نداشتن شماره خرید (purchase_number) است.
    ملاک تشخیص خرید API، داشتن شماره خرید (purchase_number) است.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'درخواست باید با متد POST ارسال شود'
        }, status=400)
    
    # دریافت شناسه خریدها از درخواست
    try:
        # بررسی نوع درخواست: JSON یا Form Data
        if request.body and 'application/json' in request.headers.get('Content-Type', ''):
            data = json.loads(request.body)
            agent_purchase_id = data.get('manual_purchase_id') or data.get('agent_purchase_id')
            api_purchase_id = data.get('bazaargah_purchase_id') or data.get('api_purchase_id')
        else:
            # اگر درخواست به صورت Form Data است
            agent_purchase_id = request.POST.get('agent_purchase_id') or request.POST.get('manual_purchase_id')
            api_purchase_id = request.POST.get('api_purchase_id') or request.POST.get('bazaargah_purchase_id')
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'داده‌های JSON نامعتبر'
        }, status=400)
    
    # بررسی وجود شناسه‌های خرید
    if not agent_purchase_id or not api_purchase_id:
        return JsonResponse({
            'success': False,
            'error': 'شناسه خرید دستی و شناسه خرید بازارگاه الزامی هستند'
        }, status=400)
    
    try:
        # یافتن خریدها
        try:
            agent_purchase = Purchase.objects.get(id=agent_purchase_id)
        except Purchase.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'خرید دستی با شناسه {agent_purchase_id} یافت نشد'
            }, status=404)
        
        try:
            api_purchase = Purchase.objects.get(id=api_purchase_id)
        except Purchase.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'خرید بازارگاه با شناسه {api_purchase_id} یافت نشد'
            }, status=404)
        
        # بررسی داشتن/نداشتن شماره خرید
        if agent_purchase.purchase_number:
            return JsonResponse({
                'success': False,
                'error': f'خرید {agent_purchase_id} دارای شماره خرید بازارگاه است و نمی‌تواند به عنوان خرید دستی ادغام شود'
            }, status=400)
        
        if not api_purchase.purchase_number:
            return JsonResponse({
                'success': False,
                'error': f'خرید {api_purchase_id} فاقد شماره خرید بازارگاه است و نمی‌تواند به عنوان خرید API ادغام شود'
            }, status=400)
        
        # بررسی محدودیت زمانی 24 ساعت
        time_threshold = timezone.now() - datetime.timedelta(hours=24)
        if api_purchase.created_at < time_threshold:
            return JsonResponse({
                'success': False,
                'error': 'امکان ادغام خرید‌های بازارگاه با عمر بیشتر از 24 ساعت وجود ندارد'
            }, status=400)
        
        # ادغام خریدها با استفاده از تراکنش برای اطمینان از یکپارچگی داده‌ها
        with transaction.atomic():
            # ذخیره اطلاعات مشتری، invoice_id و کارشناسان فروش از خرید دستی
            customer = agent_purchase.customer
            invoice_id = agent_purchase.invoice_id
            sales_agents = list(agent_purchase.purchase_sales_agents.all())
            
            # تنظیم مشتری و شناسه فاکتور در خرید API
            api_purchase.customer = customer
            
            # برای جلوگیری از مشکل UNIQUE constraint در invoice_id:
            # ابتدا invoice_id خرید API را به یک مقدار موقت تغییر می‌دهیم
            temp_invoice_id = api_purchase.invoice_id
            api_purchase.invoice_id = None
            api_purchase.save()
            
            # در مرحله بعد، حذف خرید دستی
            agent_purchase.delete()
            
            # پس از حذف خرید دستی، invoice_id آن را به خرید API اختصاص می‌دهیم
            api_purchase.invoice_id = invoice_id
            api_purchase.save()
            
            # انتقال روابط کارشناسان فروش
            from core.PurchaseModel import PuchaseSalesAgent
            
            # ابتدا تمام روابط کارشناسان فروش موجود را پاک می‌کنیم
            api_purchase.purchase_sales_agents.all().delete()
            
            # سپس کارشناسان فروش از خرید دستی را اضافه می‌کنیم
            for relation in sales_agents:
                PuchaseSalesAgent.objects.create(
                    purchase=api_purchase,
                    sales_agent=relation.sales_agent
                )
            
            # ثبت تغییرات در تاریخچه خرید
            from core.PurchaseModel import PurchaseHistory
            PurchaseHistory.objects.create(
                purchase=api_purchase,
                user=request.user,
                changes=f"ادغام با خرید دستی شماره {agent_purchase_id} - مشتری: {customer.name if customer else 'نامعلوم'}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'خرید دستی {agent_purchase_id} با خرید بازارگاه {api_purchase_id} با موفقیت ادغام شد',
                'merged_purchase_id': api_purchase_id
            })
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"خطا در ادغام خریدها: {str(e)}\n{error_details}")
        return JsonResponse({
            'success': False,
            'error': f'خطا در ادغام خریدها: {str(e)}'
        }, status=500)

