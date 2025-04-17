from django.core.management.base import BaseCommand
from core.CustomerModel import Customer, PhoneNumber
from django.db import transaction

class Command(BaseCommand):
    help = 'Migrates existing customer phone numbers to the new PhoneNumber model'

    def handle(self, *args, **options):
        self.stdout.write("Starting phone number migration...")
        
        # Get all customers with phone numbers
        customers = Customer.objects.exclude(phone_number__isnull=True).exclude(phone_number='')
        counter = 0
        skipped = 0
        
        with transaction.atomic():
            for customer in customers:
                # Check if this number already exists in the PhoneNumber model
                existing = PhoneNumber.objects.filter(number=customer.phone_number).first()
                if existing:
                    self.stdout.write(self.style.WARNING(
                        f"Phone number {customer.phone_number} already exists for customer {existing.customer.name}. Skipping."
                    ))
                    skipped += 1
                    continue
                
                # Create a new PhoneNumber object for this customer
                try:
                    PhoneNumber.objects.create(
                        number=customer.phone_number,
                        customer=customer,
                        is_primary=True
                    )
                    counter += 1
                    if counter % 100 == 0:
                        self.stdout.write(f"Migrated {counter} phone numbers...")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Error migrating phone number {customer.phone_number} for customer {customer.name}: {str(e)}"
                    ))
                    skipped += 1
        
        self.stdout.write(self.style.SUCCESS(
            f"Migration complete. {counter} phone numbers migrated. {skipped} numbers skipped."
        )) 