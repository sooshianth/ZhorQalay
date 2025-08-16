from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from core.decorators.decorators import role_required
from core.decorators.det_user_role import determine_user_role
from bki_barnameh.models.BarnamehModel import Barnameh
from ERP.views.managers_profile_view import get_client_ip
import logging

logger = logging.getLogger("major_non_bazargah_barnameh_list_view")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent')
@login_required
def non_bazargah_barnameh_list(request):
    logger.warning(f"لیست بارنامه‌های خارج از بازارگاه توسط {request.user.username} باز شد با آیپی {get_client_ip(request)}")
    
    # تشخیص نقش کاربر
    user_role = determine_user_role(request.user)
    
    # ایجاد QuerySet پایه - فقط بارنامه‌های خارج از بازارگاه
    base_queryset = Barnameh.objects.filter(
        type='Non_Bazargah'
    ).select_related(
        'non_bazargah_purchase', 'non_bazargah_purchase__customer', 
        'non_bazargah_purchase__unique_sales_agent', 'non_bazargah_purchase__product'
    ).order_by('-barnameh_created_at')
    
    # اگر کاربر کارشناس فروش است، فقط بارنامه‌های مربوطه را ببیند
    if user_role == 'sales_agent':
        if hasattr(request.user, 'sales_agent') and request.user.sales_agent:
            base_queryset = base_queryset.filter(
                non_bazargah_purchase__unique_sales_agent=request.user.sales_agent
            )
        else:
            base_queryset = Barnameh.objects.none()

    # تنظیم pagination ساده
    paginator = Paginator(base_queryset, 20)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    context = {
        'barnamehs': page_obj,
        'user_role': user_role,
        'total_barnamehs': paginator.count,
        'paginator': paginator,
        'page_obj': page_obj,
    }
    
    return render(request, 'major/non_bazargah_barnameh_list.html', context)

