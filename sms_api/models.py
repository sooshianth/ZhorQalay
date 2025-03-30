from django.db import models

class SmsLog(models.Model):
    recipient_number = models.CharField(max_length=11)
    message = models.TextField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {self.recipient_number} at {self.sent_at}"
