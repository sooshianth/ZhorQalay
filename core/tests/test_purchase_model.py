import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from core.PurchaseModel import Purchase, PurchaseStateChange, ShenaseTakhsis, PurchaseReceipts
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User


@pytest.mark.unit
class TestPurchaseModel:
    @pytest.fixture
    def user_factory(self, db):
        def create_user(username="testuser", password="password123", email="test@example.com", is_staff=True, **kwargs):
            user = User.objects.create_user(
                username=username, 
                password=password, 
                email=email, 
                is_staff=is_staff,
                **kwargs
            )
            return user
        return create_user
        
    @pytest.fixture
    def customer_factory(self, db):
        def create_customer(name="Test Customer", phone_number="9123456789", **kwargs):
            return Customer.objects.create(
                name=name,
                phone_number=phone_number,
                **kwargs
            )
        return create_customer
    
    @pytest.fixture
    def cargo_product_factory(self, db):
        def create_cargo_product(
            product_type="soybean_meal",
            vendor_weight=1000,
            purchaser_weight=1000,
            price_per_kg=10000,
            **kwargs
        ):
            return CargoProduct.objects.create(
                product_type=product_type,
                vendor_weight=vendor_weight,
                purchaser_weight=purchaser_weight,
                price_per_kg=price_per_kg,
                **kwargs
            )
        return create_cargo_product
    
    @pytest.fixture
    def purchase_factory(self, db, customer_factory, cargo_product_factory):
        def create_purchase(
            customer=None,
            amount_paid=Decimal('10000000.00'),
            cargo_product=None,
            order_weight=1000,
            state="INITIATED",
            **kwargs
        ):
            if customer is None:
                customer = customer_factory()
                
            if cargo_product is None:
                cargo_product = cargo_product_factory()
            
            return Purchase.objects.create(
                customer=customer,
                amount_paid=amount_paid,
                cargo_product=cargo_product,
                order_weight=order_weight,
                state=state,
                **kwargs
            )
        return create_purchase
    
    def test_purchase_creation(self, purchase_factory, customer_factory, cargo_product_factory):
        """Test basic Purchase creation."""
        customer = customer_factory(name="Test Customer")
        cargo = cargo_product_factory(product_type="soybean_meal", price_per_kg=10000)
        
        purchase = purchase_factory(
            customer=customer,
            cargo_product=cargo,
            amount_paid=Decimal('10000000.00'),
            order_weight=1000,
            state="INITIATED"
        )
        
        assert purchase.customer == customer
        assert purchase.cargo_product == cargo
        assert purchase.amount_paid == Decimal('10000000.00')
        assert purchase.order_weight == 1000
        assert purchase.state == "INITIATED"
        assert purchase.created_at is not None
        
        # Check defaults
        assert purchase.is_urgent is False
        assert purchase.is_canceled is False
        assert purchase.is_archived is False
        assert purchase.priority == 'low'
        assert purchase.type == 'bazaargah'
    
    def test_purchase_generate_invoice_id(self, purchase_factory):
        """Test invoice_id generation on save."""
        purchase = purchase_factory()
        
        # Check that invoice_id is generated
        assert purchase.invoice_id is not None
        assert purchase.invoice_id.startswith('KQ')
        
        # Test uniqueness by checking pattern
        purchase2 = purchase_factory()
        assert purchase.invoice_id != purchase2.invoice_id
    
    def test_purchase_state_transitions(self, purchase_factory):
        """Test Purchase state transitions."""
        purchase = purchase_factory(state="INITIATED")
        
        # Test valid state transitions
        purchase.state = "SMS_SENT"
        purchase.save()
        assert purchase.state == "SMS_SENT"
        
        purchase.state = "PAYMENT_VERIFIED"
        purchase.save()
        assert purchase.state == "PAYMENT_VERIFIED"
        
        # Try to jump to an invalid state
        with pytest.raises(ValidationError):
            purchase.state = "COMPLETED"
            purchase.clean()
    
    def test_purchase_calculate_total(self, purchase_factory, cargo_product_factory):
        """Test calculation of total purchase amount based on weight and price."""
        cargo = cargo_product_factory(price_per_kg=5000)
        purchase = purchase_factory(
            cargo_product=cargo,
            order_weight=2000,  # 2000 kg
            amount_paid=0  # Will be calculated
        )
        
        # Calculate total
        calculated_total = purchase.calculate_total()
        
        # Expected: 2000 kg * 5000 per kg = 10,000,000
        assert calculated_total == Decimal('10000000.00')
        
        # Test with a different weight
        purchase.order_weight = 3000
        calculated_total = purchase.calculate_total()
        assert calculated_total == Decimal('15000000.00')
    
    def test_purchase_get_payment_status(self, purchase_factory):
        """Test getting payment status based on state."""
        # Test paid states
        paid_states = ["PAYMENT_VERIFIED", "ALLOCATION_REGISTERED", "COMPLETED"]
        for state in paid_states:
            purchase = purchase_factory(state=state)
            assert purchase.get_payment_status() == "پرداخت شده"
        
        # Test unpaid states
        unpaid_states = ["INITIATED", "SMS_SENT"]
        for state in unpaid_states:
            purchase = purchase_factory(state=state)
            assert purchase.get_payment_status() == "پرداخت نشده"
    
    def test_purchase_is_delayed(self, purchase_factory):
        """Test checking if a purchase is delayed."""
        # Create a purchase with a creation date 3 days ago
        three_days_ago = timezone.now() - timedelta(days=3)
        purchase = purchase_factory(state="INITIATED")
        
        # Patch the created_at to simulate an old purchase
        purchase.created_at = three_days_ago
        purchase.save()
        
        # Should be delayed since it's in INITIATED state for 3 days
        assert purchase.is_delayed() is True
        
        # Test with a non-delayable state
        purchase.state = "COMPLETED"
        purchase.save()
        assert purchase.is_delayed() is False
        
        # Test with a recent purchase
        recent_purchase = purchase_factory(state="INITIATED")
        assert recent_purchase.is_delayed() is False
    
    def test_purchase_get_delay_days(self, purchase_factory):
        """Test calculating the number of delay days."""
        # Create a purchase with a creation date 5 days ago
        five_days_ago = timezone.now() - timedelta(days=5)
        purchase = purchase_factory(state="INITIATED")
        purchase.created_at = five_days_ago
        purchase.save()
        
        # Should return 5 days of delay
        assert purchase.get_delay_days() == 5
        
        # Test with a completed purchase (should return 0)
        purchase.state = "COMPLETED"
        purchase.save()
        assert purchase.get_delay_days() == 0
        
    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_change_state_method(self, mock_send_notification, purchase_factory, user_factory):
        """Test the change_state method for state transitions."""
        purchase = purchase_factory(state="INITIATED")
        user = user_factory()
        
        # Change state and check result
        purchase.change_state("SMS_SENT", user, "Test state change")
        
        # Assert state was changed
        assert purchase.state == "SMS_SENT"
        
        # Assert that a state change record was created
        state_change = PurchaseStateChange.objects.filter(purchase=purchase).first()
        assert state_change is not None
        assert state_change.previous_state == "INITIATED"
        assert state_change.new_state == "SMS_SENT"
        assert state_change.changed_by == user
        assert state_change.notes == "Test state change"
        
        # Assert notification was sent
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_confirm_bazaargah(self, mock_send_notification, purchase_factory, user_factory):
        """Test the confirm_bazaargah workflow method."""
        purchase = purchase_factory(state="INITIATED")
        user = user_factory()
        
        # Execute the method
        purchase.confirm_bazaargah(user)
        
        # Verify state change
        assert purchase.state == "BAZAARGAH_CONFIRMED"
        
        # Verify notification
        mock_send_notification.assert_called_once()
        
        # Check that state change was recorded
        assert PurchaseStateChange.objects.filter(
            purchase=purchase,
            previous_state="INITIATED",
            new_state="BAZAARGAH_CONFIRMED"
        ).exists()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_verify_payment(self, mock_send_notification, purchase_factory, user_factory):
        """Test the verify_payment workflow method."""
        purchase = purchase_factory(state="SMS_SENT")
        user = user_factory()
        
        # Execute the method
        purchase.verify_payment(user)
        
        # Verify state change
        assert purchase.state == "PAYMENT_VERIFIED"
        
        # Verify notification
        mock_send_notification.assert_called_once()
        
        # Check that state change was recorded
        assert PurchaseStateChange.objects.filter(
            purchase=purchase,
            previous_state="SMS_SENT",
            new_state="PAYMENT_VERIFIED"
        ).exists()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_register_allocation(self, mock_send_notification, purchase_factory, user_factory):
        """Test the register_allocation workflow method."""
        purchase = purchase_factory(state="PAYMENT_VERIFIED")
        user = user_factory()
        
        # Set up allocation codes
        allocation_codes = ["ALLOC123", "ALLOC456"]
        
        # Execute the method
        purchase.register_allocation(user)
        purchase.shenase_takhsis = ",".join(allocation_codes)
        purchase.save()
        
        # Verify state change
        assert purchase.state == "ALLOCATION_REGISTERED"
        
        # Verify takhsis records
        for code in allocation_codes:
            assert ShenaseTakhsis.objects.filter(purchase=purchase, code=code).exists()
            
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_approve_allocation(self, mock_send_notification, purchase_factory, user_factory):
        """Test the approve_allocation workflow method."""
        purchase = purchase_factory(state="ALLOCATION_REGISTERED")
        user = user_factory()
        
        # Execute the method
        purchase.approve_allocation(user)
        
        # Verify state change
        assert purchase.state == "ALLOCATION_APPROVED"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_settle_with_vendor(self, mock_send_notification, purchase_factory, user_factory):
        """Test the settle_with_vendor workflow method."""
        purchase = purchase_factory(state="ALLOCATION_APPROVED")
        user = user_factory()
        
        # Execute the method
        purchase.settle_with_vendor(user)
        
        # Verify state change
        assert purchase.state == "VENDOR_SETTLED"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_send_address_to_vendor(self, mock_send_notification, purchase_factory, user_factory):
        """Test the send_address_to_vendor workflow method."""
        purchase = purchase_factory(state="VENDOR_SETTLED", address="Test Address")
        user = user_factory()
        
        # Execute the method
        purchase.send_address_to_vendor(user)
        
        # Verify state change
        assert purchase.state == "ADDRESS_SENT"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_send_to_shipping(self, mock_send_notification, purchase_factory, user_factory):
        """Test the send_to_shipping workflow method."""
        purchase = purchase_factory(state="ADDRESS_SENT")
        user = user_factory()
        
        # Execute the method
        purchase.send_to_shipping(user)
        
        # Verify state change
        assert purchase.state == "SENT_TO_SHIPPING"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_issue_barnameh(self, mock_send_notification, purchase_factory, user_factory):
        """Test the issue_barnameh workflow method."""
        purchase = purchase_factory(state="SENT_TO_SHIPPING")
        user = user_factory()
        
        # Execute the method with barnameh number
        barnameh_number = "BN12345"
        purchase.issue_barnameh(user)
        purchase.barnameh = barnameh_number
        purchase.save()
        
        # Verify state change
        assert purchase.state == "BARNAMEH_ISSUED"
        assert purchase.barnameh == barnameh_number
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_mark_as_delivered(self, mock_send_notification, purchase_factory, user_factory):
        """Test the mark_as_delivered workflow method."""
        purchase = purchase_factory(state="BARNAMEH_ISSUED", order_weight=1000)
        user = user_factory()
        
        # Execute the method with delivery details
        delivered_weight = 950  # Less than order weight to test difference
        purchase.mark_as_delivered(user)
        purchase.delivered_weight = delivered_weight
        purchase.save()
        
        # Verify state change
        assert purchase.state == "DELIVERED"
        assert purchase.delivered_weight == delivered_weight
        
        # Verify difference is calculated
        weight_diff = purchase.order_weight - purchase.delivered_weight
        assert weight_diff == 50
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_approve_difference_shortage(self, mock_send_notification, purchase_factory, user_factory):
        """Test the approve_difference workflow method with shortage."""
        # Create purchase with shortage
        purchase = purchase_factory(
            state="DELIVERED", 
            order_weight=1000,
            delivered_weight=950,
            amount_paid=Decimal('10000000.00'),
            extelaf_type=None
        )
        user = user_factory()
        
        # Execute the method
        purchase.approve_difference(user)
        purchase.extelaf_type = "کسری"
        purchase.extelaf_weight = 50
        purchase.extelaf_amount = 500000
        purchase.save()
        
        # Verify state change
        assert purchase.state == "DIFFERENCE_APPROVED"
        assert purchase.extelaf_type == "کسری"
        assert purchase.extelaf_weight == 50
        assert purchase.extelaf_amount == 500000
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_approve_difference_surplus(self, mock_send_notification, purchase_factory, user_factory):
        """Test the approve_difference workflow method with surplus."""
        # Create purchase with surplus
        purchase = purchase_factory(
            state="DELIVERED", 
            order_weight=1000,
            delivered_weight=1050,
            amount_paid=Decimal('10000000.00'),
            extelaf_type=None
        )
        user = user_factory()
        
        # Execute the method
        purchase.approve_difference(user)
        purchase.extelaf_type = "سرک"
        purchase.extelaf_weight = 50
        purchase.extelaf_amount = 500000
        purchase.save()
        
        # Verify state change
        assert purchase.state == "DIFFERENCE_APPROVED"
        assert purchase.extelaf_type == "سرک"
        assert purchase.extelaf_weight == 50
        assert purchase.extelaf_amount == 500000
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_deposit_difference(self, mock_send_notification, purchase_factory, user_factory):
        """Test the deposit_difference workflow method."""
        purchase = purchase_factory(
            state="DIFFERENCE_APPROVED",
            extelaf_type="کسری"
        )
        user = user_factory()
        
        # Execute the method
        purchase.deposit_difference(user)
        
        # Verify state change
        assert purchase.state == "SHORTAGE_DEPOSITED"
        
        # Test with surplus type
        purchase2 = purchase_factory(
            state="DIFFERENCE_APPROVED",
            extelaf_type="سرک"
        )
        
        purchase2.deposit_difference(user)
        assert purchase2.state == "SURPLUS_DEPOSITED"
        
        # Verify notification
        mock_send_notification.assert_called()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_submit_receipt(self, mock_send_notification, purchase_factory, user_factory):
        """Test the submit_receipt workflow method."""
        purchase = purchase_factory(state="SHORTAGE_DEPOSITED")
        user = user_factory()
        
        # Execute the method
        purchase.submit_receipt(user)
        
        # Verify state change
        assert purchase.state == "RECEIPT_SUBMITTED"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_issue_invoice(self, mock_send_notification, purchase_factory, user_factory):
        """Test the issue_invoice workflow method."""
        purchase = purchase_factory(state="RECEIPT_SUBMITTED")
        user = user_factory()
        
        # Execute the method
        purchase.issue_invoice(user)
        
        # Verify state change
        assert purchase.state == "INVOICE_ISSUED"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_approval_workflow(self, mock_send_notification, purchase_factory, user_factory):
        """Test the complete approval workflow: sales → logistics → financial → completed."""
        purchase = purchase_factory(state="INVOICE_ISSUED")
        user = user_factory()
        
        # Step 1: Sales approval
        purchase.approve_by_sales(user)
        assert purchase.state == "SALES_APPROVED"
        
        # Step 2: Logistics approval
        purchase.approve_by_logistics(user)
        assert purchase.state == "LOGISTICS_APPROVED"
        
        # Step 3: Financial approval
        purchase.approve_by_financial(user)
        assert purchase.state == "FINANCIAL_APPROVED"
        
        # After all approvals, should become COMPLETED
        assert purchase.state == "FINANCIAL_APPROVED"
        
        # Check that the approvals were recorded and notifications sent
        mock_send_notification.assert_called()
        assert mock_send_notification.call_count == 3

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_mark_as_urgent(self, mock_send_notification, purchase_factory, user_factory):
        """Test the mark_as_urgent workflow method."""
        purchase = purchase_factory(state="ALLOCATION_REGISTERED", is_urgent=False)
        user = user_factory()
        
        # Execute the method
        purchase.mark_as_urgent(user)
        
        # Verify flagging
        assert purchase.is_urgent is True
        assert purchase.priority == "high"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_cancel_purchase(self, mock_send_notification, purchase_factory, user_factory):
        """Test the cancel_purchase workflow method."""
        purchase = purchase_factory(state="ALLOCATION_REGISTERED", is_canceled=False)
        user = user_factory()
        
        # Execute the method
        purchase.cancel_purchase(user)
        
        # Verify flagging
        assert purchase.is_canceled is True
        assert purchase.state == "CANCELED"
        
        # Verify notification
        mock_send_notification.assert_called_once()

    @patch('core.PurchaseModel.Purchase.send_notification')
    def test_archive_purchase(self, mock_send_notification, purchase_factory, user_factory):
        """Test the archive_purchase workflow method."""
        purchase = purchase_factory(state="COMPLETED", is_archived=False)
        user = user_factory()
        
        # Execute the method
        purchase.archive_purchase(user)
        
        # Verify flagging
        assert purchase.is_archived is True
        assert purchase.state == "ARCHIVED"
        
        # Verify notification
        mock_send_notification.assert_called_once()
        
    @patch('core.PurchaseModel.Purchase.notify_relevant_users')
    def test_send_notification(self, mock_notify, purchase_factory, user_factory):
        """Test the send_notification method."""
        purchase = purchase_factory()
        user = user_factory()
        
        # Call the method
        purchase.send_notification(
            user=user, 
            title="Test Notification", 
            message="This is a test notification",
            notification_type="purchase",
            priority="high"
        )
        
        # Verify the notification was created
        mock_notify.assert_called_once_with(
            message="This is a test notification",
            title="Test Notification",
            notification_type="purchase",
            priority="high"
        )
        
    def test_purchase_receipts(self, purchase_factory, user_factory):
        """Test adding receipts to a purchase."""
        purchase = purchase_factory()
        user = user_factory()
        
        # Create a receipt
        receipt = PurchaseReceipts.objects.create(
            purchase=purchase,
            user=user,
            reciept_type="bazaargah_receipt"
        )
        
        # Verify the receipt was created and linked to the purchase
        assert receipt in purchase.receipts.all()
        assert receipt.purchase == purchase
        assert receipt.user == user
        assert receipt.reciept_type == "bazaargah_receipt"
        assert receipt.created_at is not None


