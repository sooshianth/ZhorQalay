import pytest
from django.utils import timezone
from datetime import timedelta
from whatsapp_api.models import WhatsappNumber, WhatsappTemplate, WhatsappLog, WhatsappQueue


@pytest.mark.unit
class TestWhatsappNumber:
    @pytest.fixture
    def whatsapp_number_factory(self, db):
        def create_whatsapp_number(
            phone_number="989123456789",
            is_active=True,
            daily_limit=50,
            sent_today=0,
            messages_sent=0,
            priority=1,
            working_days="1,2,3,4,5,6,7"
        ):
            return WhatsappNumber.objects.create(
                phone_number=phone_number,
                is_active=is_active,
                daily_limit=daily_limit,
                sent_today=sent_today,
                messages_sent=messages_sent,
                priority=priority,
                working_days=working_days
            )
        return create_whatsapp_number
    
    def test_whatsapp_number_creation(self, whatsapp_number_factory):
        """Test that WhatsappNumber objects are created correctly."""
        number = whatsapp_number_factory(
            phone_number="989123456789",
            daily_limit=100,
            priority=2,
            working_days="1,2,3,4,5"
        )
        
        assert number.phone_number == "989123456789"
        assert number.is_active is True
        assert number.daily_limit == 100
        assert number.sent_today == 0
        assert number.messages_sent == 0
        assert number.priority == 2
        assert number.working_days == "1,2,3,4,5"
    
    def test_is_available_today(self, whatsapp_number_factory, monkeypatch):
        """Test if a number is available on the current day of the week."""
        # Create a number that works only on specific days
        number = whatsapp_number_factory(working_days="1,3,5")  # Only Saturday, Monday, Wednesday
        
        # Mock timezone.now to return Saturday (1)
        class MockDateTime:
            @classmethod
            def isoweekday(cls):
                return 1  # Saturday
        
        class MockTimezone:
            @classmethod
            def now(cls):
                return MockDateTime()
        
        monkeypatch.setattr(timezone, "now", MockTimezone.now)
        
        # Should be available on Saturday
        assert number.is_available_today() is True
        
        # Change to Sunday (2) - should not be available
        monkeypatch.setattr(MockDateTime, "isoweekday", lambda: 2)
        assert number.is_available_today() is False
        
        # Change to Monday (3) - should be available
        monkeypatch.setattr(MockDateTime, "isoweekday", lambda: 3)
        assert number.is_available_today() is True
    
    def test_can_send_more(self, whatsapp_number_factory, monkeypatch):
        """Test if a number can send more messages based on limits and availability."""
        # Create a number with specific settings
        number = whatsapp_number_factory(
            is_active=True,
            daily_limit=10,
            sent_today=8,
            working_days="1,2,3,4,5"  # Saturday to Wednesday
        )
        
        # Mock timezone.now to return Saturday (1)
        class MockDateTime:
            @classmethod
            def isoweekday(cls):
                return 1
        
        class MockTimezone:
            @classmethod
            def now(cls):
                return MockDateTime()
        
        monkeypatch.setattr(timezone, "now", MockTimezone.now)
        
        # Should be able to send more (active, within limit, available day)
        assert number.can_send_more() is True
        
        # Test reaching the daily limit
        number.sent_today = 10
        assert number.can_send_more() is False
        
        # Test inactive number
        number.sent_today = 5
        number.is_active = False
        assert number.can_send_more() is False
        
        # Test unavailable day
        number.is_active = True
        monkeypatch.setattr(MockDateTime, "isoweekday", lambda: 6)  # Thursday
        assert number.can_send_more() is False


@pytest.mark.unit
class TestWhatsappTemplate:
    @pytest.fixture
    def template_factory(self, db):
        def create_template(
            name="Test Template",
            template_type="WELCOME",
            content="Hello {name}, welcome to our service!",
            variables={"name": "Customer Name"},
            is_active=True
        ):
            return WhatsappTemplate.objects.create(
                name=name,
                template_type=template_type,
                content=content,
                variables=variables,
                is_active=is_active
            )
        return create_template
    
    def test_template_creation(self, template_factory):
        """Test that WhatsappTemplate objects are created correctly."""
        template = template_factory(
            name="Welcome Message",
            template_type="WELCOME",
            content="Hello {name}, welcome to our service!",
            variables={"name": "Customer Name"}
        )
        
        assert template.name == "Welcome Message"
        assert template.template_type == "WELCOME"
        assert template.content == "Hello {name}, welcome to our service!"
        assert template.variables == {"name": "Customer Name"}
        assert template.is_active is True
    
    def test_template_str_representation(self, template_factory):
        """Test the string representation of a template."""
        template = template_factory(name="Welcome", template_type="WELCOME")
        
        # Chedk the __str__ method
        assert "Welcome" in str(template)
        assert "پیام خوشامدگویی" in str(template)  # The display value of WELCOME


@pytest.mark.unit
class TestWhatsappLog:
    @pytest.fixture
    def log_factory(self, db, whatsapp_number_factory):
        def create_log(
            recipient_number="989123456789",
            message="Test message",
            sent_from=None,
            template_type="WELCOME"
        ):
            if sent_from is None:
                sent_from = whatsapp_number_factory()
                
            return WhatsappLog.objects.create(
                recipient_number=recipient_number,
                message=message,
                sent_from=sent_from,
                template_type=template_type
            )
        return create_log
    
    def test_log_creation(self, log_factory, whatsapp_number_factory):
        """Test that WhatsappLog objects are created correctly."""
        number = whatsapp_number_factory(phone_number="989876543210")
        log = log_factory(
            recipient_number="989123456789",
            message="Hello customer!",
            sent_from=number,
            template_type="WELCOME"
        )
        
        assert log.recipient_number == "989123456789"
        assert log.message == "Hello customer!"
        assert log.sent_from == number
        assert log.template_type == "WELCOME"
        assert log.sent_at is not None


@pytest.mark.unit
class TestWhatsappQueue:
    @pytest.fixture
    def queue_factory(self, db):
        def create_queue_item(
            recipient_number="989123456789",
            template_type="WELCOME",
            message="Test message",
            status="pending",
            retry_count=0
        ):
            return WhatsappQueue.objects.create(
                recipient_number=recipient_number,
                template_type=template_type,
                message=message,
                status=status,
                retry_count=retry_count
            )
        return create_queue_item
    
    def test_queue_creation(self, queue_factory):
        """Test that WhatsappQueue objects are created correctly."""
        queue_item = queue_factory(
            recipient_number="989123456789",
            template_type="WELCOME",
            message="Hello customer!",
            status="pending",
            retry_count=1
        )
        
        assert queue_item.recipient_number == "989123456789"
        assert queue_item.template_type == "WELCOME"
        assert queue_item.message == "Hello customer!"
        assert queue_item.status == "pending"
        assert queue_item.retry_count == 1
        assert queue_item.created_at is not None
        assert queue_item.sent_at is None 