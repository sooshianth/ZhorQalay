from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import models
from rest_framework.decorators import api_view
from .MessageModel import Message
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
def get_username(request, user_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({'username': user.username})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def chat_history(request, user_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        # تاریخچه پیام‌های خصوصی
        messages = Message.objects.filter(
            (models.Q(sender=request.user) & models.Q(receiver_id=user_id)) |
            (models.Q(sender_id=user_id) & models.Q(receiver=request.user)),
            is_global=False
        ).values('sender_id', 'receiver_id', 'message', 'file_url', 'file_type', 'timestamp')
        
        # علامت‌گذاری پیام‌ها به عنوان خوانده‌شده
        Message.objects.filter(
            sender_id=user_id,
            receiver=request.user,
            is_global=False,
            is_read=False
        ).update(is_read=True)
        
        return JsonResponse(list(messages), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def global_chat_history(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        # تاریخچه پیام‌های عمومی
        messages = Message.objects.filter(
            is_global=True
        ).order_by('-timestamp')[:100].values('sender_id', 'message', 'file_url', 'file_type', 'timestamp')
        
        # اضافه کردن نام کاربری به هر پیام
        for msg in messages:
            try:
                user = User.objects.get(id=msg['sender_id'])
                msg['username'] = user.username
            except User.DoesNotExist:
                msg['username'] = 'کاربر ناشناس'
        
        # علامت‌گذاری پیام‌های عمومی به عنوان خوانده‌شده
        Message.objects.filter(
            is_global=True,
            is_read=False
        ).exclude(sender=request.user).update(is_read=True)
                
        return JsonResponse(list(messages), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
def upload_file(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        file = request.FILES['file']
        receiver_id = request.POST.get('receiver_id')
        is_global = request.POST.get('is_global', 'false').lower() == 'true'
        
        # اطمینان از وجود پوشه chat_files
        chat_files_dir = os.path.join(settings.MEDIA_ROOT, 'chat_files')
        os.makedirs(chat_files_dir, exist_ok=True)
        
        # ذخیره فایل با نام منحصربه‌فرد برای جلوگیری از تداخل
        file_name = f"{request.user.id}_{receiver_id or 'global'}_{file.name}"
        file_path = os.path.join(chat_files_dir, file_name)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        file_url = request.build_absolute_uri(settings.MEDIA_URL + 'chat_files/' + file_name)
        return JsonResponse({'file_url': file_url})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def online_users(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        # در یک سیستم واقعی باید از یک مکانیزم ذخیره‌سازی وضعیت آنلاین کاربران استفاده کرد
        # اینجا فرض می‌کنیم همه کاربران آنلاین هستند
        users = User.objects.exclude(id=request.user.id).values('id', 'username')
        return JsonResponse(list(users), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def unread_messages_count(request):
    """دریافت تعداد پیام‌های خصوصی خوانده نشده"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        # گروه‌بندی بر اساس فرستنده
        unread_messages = Message.objects.filter(
            receiver=request.user,
            is_global=False,
            is_read=False
        )
        
        # تعداد کل پیام‌های خوانده نشده
        total_count = unread_messages.count()
        
        # تعداد پیام‌های خوانده نشده به تفکیک کاربر
        by_user = {}
        for msg in unread_messages:
            sender_id = str(msg.sender_id)
            if sender_id not in by_user:
                by_user[sender_id] = 0
            by_user[sender_id] += 1
        
        return JsonResponse({
            'count': total_count,
            'by_user': by_user
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def unread_global_messages_count(request):
    """دریافت تعداد پیام‌های عمومی خوانده نشده"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        # تعداد پیام‌های عمومی خوانده نشده (به جز پیام‌های خودم)
        count = Message.objects.filter(
            is_global=True,
            is_read=False
        ).exclude(sender=request.user).count()
        
        return JsonResponse({
            'count': count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['POST'])
def mark_messages_as_read(request):
    """علامت‌گذاری پیام‌ها به عنوان خوانده‌شده"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        sender_id = request.data.get('sender_id')
        is_global = request.data.get('is_global', False)
        
        if is_global:
            # علامت‌گذاری همه پیام‌های عمومی به عنوان خوانده‌شده
            count = Message.objects.filter(
                is_global=True,
                is_read=False
            ).exclude(sender=request.user).update(is_read=True)
        elif sender_id:
            # علامت‌گذاری پیام‌های خصوصی از یک کاربر خاص
            count = Message.objects.filter(
                sender_id=sender_id,
                receiver=request.user,
                is_global=False,
                is_read=False
            ).update(is_read=True)
        else:
            return JsonResponse({'error': 'sender_id or is_global required'}, status=400)
        
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)