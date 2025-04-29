# notifications.py
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail

class PurchaseReminder:
    def __init__(self, purchase):
        self.purchase = purchase
        
    def check_delays(self):
        """بررسی تاخیر در هر مرحله"""
        now = timezone.now()
        
        if self.purchase.state == 'PAYMENT_VERIFIED':
            days_since_payment = (now - self.purchase.updated_at).days
            if days_since_payment > 2:
                self.send_reminder(
                    'تاخیر در تخصیص',
                    f'خرید {self.purchase.invoice_id} بیش از 48 ساعت در انتظار تخصیص است'
                )