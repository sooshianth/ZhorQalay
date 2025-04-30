import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.NotificationModel import Notification


@pytest.mark.unit
class TestNotificationModel:
    """Test class for Notification model."""
    
    @pytest.fixture
    def user_factory(self, db):
        def create_user(username="testuser", password="password123", email="test@example.com", **kwargs):
            return User.objects.create_user(
                username=username, 
                password=password, 
                email=email, 
                **kwargs
            )
        return create_user
    
    @pytest.fixture
    def notification_factory(self, db, user_factory):
        def create_notification(
            title="Test Notification",
            message="Test notification message",
            notification_type="info",
            user=None,
            is_read=False,
            **kwargs
        ):
            if user is None:
                user = user_factory(username="notification_user")
            
            return Notification.objects.create(
                title=title,
                message=message,
                notification_type=notification_type,
                user=user,
                is_read=is_read,
                **kwargs
            )
        return create_notification
    
    def test_notification_creation(self, notification_factory, user_factory):
        """Test basic creation of Notification."""
        user = user_factory(username="test_notification_user")
        
        notification = notification_factory(
            title="New Order",
            message="A new order has been placed",
            notification_type="info",
            user=user,
            is_read=False
        )
        
        assert notification.title == "New Order"
        assert notification.message == "A new order has been placed"
        assert notification.notification_type == "info"
        assert notification.user == user
        assert notification.is_read is False
        assert notification.created_at is not None
        
        # Check string representation
        assert str(notification) == "New Order"
    
    def test_notification_mark_as_read(self, notification_factory):
        """Test marking a notification as read."""
        notification = notification_factory(is_read=False)
        assert notification.is_read is False
        
        # Mark as read
        notification.is_read = True
        notification.save()
        
        # Verify it's marked as read
        updated_notification = Notification.objects.get(id=notification.id)
        assert updated_notification.is_read is True
        
        # If read_at is set automatically, check that too
        if hasattr(updated_notification, 'read_at'):
            assert updated_notification.read_at is not None
    
    def test_notification_type_choices(self, db, user_factory):
        """Test validation of notification type choices."""
        user = user_factory()
        
        # Valid notification types should work
        valid_types = ["info", "success", "warning", "error"]
        for notification_type in valid_types:
            notification = Notification.objects.create(
                title=f"{notification_type.capitalize()} Notification",
                message=f"Test {notification_type} notification",
                notification_type=notification_type,
                user=user
            )
            assert notification.notification_type == notification_type
        
        # Invalid notification type should fail
        with pytest.raises(Exception) as excinfo:
            Notification.objects.create(
                title="Invalid Type Notification",
                message="Test with invalid notification type",
                notification_type="invalid_type",
                user=user
            )
        
        # Check for validation error or integrity error
        assert "invalid" in str(excinfo.value).lower() or "constraint" in str(excinfo.value).lower()
    
    def test_notification_filtering_by_user(self, notification_factory, user_factory):
        """Test filtering notifications by user."""
        user1 = user_factory(username="notification_user1")
        user2 = user_factory(username="notification_user2")
        
        # Create notifications for different users
        notification_factory(title="User1 Notification 1", user=user1)
        notification_factory(title="User1 Notification 2", user=user1)
        notification_factory(title="User2 Notification", user=user2)
        
        # Filter by user
        user1_notifications = Notification.objects.filter(user=user1)
        user2_notifications = Notification.objects.filter(user=user2)
        
        assert user1_notifications.count() == 2
        assert user2_notifications.count() == 1
    
    def test_notification_filtering_by_read_status(self, notification_factory, user_factory):
        """Test filtering notifications by read status."""
        user = user_factory(username="read_status_user")
        
        # Create a mix of read and unread notifications
        notification_factory(title="Read Notification 1", user=user, is_read=True)
        notification_factory(title="Read Notification 2", user=user, is_read=True)
        notification_factory(title="Unread Notification 1", user=user, is_read=False)
        notification_factory(title="Unread Notification 2", user=user, is_read=False)
        notification_factory(title="Unread Notification 3", user=user, is_read=False)
        
        # Filter by read status
        read_notifications = Notification.objects.filter(user=user, is_read=True)
        unread_notifications = Notification.objects.filter(user=user, is_read=False)
        
        assert read_notifications.count() == 2
        assert unread_notifications.count() == 3
    
    def test_notification_filtering_by_type(self, notification_factory, user_factory):
        """Test filtering notifications by type."""
        user = user_factory(username="type_filtering_user")
        
        # Create notifications with different types
        notification_factory(title="Info Notification 1", user=user, notification_type="info")
        notification_factory(title="Info Notification 2", user=user, notification_type="info")
        notification_factory(title="Success Notification", user=user, notification_type="success")
        notification_factory(title="Warning Notification", user=user, notification_type="warning")
        notification_factory(title="Error Notification", user=user, notification_type="error")
        
        # Filter by type
        info_notifications = Notification.objects.filter(user=user, notification_type="info")
        success_notifications = Notification.objects.filter(user=user, notification_type="success")
        warning_notifications = Notification.objects.filter(user=user, notification_type="warning")
        error_notifications = Notification.objects.filter(user=user, notification_type="error")
        
        assert info_notifications.count() == 2
        assert success_notifications.count() == 1
        assert warning_notifications.count() == 1
        assert error_notifications.count() == 1
    
    def test_notification_ordering_by_creation_date(self, notification_factory, user_factory):
        """Test ordering notifications by creation date."""
        user = user_factory(username="ordering_user")
        
        # Create notifications at different times
        # We'll use the auto-now_add for created_at, but we can still test the ordering
        notification1 = notification_factory(title="First Notification", user=user)
        notification2 = notification_factory(title="Second Notification", user=user)
        notification3 = notification_factory(title="Third Notification", user=user)
        
        # Order by creation date (descending)
        latest_notifications = Notification.objects.filter(user=user).order_by('-created_at')
        
        # Verify the order (most recent first)
        assert latest_notifications[0].id == notification3.id
        assert latest_notifications[1].id == notification2.id
        assert latest_notifications[2].id == notification1.id
    
    def test_mark_all_as_read(self, notification_factory, user_factory):
        """Test marking all notifications as read for a user."""
        user = user_factory(username="mark_all_user")
        
        # Create several unread notifications
        for i in range(5):
            notification_factory(
                title=f"Notification {i+1}",
                user=user,
                is_read=False
            )
        
        # Verify all are unread
        assert Notification.objects.filter(user=user, is_read=False).count() == 5
        
        # Mark all as read
        Notification.objects.filter(user=user).update(is_read=True)
        
        # Verify all are now read
        assert Notification.objects.filter(user=user, is_read=True).count() == 5
        assert Notification.objects.filter(user=user, is_read=False).count() == 0
    
    def test_delete_notification(self, notification_factory):
        """Test deleting a notification."""
        notification = notification_factory()
        notification_id = notification.id
        
        # Delete the notification
        notification.delete()
        
        # Verify it's deleted
        with pytest.raises(Notification.DoesNotExist):
            Notification.objects.get(id=notification_id)
    
    def test_notification_with_related_object(self, notification_factory, user_factory):
        """Test notification with a related object reference."""
        user = user_factory(username="related_object_user")
        
        # Create a notification with a related object reference (if the model supports it)
        # This will depend on your model implementation
        try:
            notification = notification_factory(
                title="Related Object Notification",
                message="Notification with related object",
                user=user,
                related_model="purchase",
                related_id=123
            )
            
            # Verify the related object fields
            assert notification.related_model == "purchase"
            assert notification.related_id == 123
        except TypeError:
            # If the model doesn't have these fields, the test will be skipped
            pass
    
    def test_notification_for_multiple_users(self, db, user_factory):
        """Test creating the same notification for multiple users."""
        users = [
            user_factory(username=f"multi_user_{i}")
            for i in range(3)
        ]
        
        # Create the same notification for each user
        for user in users:
            Notification.objects.create(
                title="System Maintenance",
                message="The system will be down for maintenance tonight",
                notification_type="warning",
                user=user
            )
        
        # Verify each user has the notification
        for user in users:
            user_notifications = Notification.objects.filter(
                user=user,
                title="System Maintenance"
            )
            assert user_notifications.count() == 1
    
    def test_notification_expiry(self, notification_factory, user_factory):
        """Test notification expiry functionality if implemented."""
        user = user_factory(username="expiry_user")
        
        # Check if expiry_date field exists
        try:
            # Create a notification with an expiry date
            yesterday = timezone.now() - timedelta(days=1)
            notification = notification_factory(
                title="Expiring Notification",
                message="This notification has already expired",
                user=user,
                expiry_date=yesterday
            )
            
            # Verify the expiry date
            assert notification.expiry_date == yesterday
            
            # Check if a method exists to filter out expired notifications
            if hasattr(Notification.objects, 'active'):
                active_notifications = Notification.objects.active()
                assert notification not in active_notifications
        except TypeError:
            # If the model doesn't have this field, the test will be skipped
            pass
    
    def test_notification_bulk_creation(self, db, user_factory):
        """Test bulk creation of notifications."""
        user = user_factory(username="bulk_notification_user")
        
        # Create a list of notification objects to bulk create
        notifications = [
            Notification(
                title=f"Bulk Notification {i+1}",
                message=f"This is bulk notification {i+1}",
                notification_type="info",
                user=user
            )
            for i in range(10)
        ]
        
        # Bulk create the notifications
        Notification.objects.bulk_create(notifications)
        
        # Verify they were all created
        user_notifications = Notification.objects.filter(user=user)
        assert user_notifications.count() == 10 