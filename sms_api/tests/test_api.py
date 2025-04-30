import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
from sms_api.models import SmsQueue, SmsLog
from django.contrib.auth.models import User
from core.SalesAgentModel import SalesAgent
from core.CustomerModel import Customer


@pytest.mark.integration
class TestSmsApi:
    @pytest.fixture
    def api_client(self):
        return APIClient()
    
    @pytest.fixture
    def admin_user(self, db):
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpassword'
        )
        return user
    
    @pytest.fixture
    def authenticated_client(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        return api_client
    
    @pytest.fixture
    def sales_agent(self, db, admin_user):
        return SalesAgent.objects.create(
            user=admin_user,
            name="Test Agent",
            phone_number="9123456789",
            factor_code="TA"
        )
    
    @pytest.fixture
    def customer(self, db, sales_agent):
        customer = Customer.objects.create(
            name="Test Customer",
            phone_number="9123456789"
        )
        customer.sales_agent.add(sales_agent)
        return customer
    
    @pytest.mark.django_db
    @patch('sms_api.apis.send_sms')
    def test_send_sms_api(self, mock_send_sms, authenticated_client, customer):
        """Test the API endpoint for sending SMS."""
        # Configure the mock to return a successful response
        mock_response = {
            'status': 'success',
            'message_id': '12345',
            'messages': ['Message sent successfully']
        }
        mock_send_sms.return_value = mock_response
        
        # Define test data
        data = {
            'recipient_number': '09123456789',
            'message': 'This is a test SMS from the API',
            'customer_id': customer.id
        }
        
        # Make the API request
        url = reverse('sms_api:send_sms')
        response = authenticated_client.post(url, data, format='json')
        
        # Check response
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        assert mock_send_sms.called
        
        # Check that an SmsLog was created
        assert SmsLog.objects.filter(recipient_number='09123456789').exists()
    
    @pytest.mark.django_db
    def test_get_sms_logs(self, authenticated_client, sms_log_factory):
        """Test the API endpoint for retrieving SMS logs."""
        # Create some test logs
        for i in range(5):
            sms_log_factory(
                recipient_number=f"0912345678{i}",
                message=f"Test message {i}"
            )
        
        # Make the API request
        url = reverse('sms_api:get_logs')
        response = authenticated_client.get(url)
        
        # Check response
        assert response.status_code == 200
        assert len(response.data) == 5
        
        # Check that the logs are ordered by sent_at (newest first)
        assert response.data[0]['message'] == "Test message 4"
    
    @pytest.mark.django_db
    def test_queue_sms(self, authenticated_client, customer):
        """Test the API endpoint for queuing SMS."""
        # Define test data
        data = {
            'recipient_number': '09123456789',
            'message': 'This is a test SMS to be queued',
            'notification_type': 'custom',
            'customer_id': customer.id
        }
        
        # Make the API request
        url = reverse('sms_api:queue_sms')
        response = authenticated_client.post(url, data, format='json')
        
        # Check response
        assert response.status_code == 201
        assert response.data['status'] == 'success'
        
        # Check that an SmsQueue item was created
        assert SmsQueue.objects.filter(recipient_number='09123456789').exists()
        queue_item = SmsQueue.objects.get(recipient_number='09123456789')
        assert queue_item.message == 'This is a test SMS to be queued'
        assert queue_item.notification_type == 'custom'
        assert queue_item.status == 'pending'
    
    @pytest.mark.django_db
    @patch('sms_api.apis.process_sms_queue')
    def test_process_queue_api(self, mock_process_queue, authenticated_client, sms_queue_factory):
        """Test the API endpoint for processing the SMS queue."""
        # Create some queued messages
        for i in range(3):
            sms_queue_factory(
                recipient_number=f"0912345678{i}",
                message=f"Test queued message {i}"
            )
        
        # Configure the mock to return a successful response
        mock_process_queue.return_value = {'processed': 3, 'success': 3, 'failed': 0}
        
        # Make the API request
        url = reverse('sms_api:process_queue')
        response = authenticated_client.post(url)
        
        # Check response
        assert response.status_code == 200
        assert response.data['status'] == 'success'
        assert response.data['processed'] == 3
        assert mock_process_queue.called 