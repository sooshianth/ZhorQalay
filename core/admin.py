from django.contrib import admin
from .CallSessionModel import CallSession
from .CargoProductModel import CargoProduct
from .CustomerModel import Customer
from .FinancialManagerModel import FinancialManager
from .LogisticsManagerModel import LogisticsManager
from .PurchaseModel import Purchase, PurchaseHistory
from .SalesAgentModel import SalesAgent
from .TaskModel import Task

# تنظیمات نمایش مدل CargoProduct در ادمین
@admin.register(CargoProduct)
class CargoProductAdmin(admin.ModelAdmin):
    list_display = ('cottage', 'product_type', 'country', 'importer_name', 'weight', 'status')
    list_filter = ('product_type', 'country', 'status')
    search_fields = ('cottage', 'importer_name')
    ordering = ('-created_at',)

# تنظیمات نمایش مدل Customer در ادمین
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'city', 'field_of_activity', 'sales_agent', 'created_at')
    list_filter = ('field_of_activity', 'city', 'sales_agent')
    search_fields = ('name', 'phone_number')
    ordering = ('-created_at',)

# تنظیمات نمایش مدل Purchase در ادمین
@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('purchase_number', 'customer', 'weight', 'amount_paid', 'is_paid', 'is_delivered', 'created_at')
    list_filter = ('is_paid', 'is_delivered', 'is_canceled', 'is_archived')
    search_fields = ('purchase_number', 'customer__name')
    ordering = ('-created_at',)

# تنظیمات نمایش مدل PurchaseHistory در ادمین
@admin.register(PurchaseHistory)
class PurchaseHistoryAdmin(admin.ModelAdmin):
    list_display = ('purchase', 'user', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('purchase__purchase_number', 'user__username')
    ordering = ('-timestamp',)

# تنظیمات نمایش مدل SalesAgent در ادمین
@admin.register(SalesAgent)
class SalesAgentAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'user')
    search_fields = ('name', 'phone_number')
    ordering = ('name',)

# تنظیمات نمایش مدل Task در ادمین
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('customer', 'description', 'status', 'due_date', 'create_time')
    list_filter = ('status', 'customer__sales_agent')
    search_fields = ('customer__name', 'description')
    ordering = ('-create_time',)

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