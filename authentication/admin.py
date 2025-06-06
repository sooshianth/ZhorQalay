from django.contrib import admin
from .models import UserPhoneNumber

@admin.register(UserPhoneNumber)
class UserPhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number')
    search_fields = ('user__username', 'phone_number')
    list_filter = ('user__is_active', 'user__is_staff')
    list_per_page = 25
    list_display_links = ('user', 'phone_number')
    list_select_related = ('user',)