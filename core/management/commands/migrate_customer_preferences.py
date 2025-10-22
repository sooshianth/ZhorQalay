from django.core.management.base import BaseCommand
from django.db import transaction
from django.core import management
from django.apps import apps
import json
from core.CustomerModel import ActivityField, ProductPreference, PaymentPreference, Customer, FIELD_OF_ACTIVITY
from core.CargoProductModel import CargoProduct
import logging

logger = logging.getLogger("bugs")

class Command(BaseCommand):
    help = 'Migrates Customer JSONFields to ManyToMany models'

    def handle(self, *args, **options):
        logger.info('Starting Customer preference fields migration')
        
        # 1. Create the preference models if they don't exist
        self.create_preference_objects()
        
        # 2. Migrate data from JSONFields to ManyToMany relationships
        with transaction.atomic():
            self.migrate_customer_json_fields()
        
        logger.info('Migration completed successfully!')
    
    def create_preference_objects(self):
        """Create the preference objects for all choices"""
        logger.info('Creating preference objects...')
        
        # Create ActivityField objects
        for code, name in FIELD_OF_ACTIVITY:
            ActivityField.objects.get_or_create(code=code)
        logger.debug(f'Created {len(FIELD_OF_ACTIVITY)} activity fields')
        
        # Create ProductPreference objects
        product_choices = CargoProduct.PRODUCT_TYPES
        for code, name in product_choices:
            ProductPreference.objects.get_or_create(code=code)
        logger.debug(f'Created {len(product_choices)} product preferences')
        
        # Create PaymentPreference objects from PAYMENT_PREFERENCE_CHOICES
        payment_choices = [
            ('cash', 'نقدی'),
            ('check', 'چک'),
            ('credit', 'اعتباری'),
            ('transfer', 'انتقال بانکی'),
            ('bazaargah', 'بازارگاه')
        ]
        for code, name in payment_choices:
            PaymentPreference.objects.get_or_create(code=code)
        logger.debug(f'Created {len(payment_choices)} payment preferences')
    
    def migrate_customer_json_fields(self):
        """Migrate data from JSONFields to ManyToMany relationships"""
        logger.info('Migrating customer data...')
        count = 0
        
        for customer in Customer.objects.all():
            logger.debug(f'Processing customer {customer.id}: {customer.name}')
            
            # Field of activity
            if hasattr(customer, 'field_of_activity') and customer.field_of_activity:
                activities = self._get_list_from_field(customer.field_of_activity)
                for activity_code in activities:
                    try:
                        activity = ActivityField.objects.get(code=activity_code)
                        customer.field_of_activity.add(activity)
                    except ActivityField.DoesNotExist:
                        logger.warning(
                            f'Activity field with code {activity_code} does not exist for customer {customer.id}'
                        )
            
            # Product preferences
            if hasattr(customer, 'product_preferences') and customer.product_preferences:
                prefs = self._get_list_from_field(customer.product_preferences)
                for pref_code in prefs:
                    try:
                        pref = ProductPreference.objects.get(code=pref_code)
                        customer.product_preferences.add(pref)
                    except ProductPreference.DoesNotExist:
                        logger.warning(
                            f'Product preference with code {pref_code} does not exist for customer {customer.id}'
                        )
            
            # Purchase preferences
            if hasattr(customer, 'purchase_preferences') and customer.purchase_preferences:
                prefs = self._get_list_from_field(customer.purchase_preferences)
                for pref_code in prefs:
                    try:
                        pref = PaymentPreference.objects.get(code=pref_code)
                        customer.purchase_preferences.add(pref)
                    except PaymentPreference.DoesNotExist:
                        logger.warning(
                            f'Payment preference with code {pref_code} does not exist for customer {customer.id}'
                        )
            
            count += 1
        
        logger.info(f'Migrated preferences for {count} customers')
    
    def _get_list_from_field(self, field_value):
        """Extracts a list from a field value that could be a list, string, or JSON string"""
        if not field_value:
            return []
            
        # If it's already a list, return it directly
        if isinstance(field_value, list):
            return field_value
        
        # Handle string or JSON string
        if isinstance(field_value, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(field_value)
                if isinstance(parsed, list):
                    return parsed
                return [field_value]
            except (ValueError, TypeError):
                # It's a string, not JSON
                return [field_value]
            
        # Unknown type
        return [] 