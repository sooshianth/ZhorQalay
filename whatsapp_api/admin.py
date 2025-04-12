from django.contrib import admin
from .models import WhatsappNumber

@admin.register(WhatsappNumber)
class WhatsappNumberAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'is_active', 'messages_sent','priority','chrome_profile')
