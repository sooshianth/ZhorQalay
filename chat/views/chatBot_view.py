from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import models
from rest_framework.decorators import api_view
from chat.MessageModel import Message
import os
from django.conf import settings
import json
from datetime import datetime


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
        messages = Message.objects.filter(
            (models.Q(sender=request.user) & models.Q(receiver_id=user_id)) |
            (models.Q(sender_id=user_id) & models.Q(receiver=request.user)),
            is_global=False
        ).values('id', 'sender_id', 'receiver_id', 'message', 'file_url', 'file_type', 'timestamp', 'reply_to', 'is_pinned')
        
        reply_ids = [m['reply_to'] for m in messages if m['reply_to']]
        replies = Message.objects.filter(id__in=reply_ids).values('id', 'message', 'sender__username')
        reply_map = {r['id']: r for r in replies}
        for m in messages:
            if m['reply_to']:
                r = reply_map.get(m['reply_to'])
                m['reply_to_message'] = r['message'] if r else ''
                m['reply_to_author'] = r['sender__username'] if r else ''

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
        messages = Message.objects.filter(
            is_global=True
        ).order_by('-timestamp')[:100].values('sender_id', 'message', 'file_url', 'file_type', 'timestamp', 'reply_to', 'is_pinned')
        
        reply_ids = [m['reply_to'] for m in messages if m['reply_to']]
        replies = Message.objects.filter(id__in=reply_ids).values('id', 'message', 'sender__username')
        reply_map = {r['id']: r for r in replies}
        for m in messages:
            if m['reply_to']:
                r = reply_map.get(m['reply_to'])
                m['reply_to_message'] = r['message'] if r else ''
                m['reply_to_author'] = r['sender__username'] if r else ''
            try:
                user = User.objects.get(id=m['sender_id'])
                m['username'] = user.username
            except User.DoesNotExist:
                m['username'] = 'کاربر ناشناس'
        
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
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({'error': 'هیچ فایلی ارسال نشده است'}, status=400)
            
        receiver_id = request.POST.get('receiver_id')
        is_global = request.POST.get('is_global', 'false').lower() == 'true'
        reply_to = request.POST.get('reply_to')
        
        chat_files_dir = os.path.join(settings.MEDIA_ROOT, 'chat_files')
        os.makedirs(chat_files_dir, exist_ok=True)
        
        file_name = f"{request.user.id}_{receiver_id or 'global'}_{file.name}"
        file_path = os.path.join(chat_files_dir, file_name)
        
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        file_url = f"{settings.MEDIA_URL}chat_files/{file_name}"
        timestamp = datetime.now()
        
        if is_global:
            message = Message.objects.create(
                sender=request.user,
                receiver=request.user,
                file_url=file_url,
                file_type=file.content_type,
                is_global=True,
                timestamp=timestamp,
                reply_to_id=reply_to
            )
        else:
            if not receiver_id:
                return JsonResponse({'error': 'شناسه گیرنده الزامی است'}, status=400)
                
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                return JsonResponse({'error': 'کاربر گیرنده یافت نشد'}, status=404)
                
            message = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                file_url=file_url,
                file_type=file.content_type,
                is_global=False,
                timestamp=timestamp,
                reply_to_id=reply_to
            )
            
        return JsonResponse({
            'success': True,
            'file_url': file_url,
            'file_type': file.content_type,
            'message_id': message.id,
            'timestamp': timestamp.isoformat(),
            'reply_to': reply_to
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def online_users(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        users = User.objects.exclude(id=request.user.id).values('id', 'username')
        return JsonResponse(list(users), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
def unread_messages_count(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        unread_messages = Message.objects.filter(
            receiver=request.user,
            is_global=False,
            is_read=False
        )
        
        total_count = unread_messages.count()
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
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
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
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        sender_id = request.data.get('sender_id')
        is_global = request.data.get('is_global', False)
        
        if is_global:
            count = Message.objects.filter(
                is_global=True,
                is_read=False
            ).exclude(sender=request.user).update(is_read=True)
        elif sender_id:
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

@api_view(['POST'])
def send_message(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        message_text = request.data.get('message')
        is_global = request.data.get('is_global', False)
        receiver_id = request.data.get('receiver_id')
        reply_to = request.data.get('reply_to')
        
        if not message_text:
            return JsonResponse({'error': 'پیام نمی‌تواند خالی باشد'}, status=400)
        
        timestamp = datetime.now()
        
        if is_global:
            message = Message.objects.create(
                sender=request.user,
                receiver=request.user,
                message=message_text,
                is_global=True,
                timestamp=timestamp,
                reply_to_id=reply_to
            )
        else:
            if not receiver_id:
                return JsonResponse({'error': 'شناسه گیرنده الزامی است'}, status=400)
            
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                return JsonResponse({'error': 'کاربر گیرنده یافت نشد'}, status=404)
            
            message = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                message=message_text,
                is_global=False,
                timestamp=timestamp,
                reply_to_id=reply_to
            )
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'timestamp': timestamp.isoformat(),
            'reply_to': reply_to
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
from django.views.decorators.csrf import csrf_exempt

@api_view(['POST'])
@csrf_exempt
def pin_message(request, message_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        msg = Message.objects.get(id=message_id)
        msg.is_pinned = True
        msg.save()
        return JsonResponse({'success': True, 'message_id': msg.id})
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)
    
@api_view(['POST'])
@csrf_exempt
def unpin_message(request, message_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        msg = Message.objects.get(id=message_id)
        msg.is_pinned = False
        msg.save()
        return JsonResponse({'success': True, 'message_id': msg.id})
    except Message.DoesNotExist:
        return JsonResponse({'error': 'Message not found'}, status=404)