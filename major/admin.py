from django.contrib import admin
from .models.NonBazargahProduct import NonBazargahProduct
from .models.Product import Product

@admin.register(NonBazargahProduct)
class NonBazargahProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'status')


