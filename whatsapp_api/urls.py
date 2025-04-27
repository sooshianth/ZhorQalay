from django.urls import path
from .views import whatsapp_dashboard
from .views import send_whatsapp, message_history

urlpatterns = [
    path('send_whatapp', send_whatsapp),
    path('whatsapp_dashboard', whatsapp_dashboard),
    path('history', message_history),
]
