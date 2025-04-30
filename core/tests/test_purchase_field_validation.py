import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from core.PurchaseModel import Purchase, PurchaseStateChange
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from decimal import Decimal
from django.contrib.auth.models import User


@pytest.mark.unit
class TestPurchaseFieldValidation:
    """Test class for Purchase model field validations."""
    
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
    def cargo_product_factory(self, db):
        def create_cargo_product(product_type="soybean_meal", price_per_kg=Decimal('15.00'), **kwargs):
            return CargoProduct.objects.create(
                product_type=product_type,
                price_per_kg=price_per_kg,
                **kwargs
            )
        return create_cargo_product
    
    @pytest.fixture
    def customer_factory(self, db):
        def create_customer(name="Test Customer", **kwargs):
            return Customer.objects.create(
                name=name,
                **kwargs
            )
        return create_customer
    
    @pytest.fixture
    def purchase_factory(self, db, customer_factory, cargo_product_factory):
        def create_purchase(
            state="INITIATED",
            order_weight=1000,
            delivered_weight=None,
            amount_paid=Decimal('10000000.00'),
            **kwargs
        ):
            customer = kwargs.pop('customer', customer_factory())
            cargo_product = kwargs.pop('cargo_product', cargo_product_factory())
            
            return Purchase.objects.create(
                customer=customer,
                cargo_product=cargo_product,
                order_weight=order_weight,
                delivered_weight=delivered_weight,
                amount_paid=amount_paid,
                state=state,
                **kwargs
            )
        return create_purchase
    
    def test_negative_order_weight(self, customer_factory, cargo_product_factory):
        """Test that negative order weight is not allowed."""
        customer = customer_factory()
        cargo_product = cargo_product_factory()
        
        with pytest.raises(ValidationError) as excinfo:
            purchase = Purchase(
                customer=customer,
                cargo_product=cargo_product,
                order_weight=-100,  # Negative weight
                amount_paid=Decimal('10000000.00'),
                state="INITIATED"
            )
            purchase.full_clean()
        
        # Check if the error message contains the expected text
        assert "order_weight" in str(excinfo.value)
        assert "negative" in str(excinfo.value).lower()
    
    def test_zero_order_weight(self, customer_factory, cargo_product_factory):
        """Test that zero order weight is not allowed."""
        customer = customer_factory()
        cargo_product = cargo_product_factory()
        
        with pytest.raises(ValidationError) as excinfo:
            purchase = Purchase(
                customer=customer,
                cargo_product=cargo_product,
                order_weight=0,  # Zero weight
                amount_paid=Decimal('10000000.00'),
                state="INITIATED"
            )
            purchase.full_clean()
        
        # Check if the error message contains the expected text
        assert "order_weight" in str(excinfo.value)
        assert "zero" in str(excinfo.value).lower() or "greater than" in str(excinfo.value).lower()
    
    def test_negative_delivered_weight(self, purchase_factory):
        """Test that negative delivered weight is not allowed."""
        purchase = purchase_factory(state="DELIVERED")
        
        # Try setting a negative delivered weight
        purchase.delivered_weight = -100
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.full_clean()
        
        # Check if the error message contains the expected text
        assert "delivered_weight" in str(excinfo.value)
        assert "negative" in str(excinfo.value).lower()
    
    def test_zero_delivered_weight(self, purchase_factory):
        """Test that zero delivered weight is not allowed for delivered state."""
        purchase = purchase_factory(state="DELIVERED")
        
        # Try setting a zero delivered weight
        purchase.delivered_weight = 0
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.full_clean()
        
        # Check if the error message contains the expected text
        assert "delivered_weight" in str(excinfo.value)
        assert "zero" in str(excinfo.value).lower() or "greater than" in str(excinfo.value).lower()
    
    def test_negative_amount_paid(self, customer_factory, cargo_product_factory):
        """Test that negative amount paid is not allowed."""
        customer = customer_factory()
        cargo_product = cargo_product_factory()
        
        with pytest.raises(ValidationError) as excinfo:
            purchase = Purchase(
                customer=customer,
                cargo_product=cargo_product,
                order_weight=1000,
                amount_paid=Decimal('-100.00'),  # Negative amount
                state="INITIATED"
            )
            purchase.full_clean()
        
        # Check if the error message contains the expected text
        assert "amount_paid" in str(excinfo.value)
        assert "negative" in str(excinfo.value).lower()
    
    def test_invalid_state(self, purchase_factory):
        """Test that invalid state is not allowed."""
        purchase = purchase_factory()
        
        # Try setting an invalid state
        purchase.state = "INVALID_STATE"
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.full_clean()
        
        # Check if the error message contains the expected text
        assert "state" in str(excinfo.value)
        assert "valid choice" in str(excinfo.value).lower()
    
    def test_barnameh_format(self, purchase_factory):
        """Test validation of barnameh format."""
        purchase = purchase_factory(state="DELIVERED")
        
        # Set an invalid barnameh format (assuming a specific format is required)
        purchase.barnameh = "invalid format"
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_barnameh()
        
        # Check if the error message contains the expected text
        assert "barnameh" in str(excinfo.value).lower()
        assert "format" in str(excinfo.value).lower()
        
        # Set a valid barnameh format
        purchase.barnameh = "BN12345"
        purchase.clean_barnameh()  # Should not raise
    
    def test_mandatory_fields_for_initiated(self, customer_factory, cargo_product_factory):
        """Test that all mandatory fields for INITIATED state are validated."""
        customer = customer_factory()
        cargo_product = cargo_product_factory()
        
        # Create a purchase with missing mandatory fields
        with pytest.raises(ValidationError) as excinfo:
            purchase = Purchase(
                customer=customer,
                # Missing cargo_product
                order_weight=1000,
                amount_paid=Decimal('10000000.00'),
                state="INITIATED"
            )
            purchase.full_clean()
        
        assert "cargo_product" in str(excinfo.value)
        
        # Create a purchase with missing order_weight
        with pytest.raises(ValidationError) as excinfo:
            purchase = Purchase(
                customer=customer,
                cargo_product=cargo_product,
                # Missing order_weight
                amount_paid=Decimal('10000000.00'),
                state="INITIATED"
            )
            purchase.full_clean()
        
        assert "order_weight" in str(excinfo.value)
    
    def test_delivered_weight_required_for_delivered(self, purchase_factory):
        """Test that delivered_weight is required when state is DELIVERED."""
        purchase = purchase_factory()
        
        # Change state to DELIVERED but don't set delivered_weight
        purchase.state = "DELIVERED"
        purchase.delivered_weight = None
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_fields()
            purchase.clean()
        
        assert "delivered_weight" in str(excinfo.value)
    
    def test_barnameh_required_for_delivered(self, purchase_factory):
        """Test that barnameh is required when state is DELIVERED."""
        purchase = purchase_factory()
        
        # Change state to DELIVERED but don't set barnameh
        purchase.state = "DELIVERED"
        purchase.delivered_weight = 1000  # Set delivered weight
        purchase.barnameh = None  # No barnameh
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_fields()
            purchase.clean()
        
        assert "barnameh" in str(excinfo.value)
    
    def test_amount_paid_greater_than_total(self, purchase_factory, cargo_product_factory):
        """Test validation that amount_paid should not be greater than calculated total."""
        cargo_product = cargo_product_factory(price_per_kg=Decimal('10.00'))
        purchase = purchase_factory(
            cargo_product=cargo_product,
            order_weight=1000,  # Total: 10.00 * 1000 = 10,000.00
            amount_paid=Decimal('15000.00')  # More than total
        )
        
        # This should raise if the model checks if amount_paid > total
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_amount()
        
        assert "amount_paid" in str(excinfo.value)
        assert "exceeds" in str(excinfo.value).lower()
    
    def test_completion_date_in_past(self, purchase_factory):
        """Test that completion_date cannot be set in the future."""
        purchase = purchase_factory()
        
        # Set completion date in the future
        future_date = timezone.now() + timedelta(days=10)
        purchase.completion_date = future_date
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_completion_date()
        
        assert "completion_date" in str(excinfo.value)
        assert "future" in str(excinfo.value).lower()
    
    def test_valid_purchase_creates_successfully(self, customer_factory, cargo_product_factory):
        """Test that a valid purchase object can be created successfully."""
        customer = customer_factory()
        cargo_product = cargo_product_factory()
        
        # Create a purchase with all valid fields
        purchase = Purchase(
            customer=customer,
            cargo_product=cargo_product,
            order_weight=1000,
            amount_paid=Decimal('10000.00'),
            state="INITIATED"
        )
        
        # Should not raise any exceptions
        purchase.full_clean()
        purchase.save()
        
        # Verify the purchase was saved
        assert purchase.id is not None
        assert Purchase.objects.filter(id=purchase.id).exists()
    
    def test_max_length_validation(self, purchase_factory):
        """Test validation of max length for text fields."""
        purchase = purchase_factory()
        
        # Test with very long barnameh
        very_long_text = "x" * 256  # Assuming max_length is 255 or less
        purchase.barnameh = very_long_text
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.full_clean()
        
        assert "barnameh" in str(excinfo.value)
        assert "length" in str(excinfo.value).lower()
    
    def test_date_ordering_validation(self, purchase_factory):
        """Test that dates follow a logical chronological order."""
        purchase = purchase_factory()
        
        # Set dates out of order
        now = timezone.now()
        past = now - timedelta(days=10)
        
        purchase.creation_date = now
        purchase.sales_approval_date = past  # Should be after creation_date
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_date_ordering()
        
        assert "date" in str(excinfo.value).lower()
        assert "order" in str(excinfo.value).lower()
    
    def test_decimal_precision(self, purchase_factory):
        """Test validation of decimal precision for money fields."""
        purchase = purchase_factory()
        
        # Set amount_paid with too many decimal places
        purchase.amount_paid = Decimal('100.123456')
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_decimal_precision()
        
        assert "amount_paid" in str(excinfo.value)
        assert "decimal" in str(excinfo.value).lower()
    
    def test_vendor_settlement_validation(self, purchase_factory):
        """Test validation for vendor settlement data."""
        purchase = purchase_factory(state="FINANCIAL_APPROVED")
        
        # Change to VENDOR_SETTLED without setting settlement data
        purchase.state = "VENDOR_SETTLED"
        
        with pytest.raises(ValidationError) as excinfo:
            purchase.clean_vendor_settlement()
        
        assert "vendor" in str(excinfo.value).lower()
        assert "settlement" in str(excinfo.value).lower()
        
        # Set settlement data and try again
        purchase.vendor_settlement_date = timezone.now()
        purchase.vendor_settlement_reference = "VS12345"
        
        # Should not raise exception
        purchase.clean_vendor_settlement() 