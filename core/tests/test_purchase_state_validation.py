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
class TestPurchaseStateValidation:
    """Test class for validating Purchase state transitions."""
    
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
    def purchase_factory(self, db):
        def create_purchase(state="INITIATED", **kwargs):
            customer = Customer.objects.create(name="Test Customer")
            cargo = CargoProduct.objects.create(product_type="soybean_meal")
            
            return Purchase.objects.create(
                customer=customer,
                cargo_product=cargo,
                amount_paid=Decimal('10000000.00'),
                order_weight=1000,
                state=state,
                **kwargs
            )
        return create_purchase
    
    def test_valid_state_transitions(self, purchase_factory):
        """Test all valid state transitions defined in the model."""
        # Define all valid transitions based on business rules
        valid_transitions = [
            ("INITIATED", "SMS_SENT"),
            ("INITIATED", "BAZAARGAH_CONFIRMED"),
            ("SMS_SENT", "PAYMENT_VERIFIED"),
            ("BAZAARGAH_CONFIRMED", "PAYMENT_VERIFIED"),
            ("PAYMENT_VERIFIED", "ALLOCATION_REGISTERED"),
            ("ALLOCATION_REGISTERED", "ALLOCATION_APPROVED"),
            ("ALLOCATION_APPROVED", "VENDOR_SETTLED"),
            ("VENDOR_SETTLED", "ADDRESS_SENT"),
            ("ADDRESS_SENT", "SENT_TO_SHIPPING"),
            ("SENT_TO_SHIPPING", "BARNAMEH_ISSUED"),
            ("BARNAMEH_ISSUED", "DELIVERED"),
            ("DELIVERED", "DIFFERENCE_APPROVED"),
            ("DIFFERENCE_APPROVED", "SHORTAGE_DEPOSITED"),
            ("DIFFERENCE_APPROVED", "SURPLUS_DEPOSITED"),
            ("SHORTAGE_DEPOSITED", "RECEIPT_SUBMITTED"),
            ("SURPLUS_DEPOSITED", "RECEIPT_SUBMITTED"),
            ("RECEIPT_SUBMITTED", "INVOICE_ISSUED"),
            ("INVOICE_ISSUED", "SALES_APPROVED"),
            ("SALES_APPROVED", "LOGISTICS_APPROVED"),
            ("LOGISTICS_APPROVED", "FINANCIAL_APPROVED"),
            ("FINANCIAL_APPROVED", "COMPLETED"),
            # Special states
            ("INITIATED", "CANCELED"),
            ("SMS_SENT", "CANCELED"),
            ("BAZAARGAH_CONFIRMED", "CANCELED"),
            ("PAYMENT_VERIFIED", "CANCELED"),
            ("COMPLETED", "ARCHIVED"),
        ]
        
        # Test each valid transition
        for from_state, to_state in valid_transitions:
            purchase = purchase_factory(state=from_state)
            purchase.state = to_state
            try:
                purchase.clean()  # Should not raise ValidationError
                purchase.save()
                assert purchase.state == to_state
            except ValidationError:
                pytest.fail(f"Validation error raised for valid transition: {from_state} -> {to_state}")
    
    def test_invalid_state_transitions(self, purchase_factory):
        """Test invalid state transitions trigger ValidationError."""
        # Define some invalid transitions
        invalid_transitions = [
            ("INITIATED", "COMPLETED"),
            ("SMS_SENT", "ALLOCATION_REGISTERED"),
            ("PAYMENT_VERIFIED", "BARNAMEH_ISSUED"),
            ("ALLOCATION_REGISTERED", "DELIVERED"),
            ("DELIVERED", "PAYMENT_VERIFIED"),
            ("INVOICE_ISSUED", "DELIVERED"),
            ("COMPLETED", "PAYMENT_VERIFIED"),
            ("CANCELED", "PAYMENT_VERIFIED"),
            ("ARCHIVED", "COMPLETED"),
        ]
        
        # Test each invalid transition
        for from_state, to_state in invalid_transitions:
            purchase = purchase_factory(state=from_state)
            purchase.state = to_state
            with pytest.raises(ValidationError):
                purchase.clean()
    
    def test_jump_multiple_states(self, purchase_factory, user_factory):
        """Test that jumping multiple states requires clean() validation but can be bypassed for admin actions."""
        user = user_factory()
        purchase = purchase_factory(state="INITIATED")
        
        # Try to jump to DELIVERED directly (invalid)
        purchase.state = "DELIVERED"
        with pytest.raises(ValidationError):
            purchase.clean()
        
        # Now try using change_state with bypass_validation
        # This simulates what happens when an admin needs to forcefully change state
        purchase.state = "INITIATED"  # Reset
        
        # This is typically done by setting a bypass_validation flag in a form
        # In the model itself, it would be done via direct save without validation
        purchase.save()  # Save without clean()
        purchase.state = "DELIVERED"  # Invalid jump
        purchase.save(update_fields=['state'])  # Force save without validation
        
        # Verify that the state was changed
        purchase.refresh_from_db()
        assert purchase.state == "DELIVERED"
    
    def test_state_change_recording(self, purchase_factory, user_factory):
        """Test that all state changes are properly recorded in PurchaseStateChange."""
        user = user_factory()
        purchase = purchase_factory(state="INITIATED")
        
        # Perform a series of valid state changes
        transitions = [
            "SMS_SENT",
            "PAYMENT_VERIFIED",
            "ALLOCATION_REGISTERED",
            "ALLOCATION_APPROVED"
        ]
        
        for new_state in transitions:
            # Perform the state change
            previous_state = purchase.state
            purchase.state = new_state
            purchase.clean()  # Validate
            purchase.save()
            
            # Create state change record manually (simulating the change_state method)
            PurchaseStateChange.objects.create(
                purchase=purchase,
                previous_state=previous_state,
                new_state=new_state,
                changed_by=user,
                notes=f"Changed from {previous_state} to {new_state}"
            )
        
        # Verify that all state changes were recorded
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase)
        assert state_changes.count() == len(transitions)
        
        # Check that the state changes are in the correct order
        expected_states = ["INITIATED"] + transitions
        for i, change in enumerate(state_changes.order_by('id')):
            assert change.previous_state == expected_states[i]
            assert change.new_state == expected_states[i+1]
    
    def test_state_flags_consistency(self, purchase_factory):
        """Test that state flags (is_urgent, is_canceled, is_archived) are consistent with state."""
        # Test CANCELED state
        purchase = purchase_factory(state="CANCELED")
        assert purchase.is_canceled is True
        
        # Test ARCHIVED state
        purchase = purchase_factory(state="ARCHIVED")
        assert purchase.is_archived is True
        
        # Test URGENT state (should set priority to high)
        purchase = purchase_factory(state="INITIATED", is_urgent=True)
        assert purchase.priority == "high"
        
        # Test setting the state directly should update the flags
        purchase = purchase_factory(state="INITIATED")
        purchase.state = "CANCELED"
        purchase.save()
        assert purchase.is_canceled is True
        
        purchase = purchase_factory(state="COMPLETED")
        purchase.state = "ARCHIVED"
        purchase.save()
        assert purchase.is_archived is True
    
    def test_required_fields_for_states(self, purchase_factory):
        """Test that certain states require specific fields to be populated."""
        # BARNAMEH_ISSUED requires barnameh number
        purchase = purchase_factory(state="SENT_TO_SHIPPING")
        purchase.state = "BARNAMEH_ISSUED"
        purchase.barnameh = None
        with pytest.raises(ValidationError):
            purchase.clean()
        
        # Fix by providing barnameh number
        purchase.barnameh = "BN12345"
        purchase.clean()  # Should not raise error
        
        # DELIVERED requires delivered_weight
        purchase = purchase_factory(state="BARNAMEH_ISSUED", barnameh="BN12345")
        purchase.state = "DELIVERED"
        purchase.delivered_weight = 0
        with pytest.raises(ValidationError):
            purchase.clean()
        
        # Fix by providing delivered_weight
        purchase.delivered_weight = 1000
        purchase.clean()  # Should not raise error
        
        # DIFFERENCE_APPROVED requires extelaf_type and extelaf_amount
        purchase = purchase_factory(
            state="DELIVERED", 
            barnameh="BN12345", 
            delivered_weight=950,  # Different from order_weight (1000)
            order_weight=1000
        )
        purchase.state = "DIFFERENCE_APPROVED"
        purchase.extelaf_type = None
        purchase.extelaf_amount = None
        with pytest.raises(ValidationError):
            purchase.clean()
        
        # Fix by providing extelaf details
        purchase.extelaf_type = "کسری"
        purchase.extelaf_weight = 50
        purchase.extelaf_amount = 500000
        purchase.clean()  # Should not raise error 