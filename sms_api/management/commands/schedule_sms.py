from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from sms_api.models import SmsQueue

class Command(BaseCommand):
    help = 'Schedule an SMS message for delivery'

    def add_arguments(self, parser):
        parser.add_argument('number', type=str, help='Phone number to send to (e.g., 09123456789)')
        parser.add_argument('message', type=str, help='Message content')
        parser.add_argument(
            '--delay',
            type=int,
            default=0,
            help='Minutes to delay before sending (default: immediate)',
        )
        parser.add_argument(
            '--type',
            type=str,
            default='custom',
            choices=['custom', 'new_purchase', 'payment_confirmation', 'address_notification', 'barnameh_notification', 'extelaf_notification'],
            help='Type of notification',
        )
        parser.add_argument(
            '--purchase-id',
            type=int,
            default=None,
            help='Associated purchase ID if applicable',
        )
        parser.add_argument(
            '--suspend',
            action='store_true',
            help='Create the message in suspended state',
        )

    def handle(self, *args, **options):
        number = options['number']
        message = options['message']
        delay_minutes = options['delay']
        notification_type = options['type']
        purchase_id = options['purchase_id']
        suspended = options['suspend']
        
        # Clean up phone number
        if number.startswith('+98'):
            number = '0' + number[3:]
        elif not number.startswith('0'):
            number = '0' + number
        
        # Set scheduled time
        scheduled_time = timezone.now()
        if delay_minutes > 0:
            scheduled_time += timedelta(minutes=delay_minutes)
        
        # Determine status
        status = 'suspended' if suspended else 'pending'
        
        # Create the SMS queue entry
        sms = SmsQueue.objects.create(
            recipient_number=number,
            message=message,
            notification_type=notification_type,
            status=status,
            is_suspended=suspended,
            scheduled_for=scheduled_time,
            purchase_id=purchase_id
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"SMS scheduled for {scheduled_time} with ID: {sms.id}"
            )
        ) 