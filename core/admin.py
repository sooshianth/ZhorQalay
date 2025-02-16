from django.contrib import admin
from .CallSessionModel import CallSession
from .CargoProductModel import CargoProduct
from .CustomerModel import Customer
from .FinancialManagerModel import FinancialManager
from .LogisticsManagerModel import LogisticsManager
from .PurchaseModel import Purchase
from .SalesAgentModel import SalesAgent
from .TaskModel import Task



admin.site.register(CallSession)
admin.site.register(CargoProduct)
admin.site.register(Customer)
admin.site.register(FinancialManager)
admin.site.register(LogisticsManager)
admin.site.register(Purchase)
admin.site.register(SalesAgent)
admin.site.register(Task)