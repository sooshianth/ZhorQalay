from django.core.management.base import BaseCommand
from django.utils import timezone
from sms_api.apis import process_sms_queue
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process pending SMS messages in the queue'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=20,
            help='Number of SMS messages to process in one batch',
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Also retry failed messages',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        retry_failed = options['retry_failed']
        
        start_time = timezone.now()
        self.stdout.write(f"Started SMS queue processing at {start_time}")
        
        try:
            results = process_sms_queue(batch_size=batch_size)
            
            # Show results summary
            sent_count = sum(1 for r in results if r.get('status') == 'sent')
            failed_count = sum(1 for r in results if r.get('status') == 'failed')
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed {len(results)} SMS messages: {sent_count} sent, {failed_count} failed"
                )
            )
            
            # Log individual failures
            for result in results:
                if result.get('status') == 'failed':
                    error_msg = result.get('error', 'Unknown error')
                    self.stdout.write(
                        self.style.WARNING(f"Failed to send SMS ID {result.get('id')}: {error_msg}")
                    )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error processing SMS queue: {str(e)}")
            )
            logger.exception("SMS queue processing error")
        
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        self.stdout.write(f"Finished SMS queue processing at {end_time} (took {duration:.2f} seconds)") 