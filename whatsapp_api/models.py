from django.db import models

class WhatsappLog(models.Model):
    recipient_number = models.CharField(max_length=20)
    message = models.TextField(max_length=255)
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_from = models.ForeignKey('WhatsappNumber', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"WhatsApp to {self.recipient_number} at {self.sent_at}"

    class Meta:
        verbose_name = "تاریخچه واتساپ"
        verbose_name_plural = "تاریخچه پیام‌های واتساپ"

class WhatsappNumber(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    daily_limit = models.IntegerField(default=50)
    sent_today = models.IntegerField(default=0)
    messages_sent = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.phone_number

    class Meta:
        verbose_name = "شماره واتساپ"
        verbose_name_plural = "شماره های واتساپ"