from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.PurchaseModel import Purchase, determine_user_role
from core.decorators.decorators import role_required
import logging
from core.logging_levels import *
logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

def get_client_ip(request):
    """
    دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
    """
    if not request:
        return "Unknown"
        
    # IP مستقیم (از سرور دیده می‌شود)
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
    # IP از طریق proxy headers
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')

    # انتخاب IP اصلی
    client_ip = direct_ip
    if forwarded_for:
        # اولین IP در لیست X-Forwarded-For
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
        
    # اگر proxy وجود دارد، هر دو IP را نمایش بده
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
        
    return f"{client_ip}-{proxy_info}"

@role_required('logistics_manager')
@login_required
def logistics_manager_profile_view(request):
    audit_logger.info(f"Logistics Manager Profile View accessed ")
    manager = request.user.logistics_manager
    user_role = determine_user_role(request.user)
    
    # وضعیت‌هایی که مدیر لجستیک می‌تواند بر روی آنها اقدام کند
    states_to_action = [
        'SMS_SENT',                 # تایید پرداخت (توسط API)
        'PAYMENT_VERIFIED',         # تایید تخصیص
        'ALLOCATION_APPROVED',      # تایید تخصیص
        'VENDOR_SETTLED',           # ارسال آدرس به واردکننده
        'ADDRESS_SENT',             # ارسال به باربری
        'SENT_TO_SHIPPING',         # صدور بارنامه یا ثبت بارنامه ناقص
        'BARNAMEH_ISSUED',          # تحویل به مشتری یا ثبت بارنامه ناقص
        'BARNAMEH_INCOMPLETE',      # تحویل به مشتری 
        'DELIVERED',                # تایید مبلغ اختلاف (لجستیک)
        'INVOICE_ISSUED',           # تایید واحد لجستیک
        'SALES_APPROVED',           # تایید واحد لجستیک
    ]
    
    pending_purchases = Purchase.objects.filter(state__in=states_to_action, is_canceled=False, is_archived=False).order_by('-updated_at')
    
    return render(request, 'logistics_manager_profile.html', {
        'manager': manager, 
        'user': request.user,
        'pending_purchases': pending_purchases,
        'user_role': user_role
    })

@role_required('financial_manager')
@login_required
def financial_manager_profile_view(request):

    audit_logger.info(f"Financial Manager Profile View accessed ")
    manager = request.user.financial_manager
    user_role = determine_user_role(request.user)
    
    # وضعیت‌هایی که مدیر مالی می‌تواند بر روی آنها اقدام کند
    states_to_action = [
        'SMS_SENT',                 # تایید پرداخت (همه خریدها)
        'PAYMENT_VERIFIED',         # تسویه با واردکننده 
        'ALLOCATION_APPROVED',      # تسویه با واردکننده
        'DELIVERED',                # تایید مبلغ اختلاف
        'DIFFERENCE_APPROVED',      # ثبت واریز اختلاف (کسری)
        'DIFFERENCE_DEPOSITED',     # ثبت رسید
        'RECEIPT_SUBMITTED',        # صدور فاکتور
        'INVOICE_ISSUED',           # تایید واحد مالی
        'SALES_APPROVED',           # تایید واحد مالی
        'LOGISTICS_APPROVED',       # تایید واحد مالی
    ]
    
    pending_purchases = Purchase.objects.filter(state__in=states_to_action, is_canceled=False, is_archived=False).order_by('-updated_at')
    
    return render(request, 'financial_manager_profile.html', {
        'manager': manager, 
        'user': request.user,
        'pending_purchases': pending_purchases,
        'user_role': user_role
    })




