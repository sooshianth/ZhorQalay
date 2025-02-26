from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from core.models import Notification

@login_required
def mark_notification_as_read(request, notif_id):
    """نوتیفیکیشن موردنظر را به عنوان خوانده‌شده علامت‌گذاری می‌کند."""
    notif = get_object_or_404(Notification, id=notif_id, user=request.user)
    notif.is_read = True
    notif.save()
    return redirect('sales_agent_profile')  # بعد از تغییر وضعیت، به پروفایل برمی‌گردد
