from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase
from django.db.models import Q

@login_required
def purchase_list(request):
    # دریافت پارامترهای جستجو از query string
    search_customer = request.GET.get('search_customer', '')
    search_sales_agent = request.GET.get('search_sales_agent', '')
    search_purchase_number = request.GET.get('search_purchase_number', '')
    search_weight = request.GET.get('search_weight', '')
    search_invoice_id = request.GET.get('search_invoice_id', '')
    search_cargo = request.GET.get('search_cargo', '')
    search_date = request.GET.get('search_date', '')
    search_state = request.GET.get('search_state', '')
    
    # فیلتر پایه: خریدهای آرشیو نشده و آرشیو شده
    active_purchases = Purchase.objects.exclude(state='ARCHIVED').order_by('-created_at')
    archived_purchases = Purchase.objects.filter(state='ARCHIVED').order_by('-created_at')

    # کارشناسان فروش فقط خریدهای مشتریان خود را می‌بینند
    if hasattr(request.user, 'sales_agent'):
        active_purchases = active_purchases.filter(customer__sales_agent=request.user.sales_agent)
        archived_purchases = archived_purchases.filter(customer__sales_agent=request.user.sales_agent)

    # اعمال فیلترهای جستجو
    if search_customer:
        active_purchases = active_purchases.filter(customer__name__icontains=search_customer)
        archived_purchases = archived_purchases.filter(customer__name__icontains=search_customer)
    
    if search_sales_agent:
        active_purchases = active_purchases.filter(customer__sales_agent__name__icontains=search_sales_agent)
        archived_purchases = archived_purchases.filter(customer__sales_agent__name__icontains=search_sales_agent)
    
    if search_purchase_number:
        active_purchases = active_purchases.filter(purchase_number__icontains=search_purchase_number)
        archived_purchases = archived_purchases.filter(purchase_number__icontains=search_purchase_number)
    
    if search_weight:
        active_purchases = active_purchases.filter(weight__icontains=search_weight)
        archived_purchases = archived_purchases.filter(weight__icontains=search_weight)
    
    if search_invoice_id:
        active_purchases = active_purchases.filter(invoice_id__icontains=search_invoice_id)
        archived_purchases = archived_purchases.filter(invoice_id__icontains=search_invoice_id)
    
    if search_cargo:
        active_purchases = active_purchases.filter(Q(cargo__cottage__icontains=search_cargo) | 
                                                 Q(cargo__product_type__icontains=search_cargo) |
                                                 Q(cargo__country__icontains=search_cargo))
        archived_purchases = archived_purchases.filter(Q(cargo__cottage__icontains=search_cargo) | 
                                                     Q(cargo__product_type__icontains=search_cargo) |
                                                     Q(cargo__country__icontains=search_cargo))
    
    if search_date:
        active_purchases = active_purchases.filter(created_at__contains=search_date)
        archived_purchases = archived_purchases.filter(created_at__contains=search_date)
    
    if search_state:
        active_purchases = active_purchases.filter(state=search_state)
    
    # فهرست وضعیت‌ها برای فیلتر
    all_states = dict(Purchase.STATUS_CHOICES)
    
    context = {
        'active_purchases': active_purchases,
        'archived_purchases': archived_purchases,
        'all_states': all_states,
        # پارامترهای جستجو برای حفظ وضعیت در فرم
        'search_params': {
            'customer': search_customer,
            'sales_agent': search_sales_agent,
            'purchase_number': search_purchase_number,
            'weight': search_weight,
            'invoice_id': search_invoice_id,
            'cargo': search_cargo,
            'date': search_date,
            'state': search_state,
        }
    }
    
    return render(request, 'purchase_list.html', context)
