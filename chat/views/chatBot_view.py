from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db import models
from rest_framework.decorators import api_view
from chat.MessageModel import Message
import os
from django.conf import settings
import json
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from core.decorators.decorators import role_required
from django.core.cache import cache
import random
import mimetypes
import logging
import html
from core.logging_levels import *

logger = logging.getLogger("bugs")
audit_logger = logging.getLogger("audit")

# Allowed MIME types for file uploads
ALLOWED_MIME_TYPES = {
    # PDF
    'application/pdf',
    
    # Microsoft Office formats
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/vnd.ms-powerpoint',  # .ppt
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
    'application/vnd.ms-access',  # .mdb
    'application/vnd.openxmlformats-officedocument.database',  # .accdb
    
    # Archive formats
    'application/zip',  # .zip
    'application/x-rar-compressed',  # .rar
    'application/x-7z-compressed',  # .7z
    'application/x-tar',  # .tar
    'application/gzip',  # .gz
    
    # Image formats
    'image/jpeg',  # .jpg, .jpeg
    'image/png',  # .png
    'image/gif',  # .gif
    'image/bmp',  # .bmp
    'image/tiff',  # .tiff
    'image/webp',  # .webp
    'image/svg+xml',  # .svg
    'image/x-icon',  # .ico
    
    # Text and Data formats
    'text/csv',  # .csv
    'text/plain',  # .txt
    'text/richtext',  # .rtf
    'application/csv',  # .csv (alternative MIME type)
    'text/tab-separated-values',  # .tsv
    'application/json',  # .json
    'text/css',  # .css
    
    # OpenDocument formats
    'application/vnd.oasis.opendocument.text',  # .odt
    'application/vnd.oasis.opendocument.spreadsheet',  # .ods
    'application/vnd.oasis.opendocument.presentation',  # .odp
    
    # Google Docs formats
    'application/vnd.google-apps.document',  # Google Docs
    'application/vnd.google-apps.spreadsheet',  # Google Sheets
    'application/vnd.google-apps.presentation',  # Google Slides
}

# Maximum file size in bytes (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

# Rate limiting settings
RATE_LIMIT_SECONDS = 5
MESSAGE_RATE_LIMIT_SECONDS = 0.1

