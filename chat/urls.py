from django.urls import path
from django.views.generic.base import RedirectView
from .views import chatBot_view


urlpatterns = [
    
    path('api/users/', chatBot_view.user_list, name='user_list'),
    path('api/chat/history/<int:user_id>/', chatBot_view.chat_history, name='chat_history'),
    path('api/chat/upload/', chatBot_view.upload_file, name='upload_file'),
    path('api/chat/global/', chatBot_view.global_chat_history, name='global_chat_history'),
    path('api/online-users/', chatBot_view.online_users, name='online_users'),
    path('api/username/<int:user_id>/', chatBot_view.get_username, name='get_username'),
    
    # endpoint جدید برای ارسال پیام
    path('api/chat/send/', chatBot_view.send_message, name='send_message'),
    
    # مسیرهای جدید برای شمارش پیام‌های خوانده نشده
    path('api/chat/unread/count/', chatBot_view.unread_messages_count, name='unread_messages_count'),
    path('api/chat/global/unread/count/', chatBot_view.unread_global_messages_count, name='unread_global_messages_count'),
    path('api/chat/mark-as-read/', chatBot_view.mark_messages_as_read, name='mark_messages_as_read'),
]
