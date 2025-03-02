from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core._models import Purchase

@login_required
def purchase_list(request):
    
    active_purchases = Purchase.objects.filter(is_archived=False).order_by('-created_at')
    
    archived_purchases = Purchase.objects.filter(is_archived=True).order_by('-created_at')

    if hasattr(request.user, 'sales_agent'):

        active_purchases = Purchase.objects.filter(is_archived=False, customer__sales_agent=request.user.sales_agent).order_by('-created_at')
        archived_purchases = Purchase.objects.filter(is_archived=True, customer__sales_agent=request.user.sales_agent).order_by('-created_at')

    context = {
        'active_purchases': active_purchases,
        'archived_purchases': archived_purchases,
    }
    
    return render(request, 'purchase_list.html', context)
