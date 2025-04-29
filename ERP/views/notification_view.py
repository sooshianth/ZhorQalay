from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ERP.models.NotificationService import NotificationService
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from ERP.models.Notification import Notification

@login_required
@require_http_methods(["GET"])
def get_notifications(request):
    """دریافت نوتیفیکیشن‌های کاربر"""
    notifications = NotificationService.get_unread_notifications(request.user)
    return JsonResponse({
        'notifications': [{
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'priority': notif.priority,
            'created_at': notif.created_at.strftime('%Y/%m/%d %H:%M')
        } for notif in notifications]
    })

@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """علامت‌گذاری نوتیفیکیشن به عنوان خوانده شده"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    NotificationService.mark_as_read(notification_id)
    return JsonResponse({'status': 'success'})