from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from major.models.NonBazargahPurchase import NonBazargahPurchase
from ERP.views.managers_profile_view import get_client_ip
import logging

logger = logging.getLogger("major_non_bazargah_purchase_list_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def non_bazargah_purchase_list(request):
    logger.warning(f"لیست خریدهای خارج از بازارگاه توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # ایجاد QuerySet پایه
    base_queryset = NonBazargahPurchase.objects.select_related(
        'customer', 'unique_sales_agent', 'product'
    ).order_by('-created_at')
    
    # اگر کاربر کارشناس فروش است، فقط خریدهای مربوطه را ببیند
    if user_role == 'sales_agent':
        if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
            base_queryset = base_queryset.filter(unique_sales_agent=request.user.sales_agent)
        else:
            base_queryset = NonBazargahPurchase.objects.none()

    # تنظیم pagination ساده
    paginator = Paginator(base_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        'purchases': page_obj,
        'user_role': user_role,
        'total_purchases': paginator.count,
        'paginator': paginator,
        'page_obj': page_obj,
    }
    
    return render(request, 'major/non_bazargah_purchase_list.html', context)
