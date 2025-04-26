from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase
from django.db.models import Q

def determine_user_role(user):
    """
    تشخیص نقش کاربر براساس روابط او
    به جای بررسی مستقیم role که وجود ندارد، روابط بررسی می‌شود
    نقش لجستیک بر فروش ارجحیت دارد
    """
    if hasattr(user, 'financial_manager') and user.financial_manager is not None:
        return 'financial_manager'
    elif hasattr(user, 'logistics_manager') and user.logistics_manager is not None:
        return 'logistics_manager'
    elif hasattr(user, 'sales_agent') and user.sales_agent is not None:
        return 'sales_agent'
    elif hasattr(user, 'support_agent') and user.support_agent is not None:
        return 'support_agent'
    elif user.is_superuser:
        # مدیر ارشد دسترسی کامل دارد
        return 'admin'
    return None

@login_required
def purchase_list(request):
    # دریافت پارامتر جستجوی سریع
    global_search = request.GET.get('global_search', '')
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # فیلتر پایه: خریدهای آرشیو نشده و آرشیو شده
    active_purchases = Purchase.objects.exclude(state='ARCHIVED').exclude(is_archived=True).order_by('-created_at')
    archived_purchases = Purchase.objects.filter(Q(state='ARCHIVED') | Q(is_archived=True)).order_by('-created_at')

    # اگر کاربر کارشناس فروش است ولی نقش لجستیک ندارد، فقط خریدهای مشتریان خود را ببیند
    if user_role == 'sales_agent':
        active_purchases = active_purchases.filter(customer__sales_agent=request.user.sales_agent)
        archived_purchases = archived_purchases.filter(customer__sales_agent=request.user.sales_agent)

    # اعمال فیلتر جستجوی سریع
    if global_search:
        active_purchases = active_purchases.filter(
            Q(customer__name__icontains=global_search) |
            Q(customer__sales_agent__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(order_weight__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__product_type__icontains=global_search) |
            Q(cargo__country__icontains=global_search) |
            Q(created_at__contains=global_search)
        )
        archived_purchases = archived_purchases.filter(
            Q(customer__name__icontains=global_search) |
            Q(customer__sales_agent__name__icontains=global_search) |
            Q(purchase_number__icontains=global_search) |
            Q(order_weight__icontains=global_search) |
            Q(invoice_id__icontains=global_search) |
            Q(cargo__cottage__icontains=global_search) |
            Q(cargo__product_type__icontains=global_search) |
            Q(cargo__country__icontains=global_search) |
            Q(created_at__contains=global_search)
        )
    
    # فهرست وضعیت‌ها برای فیلتر
    all_states = dict(Purchase.STATUS_CHOICES)
    
    context = {
        'active_purchases': active_purchases,
        'archived_purchases': archived_purchases,
        'all_states': all_states,
        'user_role': user_role,  # افزودن نقش کاربر به context
        # پارامترهای جستجو برای حفظ وضعیت در فرم
        'search_params': {
            'global_search': global_search,
        }
    }
    
    return render(request, 'purchase_list.html', context)
