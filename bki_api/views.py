import os
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from dotenv import load_dotenv
from .models import BKILog
from django.views.decorators.csrf import csrf_exempt
from core.decorators.decorators import role_required
from .bki_api_utils import get_purchase_info, bulk_update_purchase_info, send_soap_request, process_purchase_data, get_all_bazaargah_purchases
from core.PurchaseModel import Purchase

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
            purchases_data, log_entry, error = send_soap_request(test_kharid_id)
            
            # اضافه کردن نتیجه تست به context
            context['test_connection'] = True
            context['success'] = purchases_data is not None
            context['error_message'] = error
            context['purchases_data'] = purchases_data
            
            if purchases_data:
                messages.success(request, 'اتصال با سرویس BKI با موفقیت برقرار شد.')
            else:
                messages.error(request, f'خطا در اتصال به سرویس BKI: {error}')
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
    
    # فراخوانی تابع send_soap_request برای تست اتصال به API
    from .bki_api_utils import send_soap_request
    purchases_data, log_entry, error = send_soap_request(kharid_id)
    
    context = {
        'kharid_id': kharid_id,
        'success': purchases_data is not None,
        'error_message': error,
        'purchases_data': purchases_data,
        'log_entry': log_entry
    }
    
    return render(request, 'bki_api/test_result.html', context)

@role_required('admin')
@csrf_exempt
def update_purchase_info(request):
    """تابع برای دریافت اطلاعات خرید از سرویس BKI و به‌روزرسانی دیتابیس محلی"""
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
    
    # فراخوانی تابع کمکی برای دریافت و به‌روزرسانی اطلاعات خرید
    purchase, created, error = get_purchase_info(kharid_id)
    
    if error:
        return JsonResponse({'success': False, 'error': error}, status=400)
        
    if purchase:
        if created:
            # ارائه اطلاعات خرید جدید
            return JsonResponse({
                'success': True,
                'message': f'خرید جدید با شماره {purchase.purchase_number} با موفقیت ایجاد شد',
                'is_new': True,
                'purchase_id': purchase.id,
            })
        else:
            # ارائه اطلاعات خرید به‌روزرسانی شده
            return JsonResponse({
                'success': True,
                'message': f'اطلاعات خرید {purchase.purchase_number} با موفقیت به‌روزرسانی شد',
                'is_new': False,
                'purchase_id': purchase.id,
            })
    else:
        return JsonResponse({'success': False, 'error': 'خطای نامشخص در دریافت اطلاعات خرید'}, status=400)

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
        
        # پردازش شناسه‌های خرید
        results = bulk_update_purchase_info(purchase_ids)
        context['results'] = results
        
        # شمارش موفقیت‌ها و شکست‌ها
        successes = sum(1 for r in results if r.get('success', False))
        failures = len(results) - successes
        created = sum(1 for r in results if r.get('is_new', False) and r.get('success', False))
        updated = successes - created
        
        # نمایش پیام‌های خلاصه
        if successes > 0:
            messages.success(
                request, 
                f'عملیات با موفقیت انجام شد. {successes} خرید با موفقیت به‌روزرسانی شد. '
                f'({created} خرید جدید ایجاد شد، {updated} خرید موجود به‌روزرسانی شد)'
            )
        
        if failures > 0:
            messages.warning(
                request, 
                f'{failures} خرید با خطا مواجه شد. جزئیات را در جدول نتایج ببینید.'
            )
    
    return render(request, 'bki_api/bulk_update.html', context)

@role_required('admin')
def update_all_purchases(request):
    """تابع برای به‌روزرسانی تمام خریدهای موجود در دیتابیس از API بازارگاه"""
    # بررسی اگر درخواست POST نیست، نمایش فرم تایید
    if request.method != 'POST':
        return render(request, 'bki_api/update_all_confirm.html')
    
    # دریافت تمام خریدهایی که شماره خرید بازارگاه دارند
    purchases = Purchase.objects.filter(purchase_number__isnull=False).exclude(purchase_number='')
    
    # اگر خریدی یافت نشد
    if not purchases.exists():
        messages.warning(request, 'هیچ خریدی با شماره خرید بازارگاه در سیستم یافت نشد.')
        return redirect('bki_api:credentials')
    
    # بررسی اعتبارنامه‌های API
    username = settings.BKI_USERNAME
    password = settings.BKI_PASSWORD
    
    if not username or not password:
        messages.error(request, 'اطلاعات کاربری BKI تنظیم نشده است.')
        return redirect('bki_api:credentials')
    
    # جمع‌آوری تمام شماره‌های خرید
    purchase_numbers = list(purchases.values_list('purchase_number', flat=True))
    
    # به‌روزرسانی همه خریدها با تابع به‌روزرسانی دسته‌ای
    results = bulk_update_purchase_info(purchase_numbers)
    
    # تحلیل نتایج
    total = len(results)
    successes = sum(1 for r in results if r.get('success', False))
    failures = total - successes
    updated = sum(1 for r in results if r.get('success', False) and not r.get('is_new', False))
    created = successes - updated
    
    # نمایش پیام‌های مناسب
    if successes > 0:
        messages.success(
            request,
            f'عملیات با موفقیت انجام شد. از {total} خرید، {successes} مورد با موفقیت به‌روزرسانی شد. '
            f'({updated} خرید موجود به‌روزرسانی شد، {created} خرید جدید ایجاد شد)'
        )
    
    if failures > 0:
        messages.warning(
            request,
            f'{failures} خرید با خطا مواجه شد.'
        )
    
    # ارسال به صفحه نتایج
    context = {
        'results': results,
        'total': total,
        'successes': successes,
        'failures': failures,
        'updated': updated,
        'created': created
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
    
    # چاپ اطلاعات برای دیباگ (بدون نمایش رمز عبور کامل)
    print(f"استفاده از نام کاربری: {username}")
    print(f"رمز عبور وارد شده: {'*' * (len(password) if password else 0)}")
    
    # تست اتصال به API بازارگاه
    from .bki_api_utils import test_api_connection
    is_connected, connection_message = test_api_connection()
    if not is_connected:
        messages.error(request, f'خطا در اتصال به API بازارگاه: {connection_message}')
        return redirect('bki_api:credentials')
    else:
        print(f"تست اتصال به API بازارگاه: {connection_message}")
    
    # استفاده از تابع get_all_bazaargah_purchases از ماژول bki_api_utils
    try:
        # فراخوانی تابع برای دریافت و پردازش تمام خریدها
        print("شروع فراخوانی تابع get_all_bazaargah_purchases")
        total_count, success_count, created_count, updated_count, failed_count, errors = get_all_bazaargah_purchases()
        print(f"نتیجه فراخوانی: کل={total_count}, موفق={success_count}, جدید={created_count}, بروزرسانی={updated_count}, خطا={failed_count}")
        
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
        import traceback
        error_details = traceback.format_exc()
        error_message = f"خطا در اجرای تابع دریافت خریدها: {str(e)}"
        print(error_message)
        print(error_details)
        messages.error(request, error_message)
        
        # ثبت خطا در لاگ
        from .models import BKILog
        log_entry = BKILog(
            request_type='getAllKharidInfo',
            is_successful=False,
            error_message=f"خطا در اجرای تابع: {str(e)}\n{error_details}"
        )
        log_entry.save()
        
        return redirect('bki_api:credentials')

