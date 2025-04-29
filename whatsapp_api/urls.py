from django.urls import path
from . import views

urlpatterns = [
    path('send-whatsapp/', views.send_whatsapp, name='send-whatsapp'),
    path('whatsapp-dashboard/', views.whatsapp_dashboard, name='whatsapp-dashboard'),
    path('history/', views.message_history, name='message-history'),
    path('templates/', views.templates, name='templates'),
    path('queue/', views.whatsapp_queue, name='whatsapp-queue'),

]
