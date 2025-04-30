import pytest
from django.utils import timezone
from sms_api.models import SmsQueue, SmsLog


@pytest.mark.unit
class TestSmsQueue:
    @pytest.fixture
    def sms_queue_factory(self, db):
        def create_sms_queue(
            recipient_number="09123456789",
            message="Test message",
            notification_type="custom",
            status="pending",
            is_suspended=False,
            retry_count=0,
            scheduled_for=None,
            purchase=None
        ):
            if scheduled_for is None:
                scheduled_for = timezone.now()
                
            return SmsQueue.objects.create(
                recipient_number=recipient_number,
                message=message,
                notification_type=notification_type,
                status=status,
                is_suspended=is_suspended,
                retry_count=retry_count,
                scheduled_for=scheduled_for,
                purchase=purchase
            )
        return create_sms_queue
    
    def test_sms_queue_creation(self, sms_queue_factory):
        """Test that SmsQueue objects are created correctly."""
        now = timezone.now()
        sms = sms_queue_factory(
            recipient_number="09123456789",
            message="This is a test message",
            notification_type="payment_confirmation",
            status="pending",
            scheduled_for=now
        )
        
        assert sms.recipient_number == "09123456789"
        assert sms.message == "This is a test message"
        assert sms.notification_type == "payment_confirmation"
        assert sms.status == "pending"
        assert sms.is_suspended is False
        assert sms.retry_count == 0
        assert sms.scheduled_for == now
        assert sms.sent_at is None
    
    def test_sms_queue_str_representation(self, sms_queue_factory):
        """Test the string representation of an SmsQueue object."""
        sms = sms_queue_factory(
            recipient_number="09123456789",
            status="sent"
        )
        
        assert "09123456789" in str(sms)
        assert "ارسال شده" in str(sms)
    
    def test_sms_queue_with_purchase(self, sms_queue_factory, monkeypatch):
        """Test the relationship between SmsQueue and Purchase."""
        # Create a mock Purchase class
        class MockPurchase:
            def __init__(self, id):
                self.id = id
                
        # Create a mock instance
        mock_purchase = MockPurchase(id=123)
        
        # Create SmsQueue with the mock purchase
        sms = sms_queue_factory(
            recipient_number="09123456789",
            message="Test purchase notification",
            notification_type="new_purchase",
            purchase=mock_purchase
        )
        
        assert sms.purchase == mock_purchase
        assert sms.purchase_id == 123


@pytest.mark.unit
class TestSmsLog:
    @pytest.fixture
    def sms_log_factory(self, db):
        def create_sms_log(
            recipient_number="09123456789",
            message="Test message",
            notification_type="custom",
            status="sent",
            api_response=None,
            purchase=None
        ):
            return SmsLog.objects.create(
                recipient_number=recipient_number,
                message=message,
                notification_type=notification_type,
                status=status,
                api_response=api_response,
                purchase=purchase
            )
        return create_sms_log
    
    def test_sms_log_creation(self, sms_log_factory):
        """Test that SmsLog objects are created correctly."""
        sms_log = sms_log_factory(
            recipient_number="09123456789",
            message="This is a test log message",
            notification_type="payment_confirmation",
            status="sent",
            api_response="{'status': 'success', 'message_id': '12345'}"
        )
        
        assert sms_log.recipient_number == "09123456789"
        assert sms_log.message == "This is a test log message"
        assert sms_log.notification_type == "payment_confirmation"
        assert sms_log.status == "sent"
        assert sms_log.api_response == "{'status': 'success', 'message_id': '12345'}"
        assert sms_log.sent_at is not None
    
    def test_sms_log_str_representation(self, sms_log_factory):
        """Test the string representation of an SmsLog object."""
        sms_log = sms_log_factory(
            recipient_number="09123456789"
        )
        
        assert "09123456789" in str(sms_log)
        assert "at" in str(sms_log)
    
    def test_sms_log_with_purchase(self, sms_log_factory, monkeypatch):
        """Test the relationship between SmsLog and Purchase."""
        # Create a mock Purchase class
        class MockPurchase:
            def __init__(self, id):
                self.id = id
                
        # Create a mock instance
        mock_purchase = MockPurchase(id=123)
        
        # Create SmsLog with the mock purchase
        sms_log = sms_log_factory(
            recipient_number="09123456789",
            message="Test purchase log",
            notification_type="new_purchase",
            purchase=mock_purchase
        )
        
        assert sms_log.purchase == mock_purchase 