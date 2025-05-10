import os
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from dotenv import load_dotenv
from .models import BKILog
from django.views.decorators.csrf import csrf_exempt
from core.decorators.decorators import role_required
from .bki_api_utils import get_purchase_info, bulk_update_purchase_info, send_soap_request, get_all_bazaargah_purchases, process_purchase_data_new
from .bki_kharid_list_by_date import send_kharid_list_by_date_request, get_all_purchases_by_date_range
from core.PurchaseModel import Purchase
from jdatetime import datetime as jdatetime
from django.db import transaction
from django.utils import timezone
import datetime

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
    
    # استفاده از API جدید برای دریافت اطلاعات خرید
    # تنظیم تاریخ امروز برای جستجوی خرید
    from_date = "1403/11/05"  # تاریخ پیش‌فرض
    to_date = "1403/11/05"  # تاریخ پیش‌فرض
    
    # دریافت لیست خریدها
    purchases_data, log_entry, error = send_kharid_list_by_date_request(from_date, to_date)
    
    if error:
        return JsonResponse({'success': False, 'error': error}, status=400)
    
    # جستجوی خرید مورد نظر در لیست
    found_purchase_data = None
    for purchase_data in purchases_data:
        if str(purchase_data.get('idkharid', '')) == str(kharid_id):
            found_purchase_data = purchase_data
            break
    
    if not found_purchase_data:
        return JsonResponse({'success': False, 'error': f'خرید با شناسه {kharid_id} در بازه زمانی مشخص شده یافت نشد'}, status=400)
    
    # پردازش داده خرید یافت شده
    purchase, created, error = process_purchase_data_new(found_purchase_data)
    
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
        
        # استفاده از API جدید برای به‌روزرسانی دسته‌ای
        from_date = "1403/11/05"  # تاریخ پیش‌فرض
        to_date = "1403/11/05"  # تاریخ پیش‌فرض
        
        # دریافت لیست خریدها
        purchases_data, log_entry, error = send_kharid_list_by_date_request(from_date, to_date)
        
        if error:
            messages.error(request, f'خطا در دریافت اطلاعات خرید: {error}')
            return render(request, 'bki_api/bulk_update.html', context)
        
        # تبدیل رشته شناسه‌ها به لیست
        import re
        purchase_ids_list = re.split(r'[,\s]+', purchase_ids)
        purchase_ids_list = [kid.strip() for kid in purchase_ids_list if kid.strip()]
        
        # پردازش هر خرید
        results = []
        for kharid_id in purchase_ids_list:
            # جستجوی خرید مورد نظر در لیست
            found_purchase_data = None
            for purchase_data in purchases_data:
                if str(purchase_data.get('idkharid', '')) == str(kharid_id):
                    found_purchase_data = purchase_data
                    break
            
            if not found_purchase_data:
                results.append({
                    'kharid_id': kharid_id,
                    'success': False,
                    'error': f'خرید با شناسه {kharid_id} در بازه زمانی مشخص شده یافت نشد'
                })
                continue
            
            # پردازش داده خرید یافت شده
            try:
                purchase, created, error = process_purchase_data_new(found_purchase_data)
                
                if error:
                    results.append({
                        'kharid_id': kharid_id,
                        'success': False,
                        'error': error
                    })
                else:
                    if purchase:
                        result = {
                            'kharid_id': kharid_id,
                            'success': True,
                            'created': created,
                            'is_new': created,  # قالب انتظار is_new به جای created دارد
                            'purchase': purchase
                        }
                        
                        if created:
                            # برای خریدهای جدید، ارائه اطلاعات اشیاء ایجاد شده
                            result['message'] = f'خرید جدید با شماره {purchase.purchase_number} با موفقیت ایجاد شد'
                            result['created_objects'] = {
                                'customer': {
                                    'status': 'found' if hasattr(purchase, '_customer_existed') and purchase._customer_existed else 'created',
                                    'id': purchase.customer.id
                                },
                                'cargo': {
                                    'status': 'found' if hasattr(purchase, '_cargo_existed') and purchase._cargo_existed else 'created' if purchase.cargo else 'not_created',
                                    'id': purchase.cargo.id if purchase.cargo else None,
                                    'reason': 'cottage_number_missing' if not purchase.cargo else None
                                },
                                'purchase': {
                                    'status': 'created',
                                    'id': purchase.id
                                }
                            }
                        else:
                            # برای خریدهای موجود، ارائه اطلاعات به‌روزرسانی
                            result['message'] = f'اطلاعات خرید {purchase.purchase_number} با موفقیت به‌روزرسانی شد'
                            # این فیلدها توسط update_purchase_info تنظیم می‌شوند اما ما نیاز داریم آنها را ارائه دهیم
                            result['purchase_updates'] = []
                            result['customer_updates'] = {}
                        
                        results.append(result)
            except Exception as e:
                results.append({
                    'kharid_id': kharid_id,
                    'success': False,
                    'error': str(e)
                })
        
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
    
    # استفاده از API جدید برای به‌روزرسانی همه خریدها
    # استفاده از تاریخ امروز به جای تاریخ ثابت
    today_jalali = jdatetime.now().strftime("%Y/%m/%d")
    from_date = "1403/11/05"  # تاریخ شروع ثابت
    to_date = today_jalali     # تاریخ امروز
    
    print(f"دریافت خریدها از تاریخ {from_date} تا {to_date}")
    
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
    
    # استفاده از API جدید برای دریافت تمام خریدها
    try:
        # استفاده از تاریخ امروز به جای تاریخ ثابت
        today_jalali = jdatetime.now().strftime("%Y/%m/%d")
        from_date = "1403/11/05"  # تاریخ شروع ثابت
        to_date = today_jalali     # تاریخ امروز
        
        print(f"دریافت خریدها از تاریخ {from_date} تا {to_date}")
        
        # فراخوانی تابع برای دریافت و پردازش تمام خریدها
        print("شروع فراخوانی تابع get_all_purchases_by_date_range")
        total_count, success_count, created_count, updated_count, failed_count, errors = get_all_purchases_by_date_range(from_date, to_date)
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

