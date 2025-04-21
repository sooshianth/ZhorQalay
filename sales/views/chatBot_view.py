from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import models
from rest_framework.decorators import api_view
from core._models import Message
import os
from django.conf import settings

@api_view(['GET'])
def user_list(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        users = User.objects.exclude(id=request.user.id).values('id', 'username')
        return JsonResponse(list(users), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def chat_history(request, user_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        messages = Message.objects.filter(
            (models.Q(sender=request.user) & models.Q(receiver_id=user_id)) |
            (models.Q(sender_id=user_id) & models.Q(receiver=request.user))
        ).values('sender_id', 'receiver_id', 'message', 'file_url', 'file_type', 'timestamp')
        return JsonResponse(list(messages), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
def upload_file(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        file = request.FILES['file']
        receiver_id = request.POST['receiver_id']
        # اطمینان از وجود پوشه chat_files
        chat_files_dir = os.path.join(settings.MEDIA_ROOT, 'chat_files')
        os.makedirs(chat_files_dir, exist_ok=True)
        
        # ذخیره فایل با نام منحصربه‌فرد برای جلوگیری از تداخل
        file_name = f"{request.user.id}_{receiver_id}_{file.name}"
        file_path = os.path.join(chat_files_dir, file_name)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        file_url = request.build_absolute_uri(settings.MEDIA_URL + 'chat_files/' + file_name)
        return JsonResponse({'file_url': file_url})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)