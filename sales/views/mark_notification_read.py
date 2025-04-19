from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from core._models import Notification
import json
import logging

logger = logging.getLogger(__name__)

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """نوتیفیکیشن موردنظر را به عنوان خوانده‌شده علامت‌گذاری می‌کند."""
    notif = get_object_or_404(Notification, id= notification_id, user=request.user)
    notif.is_read = True
    notif.save()
    return redirect('sales_agent_profile') 

@login_required
@require_POST
def mark_all_notifications_read(request):
    for notification in Notification.objects.all():
        notification.is_read = True
        notification.save()

    return redirect('sales_agent_profile')
