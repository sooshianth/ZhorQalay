from django.core.management.base import BaseCommand
from django.utils import timezone
from sms_api.models import SmsQueue
from sms_api.apis import process_sms_queue

class Command(BaseCommand):
    help = 'Retry failed SMS messages'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Maximum number of retry attempts',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=20,
            help='Number of SMS messages to process in one batch',
        )
        parser.add_argument(
            '--id',
            type=int,
            default=None,
            help='ID of a specific SMS to retry',
        )

    def handle(self, *args, **options):
        max_retries = options['max_retries']
        batch_size = options['batch_size']
        specific_id = options['id']
        
        self.stdout.write(f"Starting retry for failed SMS messages")
        
        # Query for failed messages
        query = SmsQueue.objects.filter(status='failed')
        
        if specific_id:
            query = query.filter(id=specific_id)
        else:
            query = query.filter(retry_count__lt=max_retries)
        
        count = query.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No failed SMS messages to retry"))
            return
        
        self.stdout.write(f"Found {count} failed SMS messages to retry")
        
        # Update status to pending
        query.update(status='pending')
        
        # Process the queue
        results = process_sms_queue(batch_size=batch_size)
        
        # Show results summary
        sent_count = sum(1 for r in results if r.get('status') == 'sent')
        failed_count = sum(1 for r in results if r.get('status') == 'failed')
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Retried {len(results)} SMS messages: {sent_count} sent, {failed_count} failed"
            )
        ) 