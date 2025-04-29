from .Notification import Notification

class NotificationService:
    @staticmethod
    def create_notification(user, title, message, notification_type='system', priority='low'):
        """ایجاد نوتیفیکیشن جدید"""
        return Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority
        )
    
    @staticmethod
    def mark_as_read(notification_id):
        """علامت‌گذاری نوتیفیکیشن به عنوان خوانده شده"""
        try:
            notification = Notification.objects.get(id=notification_id)
            notification.is_read = True
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
    
    @staticmethod
    def get_unread_notifications(user):
        """دریافت نوتیفیکیشن‌های خوانده نشده کاربر"""
        return Notification.objects.filter(user=user, is_read=False)
    
    @staticmethod
    def get_all_notifications(user):
        """دریافت تمام نوتیفیکیشن‌های کاربر"""
        return Notification.objects.filter(user=user)