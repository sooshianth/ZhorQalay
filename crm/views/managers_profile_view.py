from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.PurchaseModel import Purchase, determine_user_role

@login_required
def logistics_manager_profile_view(request):
    manager = request.user.logistics_manager
    user_role = determine_user_role(request.user)
    
    # وضعیت‌هایی که مدیر لجستیک می‌تواند بر روی آنها اقدام کند
    states_to_action = [
        'BAZAARGAH_CONFIRMED',      # تایید بازارگاه
        'ALLOCATION_APPROVED',      # تایید تخصیص
        'ADDRESS_SENT',             # تأیید ارسال شدن آدرس به واردکننده
        'ADDRESS_SENT',             # ارسال به باربری
        'SENT_TO_SHIPPING',         # صدور بارنامه
        'BARNAMEH_ISSUED',          # تحویل به مشتری
        'DIFFERENCE_APPROVED',      # تایید مبلغ اختلاف
        'LOGISTICS_APPROVED',       # تایید واحد لجستیک
    ]
    
    pending_purchases = Purchase.objects.filter(state__in=states_to_action, is_canceled=False, is_archived=False).order_by('-updated_at')
    
    return render(request, 'logistics_manager_profile.html', {
        'manager': manager, 
        'user': request.user,
        'pending_purchases': pending_purchases,
        'user_role': user_role
    })

@login_required
def financial_manager_profile_view(request):
    manager = request.user.financial_manager
    user_role = determine_user_role(request.user)
    
    # وضعیت‌هایی که مدیر مالی می‌تواند بر روی آنها اقدام کند
    states_to_action = [
        'VENDOR_SETTLED',           # تسویه با واردکننده
        'DIFFERENCE_APPROVED',      # تایید مبلغ اختلاف
        'DIFFERENCE_APPROVED',      # واریز کسری
        'RECEIPT_SUBMITTED',        # ثبت رسید
        'INVOICE_ISSUED',           # صدور فاکتور
        'FINANCIAL_APPROVED',       # تایید واحد مالی
    ]
    
    pending_purchases = Purchase.objects.filter(state__in=states_to_action, is_canceled=False, is_archived=False).order_by('-updated_at')
    
    return render(request, 'financial_manager_profile.html', {
        'manager': manager, 
        'user': request.user,
        'pending_purchases': pending_purchases,
        'user_role': user_role
    })

@login_required
def support_agent_profile_view(request):
    agent = request.user.support_agent
    return render(request, 'support_agent_profile.html', {'agent': agent, 'user': request.user})


