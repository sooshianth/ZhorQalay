import pytest
from django.contrib.auth.models import User
from core.SalesAgentModel import SalesAgent
from core.CustomerModel import Customer, PhoneNumber, ActivityField, ProductPreference, PaymentPreference
from core.CargoProductModel import CargoProduct
from django.utils import timezone


@pytest.fixture
def user_factory(db):
    def create_user(username="testuser", password="password123", email="test@example.com", **kwargs):
        return User.objects.create_user(
            username=username, 
            password=password, 
            email=email, 
            **kwargs
        )
    return create_user


@pytest.fixture
def sales_agent_factory(db, user_factory):
    def create_sales_agent(name="Test Agent", phone_number="9123456789", factor_code="TA", target_monthly_sales=10000.0, user=None, **kwargs):
        if user is None:
            user = user_factory()
        
        return SalesAgent.objects.create(
            user=user,
            name=name,
            phone_number=phone_number,
            factor_code=factor_code,
            target_monthly_sales=target_monthly_sales,
            **kwargs
        )
    return create_sales_agent


@pytest.fixture
def activity_field_factory(db):
    def create_activity_field(code='chicken'):
        return ActivityField.objects.create(code=code)
    return create_activity_field


@pytest.fixture
def product_preference_factory(db):
    def create_product_preference(code='soybean_meal'):
        return ProductPreference.objects.create(code=code)
    return create_product_preference


@pytest.fixture
def payment_preference_factory(db):
    def create_payment_preference(code='cash'):
        return PaymentPreference.objects.create(code=code)
    return create_payment_preference


@pytest.fixture
def customer_factory(db, sales_agent_factory):
    def create_customer(name="Test Customer", city="Tehran", whatsapp_preference=True, sms_preference=True, **kwargs):
        customer = Customer.objects.create(
            name=name,
            city=city,
            whatsapp_preference=whatsapp_preference,
            sms_preference=sms_preference,
            **kwargs
        )
        
        # Add default sales agent if not provided
        if 'sales_agent' not in kwargs and not customer.sales_agent.exists():
            sales_agent = sales_agent_factory()
            customer.sales_agent.add(sales_agent)
        
        return customer
    return create_customer


@pytest.fixture
def phone_number_factory(db, customer_factory):
    def create_phone_number(number="9123456789", is_primary=True, customer=None):
        if customer is None:
            customer = customer_factory()
        
        return PhoneNumber.objects.create(
            number=number,
            is_primary=is_primary,
            customer=customer
        )
    return create_phone_number


@pytest.fixture
def cargo_product_factory(db):
    def create_cargo_product(product_type='soybean_meal', vendor_weight=1000, purchaser_weight=1000, **kwargs):
        return CargoProduct.objects.create(
            product_type=product_type,
            vendor_weight=vendor_weight,
            purchaser_weight=purchaser_weight,
            **kwargs
        )
    return create_cargo_product 