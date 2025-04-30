import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from core.PurchaseModel import Purchase, PurchaseStateChange
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from core.PurchaseModel import ShenaseTakhsis
from core.PurchaseModel import PurchaseReceipts
from decimal import Decimal
from django.contrib.auth.models import User


@pytest.mark.unit
class TestPurchaseBusinessLogic:
    """Test class for Purchase model business logic."""
    
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
    
    def test_invoice_id_generation(self, purchase_factory):
        """Test that invoice IDs are generated correctly."""
        purchase = purchase_factory()
        
        # Invoice ID should be auto-generated
        assert purchase.invoice_id is not None
        assert len(purchase.invoice_id) > 0
        
        # Each purchase should have a unique invoice ID
        purchase2 = purchase_factory()
        assert purchase.invoice_id != purchase2.invoice_id
    
    def test_total_calculation_order_weight(self, purchase_factory, cargo_product_factory):
        """Test total calculation based on order weight and price."""
        # Create with specific price and weight
        cargo_product = cargo_product_factory(price_per_kg=Decimal('20.00'))
        purchase = purchase_factory(
            cargo_product=cargo_product,
            order_weight=500,  # 500 kg
            delivered_weight=None  # Not delivered yet
        )
        
        # Calculate expected total: 500 kg * 20.00 per kg = 10,000.00
        expected_total = Decimal('10000.00')
        
        # Call the calculate_total method
        total = purchase.calculate_total()
        
        # Assert that the calculated total matches the expected value
        assert total == expected_total
    
    def test_total_calculation_delivered_weight(self, purchase_factory, cargo_product_factory):
        """Test total calculation based on delivered weight when available."""
        # Create with specific price and weights
        cargo_product = cargo_product_factory(price_per_kg=Decimal('20.00'))
        purchase = purchase_factory(
            cargo_product=cargo_product,
            order_weight=500,      # 500 kg ordered
            delivered_weight=480,  # 480 kg delivered
            state="DELIVERED"
        )
        
        # Calculate expected total: 480 kg * 20.00 per kg = 9,600.00
        expected_total = Decimal('9600.00')
        
        # Call the calculate_total method
        total = purchase.calculate_total()
        
        # Assert that the calculated total uses delivered weight instead of order weight
        assert total == expected_total
    
    def test_payment_status_determination(self, purchase_factory):
        """Test that payment status is correctly determined based on state."""
        # States that should be considered paid
        paid_states = ["PAYMENT_VERIFIED", "ALLOCATION_REGISTERED", "ALLOCATION_APPROVED", 
                       "VENDOR_SETTLED", "COMPLETED"]
        
        # States that should be considered unpaid
        unpaid_states = ["INITIATED", "SMS_SENT", "BAZAARGAH_CONFIRMED", "CANCELED"]
        
        # Test paid states
        for state in paid_states:
            purchase = purchase_factory(state=state)
            assert purchase.get_payment_status() == "پرداخت شده"
        
        # Test unpaid states
        for state in unpaid_states:
            purchase = purchase_factory(state=state)
            assert purchase.get_payment_status() == "پرداخت نشده"
    
    def test_weight_difference_calculation(self, purchase_factory):
        """Test calculation of weight differences between ordered and delivered."""
        # Test shortage case
        purchase = purchase_factory(
            order_weight=1000,
            delivered_weight=950
        )
        
        # Calculate the difference
        diff_type, diff_weight = purchase.calculate_weight_difference()
        
        # Assert shortage was detected correctly
        assert diff_type == "کسری"
        assert diff_weight == 50
        
        # Test surplus case
        purchase = purchase_factory(
            order_weight=1000,
            delivered_weight=1050
        )
        
        # Calculate the difference
        diff_type, diff_weight = purchase.calculate_weight_difference()
        
        # Assert surplus was detected correctly
        assert diff_type == "اضافه"
        assert diff_weight == 50
        
        # Test no difference case
        purchase = purchase_factory(
            order_weight=1000,
            delivered_weight=1000
        )
        
        # Calculate the difference
        diff_type, diff_weight = purchase.calculate_weight_difference()
        
        # Assert no difference was detected
        assert diff_type is None
        assert diff_weight == 0
    
    def test_difference_approval_process(self, purchase_factory, user_factory):
        """Test the approval process for weight differences."""
        user = user_factory()
        
        # Create a purchase with a shortage
        purchase = purchase_factory(
            state="DELIVERED",
            order_weight=1000,
            delivered_weight=950,
            barnameh="BN12345"
        )
        
        # Approve the difference
        with patch.object(Purchase, 'save') as mock_save:
            purchase.approve_difference(
                extelaf_type="کسری",
                extelaf_weight=50,
                extelaf_amount=Decimal('500000.00'),
                approved_by=user
            )
            mock_save.assert_called()
        
        # Verify the state and difference fields
        assert purchase.state == "DIFFERENCE_APPROVED"
        assert purchase.extelaf_type == "کسری"
        assert purchase.extelaf_weight == 50
        assert purchase.extelaf_amount == Decimal('500000.00')
    
    def test_purchase_deposit_shortage(self, purchase_factory, user_factory):
        """Test the deposit shortage process."""
        user = user_factory()
        
        # Create a purchase with approved shortage
        purchase = purchase_factory(
            state="DIFFERENCE_APPROVED",
            order_weight=1000,
            delivered_weight=950,
            extelaf_type="کسری",
            extelaf_weight=50,
            extelaf_amount=Decimal('500000.00')
        )
        
        # Process shortage deposit
        with patch.object(Purchase, 'save') as mock_save:
            purchase.deposit_shortage(
                deposit_reference="DEP123",
                deposited_by=user
            )
            mock_save.assert_called()
        
        # Verify the state and deposit fields
        assert purchase.state == "SHORTAGE_DEPOSITED"
        assert purchase.shortage_deposit_reference == "DEP123"
    
    def test_purchase_deposit_surplus(self, purchase_factory, user_factory):
        """Test the deposit surplus process."""
        user = user_factory()
        
        # Create a purchase with approved surplus
        purchase = purchase_factory(
            state="DIFFERENCE_APPROVED",
            order_weight=1000,
            delivered_weight=1050,
            extelaf_type="اضافه",
            extelaf_weight=50,
            extelaf_amount=Decimal('500000.00')
        )
        
        # Process surplus deposit
        with patch.object(Purchase, 'save') as mock_save:
            purchase.deposit_surplus(
                deposit_reference="DEP456",
                deposited_by=user
            )
            mock_save.assert_called()
        
        # Verify the state and deposit fields
        assert purchase.state == "SURPLUS_DEPOSITED"
        assert purchase.surplus_deposit_reference == "DEP456"
    
    def test_full_purchase_approval_workflow(self, purchase_factory, user_factory):
        """Test the full approval workflow for a purchase."""
        user = user_factory()
        
        # Create a purchase with all prerequisites met
        purchase = purchase_factory(
            state="INVOICE_ISSUED",
            order_weight=1000,
            delivered_weight=1000,
            amount_paid=Decimal('15000000.00'),
            barnameh="BN12345"
        )
        
        # Approve by sales
        with patch.object(Purchase, 'save') as mock_save:
            purchase.approve_by_sales(approved_by=user)
            mock_save.assert_called()
        
        assert purchase.state == "SALES_APPROVED"
        assert purchase.sales_approval_date is not None
        
        # Approve by logistics
        with patch.object(Purchase, 'save') as mock_save:
            purchase.approve_by_logistics(approved_by=user)
            mock_save.assert_called()
        
        assert purchase.state == "LOGISTICS_APPROVED"
        assert purchase.logistics_approval_date is not None
        
        # Approve by finance
        with patch.object(Purchase, 'save') as mock_save:
            purchase.approve_by_finance(approved_by=user)
            mock_save.assert_called()
        
        assert purchase.state == "FINANCIAL_APPROVED"
        assert purchase.finance_approval_date is not None
        
        # Complete the purchase
        with patch.object(Purchase, 'save') as mock_save:
            purchase.complete(completed_by=user)
            mock_save.assert_called()
        
        assert purchase.state == "COMPLETED"
        assert purchase.completion_date is not None
    
    def test_receipt_submission(self, purchase_factory, user_factory):
        """Test submitting receipts for a purchase."""
        user = user_factory()
        
        # Create a purchase ready for receipt submission
        purchase = purchase_factory(
            state="SHORTAGE_DEPOSITED",
            order_weight=1000,
            delivered_weight=950,
            extelaf_type="کسری",
            extelaf_weight=50,
            extelaf_amount=Decimal('500000.00'),
            shortage_deposit_reference="DEP123"
        )
        
        # Submit receipt
        with patch.object(Purchase, 'save') as mock_save:
            with patch.object(PurchaseReceipts.objects, 'create') as mock_receipt_create:
                purchase.submit_receipt(
                    receipt_type="payment",
                    receipt_number="RCT123",
                    submitted_by=user
                )
                mock_save.assert_called()
                mock_receipt_create.assert_called_once()
        
        assert purchase.state == "RECEIPT_SUBMITTED"
    
    def test_allocation_registration(self, purchase_factory, user_factory):
        """Test registering allocation for a purchase."""
        user = user_factory()
        
        # Create a purchase ready for allocation
        purchase = purchase_factory(
            state="PAYMENT_VERIFIED"
        )
        
        # Register allocation
        with patch.object(Purchase, 'save') as mock_save:
            with patch.object(ShenaseTakhsis.objects, 'create') as mock_allocation_create:
                purchase.register_allocation(
                    allocation_number="ALT123",
                    allocation_date=timezone.now(),
                    registered_by=user
                )
                mock_save.assert_called()
                mock_allocation_create.assert_called_once()
        
        assert purchase.state == "ALLOCATION_REGISTERED"
        assert purchase.allocation_number == "ALT123"
    
    def test_delay_calculation(self, purchase_factory):
        """Test delay calculation for purchases."""
        # Create a purchase that is 10 days old
        ten_days_ago = timezone.now() - timedelta(days=10)
        purchase = purchase_factory(
            state="PAYMENT_VERIFIED",
            creation_date=ten_days_ago
        )
        
        # Test is_delayed
        assert purchase.is_delayed() is True
        
        # Test get_delay_days
        assert purchase.get_delay_days() == 10
        
        # Test a completed purchase (should not be delayed)
        purchase.state = "COMPLETED"
        assert purchase.is_delayed() is False
        
        # Test a recent purchase (should not be delayed)
        today = timezone.now()
        purchase = purchase_factory(
            state="PAYMENT_VERIFIED",
            creation_date=today
        )
        assert purchase.is_delayed() is False
        assert purchase.get_delay_days() == 0 