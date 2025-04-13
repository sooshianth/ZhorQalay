from django.urls import path
from .views import test_whatsapp_sending

urlpatterns = [
    path('test-whatsapp/', test_whatsapp_sending),
]
