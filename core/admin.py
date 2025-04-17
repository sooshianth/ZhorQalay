from django.contrib import admin
from .CallSessionModel import CallSession
from .CargoProductModel import CargoProduct
from .CustomerModel import Customer, PhoneNumber
from .FinancialManagerModel import FinancialManager
from .LogisticsManagerModel import LogisticsManager
from .PurchaseModel import Purchase, PurchaseHistory, ShenaseTakhsis
from .SalesAgentModel import SalesAgent
from .TaskModel import Task
from .NotificationModel import Notification

# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ('user', 'message')

# تنظیمات نمایش مدل CargoProduct در ادمین
@admin.register(CargoProduct)
class CargoProductAdmin(admin.ModelAdmin):
    list_display = ('cottage', 'product_type', 'country', 'importer_name', 'port', 'weight', 'status')
    list_filter = ('product_type', 'country', 'importer_name', 'port', 'status')
    search_fields = ('cottage', 'importer_name')
    ordering = ('-created_at',)

class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 1

class PurchaseInline(admin.TabularInline):
    model = Purchase
    fields = ( 'purchase_number', 'weight', 'amount_paid', 'is_paid', 'is_barnamed', 'created_at')
    extra = 0

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    search_fields = ('name', 'phone_number')
    list_display = ('pk', 'name', 'get_primary_phone', 'city', 'field_of_activity')
    list_filter = ('field_of_activity', 'city', 'sms_preference', 'whatsapp_preference')
    ordering = ('-created_at',)
    inlines = [PhoneNumberInline, PurchaseInline]
    
    def get_primary_phone(self, obj):
        return obj.get_primary_phone()
    get_primary_phone.short_description = 'شماره تلفن اصلی'

class ShenaseTakhsisInline(admin.TabularInline):
    model = ShenaseTakhsis
    extra = 1
    verbose_name = "شناسه تخصیص"
    verbose_name_plural = "شناسه‌های تخصیص"

# تنظیمات نمایش مدل Purchase در ادمین
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('invoice_id', 'purchase_number', 'customer', 'weight', 'amount_paid', 'is_paid', 'is_barnamed', 'created_at')
    list_filter = ('customer', 'is_paid', 'is_delivered', 'is_canceled', 'is_archived')
    search_fields = ('invoice_id', 'purchase_number', 'customer__name', 'customer__phone_number', 'customer__sales_agent__name')
    ordering = ('-created_at',)
    inlines = [ShenaseTakhsisInline]

# تنظیمات نمایش مدل PurchaseHistory در ادمین
# @admin.register(PurchaseHistory)
# class PurchaseHistoryAdmin(admin.ModelAdmin):
#     list_display = ('purchase', 'user', 'timestamp')
#     list_filter = ('timestamp',)
#     search_fields = ('purchase__purchase_number', 'user__username')
#     ordering = ('-timestamp',)

# تنظیمات نمایش مدل ShenaseTakhsis در ادمین
# @admin.register(ShenaseTakhsis)
# class ShenaseTakhsisAdmin(admin.ModelAdmin):
#     list_display = ('purchase', 'code', 'created_at')
#     list_filter = ('created_at',)
#     search_fields = ('purchase__purchase_number', 'code')
#     ordering = ('-created_at',)

# تنظیمات نمایش مدل SalesAgent در ادمین
@admin.register(SalesAgent)
class SalesAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)

# تنظیمات نمایش مدل Task در ادمین
# @admin.register(Task)
# class TaskAdmin(admin.ModelAdmin):
#     list_display = ('customer', 'description', 'status', 'due_date',  'create_time')
#     list_filter = ('status',)
#     search_fields = ('customer__name', 'description')
#     ordering = ('due_date',)

# تنظیمات نمایش مدل CallSession در ادمین
@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'date')
    list_filter = ('date', 'customer__sales_agent')
    ordering = ('-date',)

# تنظیمات نمایش مدل FinancialManager در ادمین
@admin.register(FinancialManager)
class FinancialManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)

# تنظیمات نمایش مدل LogisticsManager در ادمین
@admin.register(LogisticsManager)
class LogisticsManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)

@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('number', 'customer', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('number', 'customer__name')
    raw_id_fields = ('customer',)