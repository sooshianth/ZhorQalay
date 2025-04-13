from django.contrib import admin
from .models import WhatsappNumber, WhatsappLog

@admin.register(WhatsappNumber)
class WhatsappNumberAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'is_active', 'messages_sent','priority','chrome_profile')

@admin.register(WhatsappLog)
class WhatsappLogAdmin(admin.ModelAdmin):
    list_display = ('recipient_number','sent_at','sent_from')
