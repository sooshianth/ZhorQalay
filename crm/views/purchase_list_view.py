from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase
from django.db.models import Q

@login_required
def purchase_list(request):
    # دریافت پارامتر جستجوی سریع
    global_search = request.GET.get('global_search', '')
    
    # فیلتر پایه: خریدهای آرشیو نشده و آرشیو شده
    active_purchases = Purchase.objects.exclude(state='ARCHIVED').order_by('-created_at')
    archived_purchases = Purchase.objects.filter(state='ARCHIVED').order_by('-created_at')

    # کارشناسان فروش فقط خریدهای مشتریان خود را می‌بینند
    if hasattr(request.user, 'sales_agent'):
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
        # پارامترهای جستجو برای حفظ وضعیت در فرم
        'search_params': {
            'global_search': global_search,
        }
    }
    
    return render(request, 'purchase_list.html', context)
