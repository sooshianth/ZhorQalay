from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from core._models import Notification

@login_required
@require_POST
def delete_notification(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.delete()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)
