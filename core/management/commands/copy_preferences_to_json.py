from django.core.management.base import BaseCommand
import json
from core.CustomerModel import Customer
import logging

logger = logging.getLogger("bugs")

class Command(BaseCommand):
    help = 'کپی ترجیحات مشتری از فیلدهای ManyToMany به فیلدهای JSON'

    def handle(self, *args, **options):
        logger.debug('Starting to copy customer preferences...')
        
        customers = Customer.objects.all()
        count = 0
        
        for customer in customers:
            # کپی زمینه فعالیت
            field_of_activity_codes = [activity.code for activity in customer.field_of_activity.all()]
            customer._field_of_activity_json = json.dumps(field_of_activity_codes)
            
            # کپی ترجیحات کالایی
            product_preferences_codes = [preference.code for preference in customer.product_preferences.all()]
            customer._product_preferences_json = json.dumps(product_preferences_codes)
            
            # کپی ترجیحات پرداخت
            purchase_preferences_codes = [preference.code for preference in customer.purchase_preferences.all()]
            customer._purchase_preferences_json = json.dumps(purchase_preferences_codes)
            
            # ذخیره تغییرات
            try:
                customer.save(update_fields=['_field_of_activity_json', '_product_preferences_json', '_purchase_preferences_json'])
                count += 1
            except Exception as e:
                logger.error(f'Error saving preferences for customer {customer.id}: {e}')
        
        logger.debug(f'Successfully copied preferences for {count} customers.')