from django.contrib import admin
from .MessageModel import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'message', 'timestamp')
    search_fields = ('sender__name', 'receiver__name', 'message')
    ordering = ('-timestamp',)