@pytest.mark.unit
class TestPurchaseReceipts:
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
    def purchase_factory(self, db, customer_factory, cargo_product_factory):
        def create_purchase(**kwargs):
            customer = Customer.objects.create(name="Test Customer")
            cargo = CargoProduct.objects.create(product_type="soybean_meal")
            return Purchase.objects.create(
                customer=customer,
                cargo_product=cargo,
                amount_paid=Decimal('10000000.00'),
                order_weight=1000,
                state="INITIATED",
                **kwargs
            )
        return create_purchase
        
    @pytest.fixture
    def customer_factory(self, db):
        def create_customer(**kwargs):
            return Customer.objects.create(name="Test Customer", **kwargs)
        return create_customer
        
    @pytest.fixture
    def cargo_product_factory(self, db):
        def create_cargo_product(**kwargs):
            return CargoProduct.objects.create(product_type="soybean_meal", **kwargs)
        return create_cargo_product
    
    def test_receipt_creation(self, purchase_factory, user_factory):
        """Test creating different types of receipts."""
        purchase = purchase_factory()
        user = user_factory()
        
        receipt_types = [
            "bazaargah_receipt",
            "non_bazaargah_receipt",
            "deliver",
            "extelaf_receipt",
            "invoice"
        ]
        
        for receipt_type in receipt_types:
            receipt = PurchaseReceipts.objects.create(
                purchase=purchase,
                user=user,
                reciept_type=receipt_type
            )
            
            assert receipt.purchase == purchase
            assert receipt.user == user
            assert receipt.reciept_type == receipt_type
            
    def test_receipt_upload_path(self, purchase_factory, user_factory):
        """Test the receipt_upload_path function."""
        purchase = purchase_factory()
        user = user_factory()
        
        receipt = PurchaseReceipts.objects.create(
            purchase=purchase,
            user=user,
            reciept_type="invoice"
        )
        
        # Test the upload path generation
        upload_path = PurchaseReceipts.receipt_upload_path(receipt, "test_file.pdf")
        expected_path = f"purchase_receipts/purchase_{purchase.id}/test_file.pdf"
        
        assert upload_path == expected_path 