@role_required('sales_agent', 'admin')
@csrf_exempt
def merge_purchases_view(request):
    """
    ادغام خرید ایجاد شده توسط کارشناس فروش با خرید ایجاد شده توسط API بازارگاه
    
    این تابع دو خرید را ادغام می‌کند:
    1. خریدی که کارشناس فروش ایجاد کرده و پیامکش را ارسال کرده
    2. خریدی که از طریق API بازارگاه شناسایی و ایجاد شده
    
    مقادیر invoice_id و customer از خرید کارشناس فروش حفظ می‌شوند
    و سایر اطلاعات از خرید API بازارگاه گرفته می‌شود.
    """
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'error': 'درخواست باید با متد POST ارسال شود'
        }, status=405)
    
    # دریافت شناسه‌های خرید
    try:
        agent_purchase_id = request.POST.get('agent_purchase_id')
        api_purchase_id = request.POST.get('api_purchase_id')
        
        if not agent_purchase_id or not api_purchase_id:
            return JsonResponse({
                'success': False,
                'error': 'هر دو شناسه خرید الزامی هستند'
            }, status=400)
            
        # تبدیل به عدد
        agent_purchase_id = int(agent_purchase_id)
        api_purchase_id = int(api_purchase_id)
    except (ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'error': 'فرمت شناسه‌های خرید نامعتبر است'
        }, status=400)
    
    # دریافت خریدها
    from core.PurchaseModel import Purchase, PurchaseHistory, PuchaseSalesAgent
    
    try:
        agent_purchase = Purchase.objects.get(id=agent_purchase_id)
        api_purchase = Purchase.objects.get(id=api_purchase_id)
    except Purchase.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'یک یا هر دو خرید مورد نظر یافت نشد'
        }, status=404)
    
    # بررسی دسترسی کارشناس فروش به خرید خودش
    if not request.user.is_superuser:
        sales_agent = None
        try:
            from core.SalesAgentModel import SalesAgent
            sales_agent = SalesAgent.objects.get(user=request.user)
        except SalesAgent.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'کاربر جاری کارشناس فروش نیست'
            }, status=403)
            
        # بررسی دسترسی کارشناس فروش به خرید
        # if not agent_purchase.sales_agent.filter(id=sales_agent.id).exists():
        #     return JsonResponse({
        #         'success': False,
        #         'error': 'شما اجازه دسترسی به این خرید را ندارید'
        #     }, status=403)
    
    # بررسی این که خرید API از نوع بازارگاه باشد
    if api_purchase.type != 'bazaargah':
        return JsonResponse({
            'success': False,
            'error': 'خرید API باید از نوع بازارگاه باشد'
        }, status=400)
    
    # بررسی وجود شماره خرید بازارگاه در خرید API
    if not api_purchase.purchase_number:
        return JsonResponse({
            'success': False,
            'error': 'خرید API باید دارای شماره خرید بازارگاه باشد'
        }, status=400)
    
    # بررسی زمان ایجاد خرید API (محدودیت 24 ساعت)
    time_threshold = timezone.now() - datetime.timedelta(hours=24)
    if api_purchase.created_at < time_threshold:
        return JsonResponse({
            'success': False,
            'error': 'خرید‌های بازارگاه با عمر بیشتر از 24 ساعت قابل ادغام نیستند'
        }, status=400)
    
    # ایجاد تراکنش برای ادغام خریدها
    with transaction.atomic():
        # ذخیره مقادیر مهم از خرید کارشناس فروش
        invoice_id = agent_purchase.invoice_id
        customer = agent_purchase.customer
        sales_agents = list(agent_purchase.sales_agent.all())
        
        # لاگ تغییرات
        PurchaseHistory.objects.create(
            purchase=agent_purchase,
            user=request.user,
            changes=f"ادغام با خرید API بازارگاه با شناسه {api_purchase.id} و شماره خرید {api_purchase.purchase_number}"
        )
        
        # مقادیری که از خرید API گرفته می‌شوند
        # به‌روزرسانی فیلدهای خرید کارشناس فروش با مقادیر خرید API
        fields_to_update = [
            'purchase_number', 'tracking_number', 'shenase_takhsis',
            'code_melli_tahvil', 'bazaargah_phone_number', 'buyer_name',
            'tahvil_phone_number', 'barnameh', 'order_weight',
            'delivered_weight', 'cargo', 'amount_paid', 'payment_method',
            'address', 'state'
        ]
        
        # کپی مقادیر از خرید API به خرید کارشناس فروش
        for field in fields_to_update:
            setattr(agent_purchase, field, getattr(api_purchase, field))
        
        # حفظ invoice_id و customer از خرید کارشناس فروش
        agent_purchase.invoice_id = invoice_id
        agent_purchase.customer = customer
        
        # ذخیره تغییرات
        agent_purchase.save()
        
        # بازگرداندن کارشناس فروش‌های اصلی
        agent_purchase.sales_agent.clear()
        for agent in sales_agents:
            PuchaseSalesAgent.objects.create(
                purchase=agent_purchase,
                sales_agent=agent
            )
            
        # انتقال شناسه‌های تخصیص از خرید API به خرید ادغام شده
        from core.PurchaseModel import ShenaseTakhsis
        api_allocation_ids = ShenaseTakhsis.objects.filter(purchase=api_purchase)
        
        # حذف شناسه‌های تخصیص فعلی خرید کارشناس فروش
        ShenaseTakhsis.objects.filter(purchase=agent_purchase).delete()
        
        # افزودن شناسه‌های تخصیص از خرید API
        for allocation in api_allocation_ids:
            ShenaseTakhsis.objects.create(
                purchase=agent_purchase,
                code=allocation.code,
                weight=allocation.weight
            )
        
        # رسیدهای خرید
        from core.PurchaseModel import PurchaseReceipts
        api_receipts = PurchaseReceipts.objects.filter(purchase=api_purchase)
        
        # انتقال رسیدها به خرید ادغام شده
        for receipt in api_receipts:
            # ایجاد یک کپی از رسید در خرید ادغام شده
            new_receipt = PurchaseReceipts(
                purchase=agent_purchase,
                user=receipt.user,
                reciept_type=receipt.reciept_type,
                created_at=receipt.created_at
            )
            # کپی فایل اگر موجود است
            if receipt.reciept_file:
                new_receipt.reciept_file = receipt.reciept_file
            
            new_receipt.save()
        
        # حذف خرید API
        api_purchase.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'خرید‌ها با موفقیت ادغام شدند',
            'purchase_id': agent_purchase.id,
            'invoice_id': agent_purchase.invoice_id
        })

