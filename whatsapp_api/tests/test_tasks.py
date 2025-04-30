import pytest
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
from whatsapp_api.tasks import assign_customers_to_days, send_daily_whatsapp_messages, reset_daily_limits
from whatsapp_api.models import WhatsappNumber
from core.CustomerModel import Customer


@pytest.mark.unit
class TestAssignCustomersToDays:
    @pytest.fixture
    def setup_customers(self, db):
        # Create customers with WhatsApp preference enabled
        customers = []
        for i in range(30):
            c = Customer.objects.create(
                name=f"Customer {i}",
                whatsapp_preference=True, 
                day_of_week=None  # Not yet assigned to any day
            )
            customers.append(c)
        return customers
    
    def test_assign_customers_to_days(self, setup_customers):
        """Test that customers are assigned to days of the week."""
        assign_customers_to_days()
        
        # Check if all customers have been assigned a day
        for customer in Customer.objects.filter(whatsapp_preference=True):
            assert customer.day_of_week is not None
            assert 1 <= customer.day_of_week <= 7
        
        # Check distribution across days
        for day in range(1, 8):
            # Should have approximately equal distribution
            count = Customer.objects.filter(
                whatsapp_preference=True, 
                day_of_week=day
            ).count()
            # We have 30 customers, so each day should have about 4-5 customers
            # Allow for some flexibility in distribution
            assert 3 <= count <= 6, f"Day {day} has {count} customers, expected 4-5"


@pytest.mark.unit
class TestSendDailyWhatsappMessages:
    @pytest.fixture
    def setup_customers_and_whatsapp(self, db, monkeypatch):
        # Create customers with WhatsApp consent
        customers = []
        
        # Today's customers
        today = timezone.now().isoweekday()
        for i in range(5):
            c = Customer.objects.create(
                name=f"Today Customer {i}",
                whatsapp_consent=True,
                whatsapp_day=today
            )
            customers.append(c)
        
        # Customers who have received a message in the last week
        for i in range(3):
            c = Customer.objects.create(
                name=f"Recent Customer {i}",
                whatsapp_consent=True,
                whatsapp_day=today,
                last_whatsapp_sent=timezone.now() - timedelta(days=3)
            )
            customers.append(c)
        
        # Mock the send_whatsapp_message function
        mock_send = MagicMock(return_value=True)
        monkeypatch.setattr('whatsapp_api.tasks.send_whatsapp_message', mock_send)
        
        return {'customers': customers, 'mock_send': mock_send}
    
    def test_send_daily_messages(self, setup_customers_and_whatsapp):
        """Test sending daily WhatsApp messages."""
        mock_data = setup_customers_and_whatsapp
        
        # Call the task in test mode
        send_daily_whatsapp_messages(test_mode=True)
        
        # In test mode, no messages should be sent
        assert mock_data['mock_send'].call_count == 0
        
        # Call the task in normal mode
        send_daily_whatsapp_messages(test_mode=False)
        
        # Should only send to 5 customers (today's customers who haven't received a message in the last week)
        assert mock_data['mock_send'].call_count == 5
        
        # Check that last_whatsapp_sent was not updated since we're mocking
        for customer in Customer.objects.filter(name__startswith="Today Customer"):
            assert customer.last_whatsapp_sent is None


@pytest.mark.unit
class TestResetDailyLimits:
    @pytest.fixture
    def setup_whatsapp_numbers(self, db):
        # Create WhatsApp numbers with sent_today counts
        numbers = []
        for i in range(5):
            number = WhatsappNumber.objects.create(
                phone_number=f"98912345678{i}",
                sent_today=10 + i
            )
            numbers.append(number)
        return numbers
    
    def test_reset_daily_limits(self, setup_whatsapp_numbers):
        """Test resetting the daily limits for WhatsApp numbers."""
        # Verify initial state
        for i, number in enumerate(WhatsappNumber.objects.all()):
            assert number.sent_today == 10 + i
        
        # Call the task
        reset_daily_limits()
        
        # Verify all sent_today values are reset to 0
        for number in WhatsappNumber.objects.all():
            assert number.sent_today == 0 