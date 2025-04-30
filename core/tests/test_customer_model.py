import pytest
from django.core.exceptions import ValidationError
from core.CustomerModel import Customer, PhoneNumber, ActivityField, ProductPreference, PaymentPreference
from django.utils import timezone


@pytest.mark.unit
class TestPhoneNumber:
    def test_phone_number_creation(self, phone_number_factory, customer_factory):
        """Test the basic creation of a phone number."""
        customer = customer_factory()
        phone = phone_number_factory(number="9123456789", customer=customer)
        
        assert phone.number == "9123456789"
        assert phone.is_primary is True
        assert phone.customer == customer
    
    def test_persian_digits_conversion(self, db, customer_factory):
        """Test that Persian digits are converted to English digits."""
        customer = customer_factory()
        phone = PhoneNumber(number="۹۱۲۳۴۵۶۷۸۹", is_primary=True, customer=customer)
        phone.save()
        
        assert phone.number == "9123456789"
    
    def test_clean_phone_number(self, db, customer_factory):
        """Test that phone numbers are properly cleaned."""
        customer = customer_factory()
        
        # Test with leading zero and spaces
        phone = PhoneNumber(number="0 912 345 6789", is_primary=True, customer=customer)
        phone.save()
        assert phone.number == "9123456789"
        
        # Test with dashes and parentheses
        phone = PhoneNumber(number="(0912)-345-6789", is_primary=True, customer=customer)
        phone.save()
        assert phone.number == "9123456789"
    
    def test_invalid_phone_number(self, db, customer_factory):
        """Test validation of invalid phone numbers."""
        customer = customer_factory()
        
        # Test with non-9 starting number
        with pytest.raises(ValidationError):
            phone = PhoneNumber(number="8123456789", is_primary=True, customer=customer)
            phone.clean()
        
        # Test with too short number
        with pytest.raises(ValidationError):
            phone = PhoneNumber(number="91234", is_primary=True, customer=customer)
            phone.clean()
        
        # Test with too long number
        with pytest.raises(ValidationError):
            phone = PhoneNumber(number="91234567890", is_primary=True, customer=customer)
            phone.clean()
    
    def test_primary_phone_setting(self, db, customer_factory):
        """Test that only one phone can be primary for a customer."""
        customer = customer_factory()
        
        # Create first primary phone
        phone1 = PhoneNumber(number="9123456789", is_primary=True, customer=customer)
        phone1.save()
        
        # Create second primary phone
        phone2 = PhoneNumber(number="9123456788", is_primary=True, customer=customer)
        phone2.save()
        
        # Refresh from db to get updated values
        phone1.refresh_from_db()
        
        # Check that phone1 is no longer primary
        assert phone1.is_primary is False
        assert phone2.is_primary is True
        
        # Check that customer's phone_number field is updated
        customer.refresh_from_db()
        assert customer.phone_number == "9123456788"


@pytest.mark.unit
class TestCustomerModel:
    def test_customer_creation(self, customer_factory, sales_agent_factory):
        """Test basic customer creation."""
        sales_agent = sales_agent_factory()
        customer = customer_factory(name="Test Customer", city="Tehran")
        customer.sales_agent.add(sales_agent)
        
        assert customer.name == "Test Customer"
        assert customer.city == "Tehran"
        assert customer.whatsapp_preference is True
        assert customer.sms_preference is True
        assert sales_agent in customer.sales_agent.all()
    
    def test_customer_with_phone_numbers(self, customer_factory, phone_number_factory):
        """Test customer with multiple phone numbers."""
        customer = customer_factory()
        
        # Add two phone numbers
        phone1 = phone_number_factory(number="9123456789", is_primary=True, customer=customer)
        phone2 = phone_number_factory(number="9123456788", is_primary=False, customer=customer)
        
        # Test getting primary phone
        assert customer.get_primary_phone() == "9123456789"
        
        # Test getting all phone numbers
        all_phones = customer.get_all_phone_numbers()
        assert "9123456789" in all_phones
        assert "9123456788" in all_phones
    
    def test_get_customer_by_phone(self, customer_factory, phone_number_factory):
        """Test the get_customer_by_phone static method."""
        customer = customer_factory()
        phone = phone_number_factory(number="9123456789", customer=customer)
        
        # Test finding by phone number
        found_customer = Customer.get_customer_by_phone("9123456789")
        assert found_customer == customer
        
        # Test finding with formatting
        found_customer = Customer.get_customer_by_phone("0912-345-6789")
        assert found_customer == customer
        
        # Test finding with Persian digits
        found_customer = Customer.get_customer_by_phone("۹۱۲۳۴۵۶۷۸۹")
        assert found_customer == customer
        
        # Test finding non-existent phone
        found_customer = Customer.get_customer_by_phone("9999999999")
        assert found_customer is None
        
        # Test with None
        found_customer = Customer.get_customer_by_phone(None)
        assert found_customer is None
    
    def test_field_of_activity(self, db, customer_factory, activity_field_factory):
        """Test setting and getting field of activity."""
        customer = customer_factory()
        
        # Create activity fields
        chicken = activity_field_factory(code='chicken')
        livestock = activity_field_factory(code='livestock')
        
        # Test using the property
        customer.field_of_activity_list = ['chicken', 'livestock']
        
        # Check if set correctly
        assert set(customer.field_of_activity_list) == {'chicken', 'livestock'}
        
        # Test the display method
        display = customer.get_field_of_activity_display()
        assert "مرغدار" in display
        assert "دامدار" in display
        
        # Test clearing
        customer.field_of_activity_list = []
        assert customer.field_of_activity_list == []
        assert customer.get_field_of_activity_display() == ""
    
    def test_payment_preferences(self, db, customer_factory, payment_preference_factory):
        """Test setting and getting payment preferences."""
        customer = customer_factory()
        
        # Create payment preferences
        cash = payment_preference_factory(code='cash')
        check = payment_preference_factory(code='check')
        
        # Test using the property
        customer.purchase_preferences_list = ['cash', 'check']
        
        # Check if set correctly
        assert set(customer.purchase_preferences_list) == {'cash', 'check'}
        
        # Test clearing
        customer.purchase_preferences_list = []
        assert customer.purchase_preferences_list == []
    
    def test_product_preferences(self, db, customer_factory, product_preference_factory):
        """Test setting and getting product preferences."""
        customer = customer_factory()
        
        # Create product preferences
        soybean = product_preference_factory(code='soybean_meal')
        corn = product_preference_factory(code='corn')
        
        # Test using the property
        customer.product_preferences_list = ['soybean_meal', 'corn']
        
        # Check if set correctly
        assert set(customer.product_preferences_list) == {'soybean_meal', 'corn'}
        
        # Test clearing
        customer.product_preferences_list = []
        assert customer.product_preferences_list == [] 