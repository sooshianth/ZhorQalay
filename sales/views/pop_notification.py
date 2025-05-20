from django.http import JsonResponse
from core._models import Notification
from django.contrib.auth.decorators import login_required

@login_required
def get_unread_notifications(request):
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    return JsonResponse({
        'unread_count': notifications.count(),
        'notifications': [
            {
                'id': n.id,
                'message': n.message,
                'type': 'info',
                'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
                'icon': 'bell'
            } for n in notifications
        ]
    })
