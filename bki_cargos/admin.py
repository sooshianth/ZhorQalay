from django.contrib import admin
from core._models import Barbary, VaredKonandeh

@admin.register(Barbary)
class BarbaryAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email')
    search_fields = ('name', 'phone_number', 'email')
    ordering = ('-id',)

@admin.register(VaredKonandeh)
class VaredKonandehAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'email', 'website', 'balance')
    search_fields = ('name', 'phone_number', 'email', 'website')
    ordering = ('-id',) 