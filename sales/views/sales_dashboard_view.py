from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@login_required
def sales_dashboard_view(request):
    if not hasattr(request.user, 'sales_agent'):
        logger.warning(f"Unauthorized access attempt by user {request.user.username}")
        return redirect('sales_agent_login')

    sales_agent = request.user.sales_agent
    today = timezone.now()

    # داده‌های فروش برای 6 ماه گذشته
    monthly_sales = []
    for i in range(6):  # 6 ماه گذشته شامل ماه جاری
        # محاسبه شروع و پایان ماه
        month_date = today - timedelta(days=i * 30)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=31)).replace(day=1) - timedelta(seconds=1)

        # جمع وزن فروش‌های هر ماه
        sales_weight = sum(
            purchase.weight for purchase in sales_agent.get_all_active_sales()
            if month_start <= purchase.created_at <= month_end
        )

        monthly_sales.append({
            'month': month_start.strftime('%Y-%m'),
            'sales': sales_weight
        })

    # پیش‌بینی فروش ماه بعد (میانگین 6 ماه گذشته)
    total_sales = sum(m['sales'] for m in monthly_sales)
    sales_prediction = total_sales / len(monthly_sales) if monthly_sales else 0

    context = {
        'sales_agent': sales_agent,
        'monthly_sales': monthly_sales[::-1],  # معکوس برای نمایش از قدیم به جدید
        'task_stats': {
            'pending': len(sales_agent.get_all_undone_tasks()),
            'completed': len([task for task in sales_agent.get_all_tasks() if task.status])
        },
        'sales_prediction': round(sales_prediction, 2),
        'this_month_sales_weight': sales_agent.get_this_month_sales_weight(),
        'this_month_sales_count': sales_agent.get_this_month_sales_count(),
    }
    logger.info(f"Dashboard loaded for {sales_agent.name}")
    return render(request, 'sales_dashboard.html', context)