def get_client_ip(request):
    """
    دریافت IP کامل کلاینت (محلی و خارجی، پشتیبانی از proxy و load balancer)
    """
    if not request:
        return "Unknown"
        
    # IP مستقیم (از سرور دیده می‌شود)
    direct_ip = request.META.get('REMOTE_ADDR', 'Unknown')
        
    # IP از طریق proxy headers
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    real_ip = request.META.get('HTTP_X_REAL_IP')

    # انتخاب IP اصلی
    client_ip = direct_ip
    if forwarded_for:
        # اولین IP در لیست X-Forwarded-For
        client_ip = forwarded_for.split(',')[0].strip()
    elif real_ip:
        client_ip = real_ip
        
    # اگر proxy وجود دارد، هر دو IP را نمایش بده
    if forwarded_for or real_ip:
        proxy_info = f" (via {direct_ip})"
    else:
        proxy_info = ""
        
    return f"{client_ip}-{proxy_info}"

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def user_list(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt to access user list")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        audit_logger.info(f"User list accessed")
        users = User.objects.exclude(id=request.user.id).values('id', 'username')
        return JsonResponse(list(users), safe=False)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def get_username(request, user_id):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt to access user username: {user_id}")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        audit_logger.info(f"Getting username for user: {user_id}")
        user = User.objects.get(id=user_id)
        return JsonResponse({'username': user.username})
    except User.DoesNotExist:
        audit_logger.alert(f"404 error imppossible: {user_id}")
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def chat_history(request, user_id):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt to access chat history: {user_id}")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        audit_logger.info(f"Getting chat history for user: {user_id}")
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
        logger.error(f"Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def global_chat_history(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt to access global chat history")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        audit_logger.info(f"Getting global chat history")
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
        logger.error(f"Error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['POST'])
@login_required
def upload_file(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt to upload file")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    
    try:
        audit_logger.info(f"User is uploading a file")
        # Rate limiting check
        rate_limit_key = f"file_upload_rate_limit_{request.user.id}"
        if cache.get(rate_limit_key):
            audit_logger.alert(f"Rate limit exceeded for user")
            return JsonResponse({
                'error': f'لطفاً {RATE_LIMIT_SECONDS} ثانیه صبر کنید قبل از ارسال فایل بعدی'
            }, status=429)

        file = request.FILES.get('file')
        if not file:
            audit_logger.activity(f"File upload attempt without file")
            return JsonResponse({'error': 'هیچ فایلی ارسال نشده است'}, status=400)
        
        # Check file size
        if file.size > MAX_FILE_SIZE:
            audit_logger.activity(f"File size exceeds limit, file: {file.name}, size: {file.size}")
            return JsonResponse({
                'error': f'حجم فایل نمی‌تواند بیشتر از {MAX_FILE_SIZE // (1024*1024)} مگابایت باشد'
            }, status=400)
        
        # Check file type
        file_mime_type = file.content_type
        if file_mime_type not in ALLOWED_MIME_TYPES:
            audit_logger.alert(f"Unauthorized file type: {file_mime_type}, file: {file.name}")
            return JsonResponse({
                'error': 'نوع فایل مجاز نیست. فقط فایل‌های PDF، Office، آرشیو و تصاویر پذیرفته می‌شوند'
            }, status=400)
        
        # Additional security check for executable files
        file_extension = os.path.splitext(file.name)[1].lower()
        dangerous_extensions = {'.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.vbs', '.js', '.jar', '.msi', '.dmg', '.app', '.sh', '.sql','.sqlite', '.sqlite3'}
        if file_extension in dangerous_extensions:
            audit_logger.alert(f"Unauthorized executable file: {file.name}, type: {file_mime_type}")
            return JsonResponse({
                'error': 'فایل‌های اجرایی مجاز نیستند'
            }, status=400)
            
        receiver_id = request.POST.get('receiver_id')
        is_global = request.POST.get('is_global', 'false').lower() == 'true'
        reply_to = request.POST.get('reply_to')
        
        # Generate new file name: userid_senderid_date_time_random2digitvalue
        now = datetime.now()
        date_str = now.strftime('%Y%m%d')
        time_str = now.strftime('%H%M%S')
        random_digits = str(random.randint(10, 99))
        
        # Get file extension
        file_extension = os.path.splitext(file.name)[1]
        
        # Create new filename
        new_filename = f"{request.user.id}_{receiver_id or 'global'}_{date_str}_{time_str}_{random_digits}{file_extension}"
        
        chat_files_dir = os.path.join(settings.MEDIA_ROOT, 'chat_files')
        os.makedirs(chat_files_dir, exist_ok=True)
        
        file_path = os.path.join(chat_files_dir, new_filename)
        
        # Save file
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        file_url = f"{settings.MEDIA_URL}chat_files/{new_filename}"
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
                audit_logger.activity(f"File upload attempt without receiver ID")
                return JsonResponse({'error': 'شناسه گیرنده الزامی است'}, status=400)
                
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                audit_logger.activity(f"File upload attempt to non-existent user: {receiver_id}")
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
        
        # Set rate limit cache
        cache.set(rate_limit_key, True, timeout=RATE_LIMIT_SECONDS)
            
        return JsonResponse({
            'success': True,
            'file_url': file_url,
            'file_type': file.content_type,
            'message_id': message.id,
            'timestamp': timestamp.isoformat(),
            'reply_to': reply_to,
        })
    except Exception as e:
        audit_logger.error(f"Error occurred: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def online_users(request):
    if not request.user.is_authenticated:
        audit_logger.error(f"Hack attempt detected")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        audit_logger.info(f"Online users list requested")
        users = User.objects.exclude(id=request.user.id).values('id', 'username')
        return JsonResponse(list(users), safe=False)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def unread_messages_count(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt detected")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        audit_logger.info(f"Unread messages count requested")
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
        audit_logger.error(f"Error occurred: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['GET'])
@login_required
def unread_global_messages_count(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt detected")
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
        logger.error(f"Error occurred: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['POST'])
@login_required
def mark_messages_as_read(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt detected")
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
            audit_logger.activity(f"Invalid request data: sender_id or is_global required")
            return JsonResponse({'error': 'sender_id or is_global required'}, status=400)
        
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['POST'])
@login_required
def send_message(request):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt detected")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    
    try:
        # Rate limiting check for messages
        message_rate_limit_key = f"message_rate_limit_{request.user.id}"
        if cache.get(message_rate_limit_key):
            audit_logger.alert(f"Too many messages sent in a short period")
            return JsonResponse({
                'success': False,
                'error': f'لطفاً {MESSAGE_RATE_LIMIT_SECONDS} ثانیه صبر کنید قبل از ارسال پیام بعدی'
            }, status=429)
        
        message_text = request.data.get('message')
        #escape html tags
        message_text = html.escape(message_text)
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
                audit_logger.activity(f"Invalid request data: receiver_id is required")
                return JsonResponse({'error': 'شناسه گیرنده الزامی است'}, status=400)
            
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                audit_logger.activity(f"Invalid request data: receiver_id not found")
                return JsonResponse({'error': 'کاربر گیرنده یافت نشد'}, status=404)
            
            message = Message.objects.create(
                sender=request.user,
                receiver=receiver,
                message=message_text,
                is_global=False,
                timestamp=timestamp,
                reply_to_id=reply_to
            )
        
        # Set rate limit cache for messages
        cache.set(message_rate_limit_key, True, timeout=MESSAGE_RATE_LIMIT_SECONDS)
        
        return JsonResponse({
            'success': True,
            'message_id': message.id,
            'timestamp': timestamp.isoformat(),
            'reply_to': reply_to
        })
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    
@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['POST'])
@login_required
def pin_message(request, message_id):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt detected")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        msg = Message.objects.get(id=message_id)
        msg.is_pinned = True
        msg.save()
        return JsonResponse({'success': True, 'message_id': msg.id})
    except Message.DoesNotExist:
        audit_logger.activity(f"Invalid request data: message_id not found")
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")

@role_required('admin', 'logistics_manager', 'financial_manager', 'sales_agent', 'support_agent', 'employee')
@api_view(['POST'])
@login_required
def unpin_message(request, message_id):
    if not request.user.is_authenticated:
        audit_logger.alert(f"Hack attempt detected")
        return JsonResponse({'error': 'User not authenticated'}, status=401)
    try:
        msg = Message.objects.get(id=message_id)
        msg.is_pinned = False
        msg.save()
        return JsonResponse({'success': True, 'message_id': msg.id})
    except Message.DoesNotExist:
        audit_logger.activity(f"Invalid request data: message_id not found")
        return JsonResponse({'error': 'Message not found'}, status=404)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")