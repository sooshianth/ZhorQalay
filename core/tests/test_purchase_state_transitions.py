import pytest
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from core.PurchaseModel import Purchase, PurchaseStateChange
from core.CustomerModel import Customer
from core.CargoProductModel import CargoProduct
from decimal import Decimal
from unittest.mock import patch


@pytest.mark.unit
class TestPurchaseStateTransitions:
    """Test class for Purchase model state transitions and state change history."""
    
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
    def purchase_factory(self, db, customer_factory, cargo_product_factory, user_factory):
        def create_purchase(
            state="INITIATED",
            order_weight=1000,
            delivered_weight=None,
            amount_paid=Decimal('10000000.00'),
            **kwargs
        ):
            customer = kwargs.pop('customer', customer_factory())
            cargo_product = kwargs.pop('cargo_product', cargo_product_factory())
            created_by = kwargs.pop('created_by', user_factory())
            
            return Purchase.objects.create(
                customer=customer,
                cargo_product=cargo_product,
                order_weight=order_weight,
                delivered_weight=delivered_weight,
                amount_paid=amount_paid,
                state=state,
                created_by=created_by,
                **kwargs
            )
        return create_purchase
    
    def test_initial_state(self, purchase_factory):
        """Test that purchase is correctly created with initial state."""
        purchase = purchase_factory(state="INITIATED")
        
        assert purchase.state == "INITIATED"
        # Check if initial state is recorded in state change history
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase)
        assert state_changes.count() == 1
        assert state_changes.first().from_state is None
        assert state_changes.first().to_state == "INITIATED"
    
    def test_valid_state_transition(self, purchase_factory, user_factory):
        """Test valid state transition from INITIATED to SALES_APPROVED."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Mock save method to avoid database operations
        with patch.object(Purchase, 'save'):
            # Transition to SALES_APPROVED
            purchase.transition_to_state("SALES_APPROVED", approver)
        
        # Check the state was changed
        assert purchase.state == "SALES_APPROVED"
        
        # Check that a state change record was created
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase)
        assert state_changes.count() == 2  # Initial state + transition
        
        latest_change = state_changes.order_by('-timestamp').first()
        assert latest_change.from_state == "INITIATED"
        assert latest_change.to_state == "SALES_APPROVED"
        assert latest_change.changed_by == approver
    
    def test_invalid_state_transition(self, purchase_factory, user_factory):
        """Test invalid state transition rejection."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Try an invalid transition (e.g., INITIATED -> DELIVERED, skipping steps)
        with pytest.raises(ValueError) as excinfo:
            purchase.transition_to_state("DELIVERED", approver)
        
        # Check that the state was not changed
        assert purchase.state == "INITIATED"
        assert "Invalid state transition" in str(excinfo.value)
        
        # Check that no new state change record was created
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase)
        assert state_changes.count() == 1  # Only the initial state
    
    def test_full_state_transition_sequence(self, purchase_factory, user_factory):
        """Test a complete sequence of valid state transitions."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        expected_states = [
            "INITIATED",
            "SALES_APPROVED",
            "TRANSPORT_ASSIGNED",
            "DELIVERED",
            "DIFFERENCE_APPROVED",
            "FINANCIAL_APPROVED",
            "VENDOR_SETTLED",
            "COMPLETED"
        ]
        
        current_state = "INITIATED"
        
        # Perform all transitions in sequence
        for next_state in expected_states[1:]:
            # Set required fields for specific transitions
            if next_state == "DELIVERED":
                purchase.delivered_weight = 990  # Slightly less than ordered
                purchase.barnameh = "BN12345"
            
            if next_state == "VENDOR_SETTLED":
                purchase.vendor_settlement_date = timezone.now()
                purchase.vendor_settlement_reference = "VS12345"
            
            # Mock save method to avoid database operations for most transitions
            # but actually save for some to ensure database consistency
            if next_state in ["DELIVERED", "VENDOR_SETTLED"]:
                purchase.transition_to_state(next_state, approver)
            else:
                with patch.object(Purchase, 'save'):
                    purchase.transition_to_state(next_state, approver)
            
            # Check that state was updated correctly
            assert purchase.state == next_state
            
            # Update current state for next iteration
            current_state = next_state
        
        # Check that all state changes were recorded
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase)
        assert state_changes.count() == len(expected_states)
        
        # Check that states were transitioned in the expected order
        state_change_sequence = list(state_changes.order_by('timestamp').values_list('to_state', flat=True))
        assert state_change_sequence == expected_states
    
    def test_state_transition_with_reason(self, purchase_factory, user_factory):
        """Test state transition with specified reason."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        reason = "Approved after verification"
        
        # Transition with reason
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("SALES_APPROVED", approver, reason=reason)
        
        # Check if reason was recorded
        latest_change = PurchaseStateChange.objects.filter(purchase=purchase).order_by('-timestamp').first()
        assert latest_change.reason == reason
    
    def test_direct_state_assignment_creates_history(self, purchase_factory, user_factory):
        """Test that direct state assignment also creates state change history."""
        purchase = purchase_factory(state="INITIATED")
        
        # Directly assign a new state
        purchase.state = "SALES_APPROVED"
        purchase.save()
        
        # Check if a state change was recorded
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('-timestamp')
        assert state_changes.count() == 2  # Initial state + direct change
        
        latest_change = state_changes.first()
        assert latest_change.from_state == "INITIATED"
        assert latest_change.to_state == "SALES_APPROVED"
    
    def test_duplicate_transition_rejected(self, purchase_factory, user_factory):
        """Test rejection of transition to the same state."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Try to transition to the same state
        with pytest.raises(ValueError) as excinfo:
            purchase.transition_to_state("INITIATED", approver)
        
        assert "already in state" in str(excinfo.value).lower()
        
        # Check that no new state change record was created
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase)
        assert state_changes.count() == 1  # Only the initial state
    
    def test_transition_sets_timestamp_fields(self, purchase_factory, user_factory):
        """Test that transitioning to specific states sets appropriate timestamp fields."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Transition to SALES_APPROVED
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("SALES_APPROVED", approver)
        
        # Check that sales_approval_date was set
        assert purchase.sales_approval_date is not None
        
        # Transition to DELIVERED
        purchase.delivered_weight = 990
        purchase.barnameh = "BN12345"
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("DELIVERED", approver)
        
        # Check that delivery_date was set
        assert purchase.delivery_date is not None
        
        # Transition to COMPLETED
        with patch.object(Purchase, 'save'):
            # Transition through intermediate states
            for state in ["DIFFERENCE_APPROVED", "FINANCIAL_APPROVED"]:
                purchase.transition_to_state(state, approver)
            
            # Add required fields for VENDOR_SETTLED
            purchase.vendor_settlement_date = timezone.now()
            purchase.vendor_settlement_reference = "VS12345"
            purchase.transition_to_state("VENDOR_SETTLED", approver)
            
            # Finally transition to COMPLETED
            purchase.transition_to_state("COMPLETED", approver)
        
        # Check that completion_date was set
        assert purchase.completion_date is not None
    
    def test_state_change_user_tracking(self, purchase_factory, user_factory):
        """Test that user who made state changes is correctly tracked."""
        purchase = purchase_factory(state="INITIATED")
        first_approver = user_factory(username="first_approver")
        second_approver = user_factory(username="second_approver")
        
        # First transition by first_approver
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("SALES_APPROVED", first_approver)
        
        # Second transition by second_approver
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("TRANSPORT_ASSIGNED", second_approver)
        
        # Check that changes were attributed to the correct users
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('timestamp')
        assert state_changes.count() == 3  # Initial + 2 transitions
        
        # Check the first transition (ignoring initial state)
        first_transition = state_changes[1]
        assert first_transition.from_state == "INITIATED"
        assert first_transition.to_state == "SALES_APPROVED"
        assert first_transition.changed_by == first_approver
        
        # Check the second transition
        second_transition = state_changes[2]
        assert second_transition.from_state == "SALES_APPROVED"
        assert second_transition.to_state == "TRANSPORT_ASSIGNED"
        assert second_transition.changed_by == second_approver
    
    def test_state_change_rejection_with_validation(self, purchase_factory, user_factory):
        """Test state change rejection due to validation failure."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Try to transition to DELIVERED without setting delivered_weight
        purchase.delivered_weight = None
        purchase.barnameh = "BN12345"
        
        with pytest.raises(ValueError) as excinfo:
            purchase.transition_to_state("DELIVERED", approver)
        
        assert "validation" in str(excinfo.value).lower()
        
        # State should remain unchanged
        assert purchase.state == "INITIATED"
        
        # Now set the required field and try again
        purchase.delivered_weight = 990
        
        # Now it should work
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("SALES_APPROVED", approver)
            purchase.transition_to_state("TRANSPORT_ASSIGNED", approver)
            purchase.transition_to_state("DELIVERED", approver)
        
        assert purchase.state == "DELIVERED"
    
    def test_custom_rule_based_transition_validation(self, purchase_factory, user_factory):
        """Test custom business rules validation during state transitions."""
        purchase = purchase_factory(state="DELIVERED", delivered_weight=900, order_weight=1000)
        approver = user_factory(username="approver")
        
        # Assume there's a business rule: can't approve if weight difference is too large
        # Let's say more than 10% difference requires special handling
        # Calculate percentage difference
        difference_percentage = abs(purchase.delivered_weight - purchase.order_weight) / purchase.order_weight * 100
        
        # Mock the transition validation method to check this rule
        original_validate = Purchase.validate_transition
        
        def mock_validate(self, to_state, user):
            # Add custom business logic
            if to_state == "DIFFERENCE_APPROVED" and difference_percentage > 10:
                raise ValueError("Weight difference too large (>10%) for automatic approval")
            return original_validate(self, to_state, user)
        
        # Apply the mock
        with patch.object(Purchase, 'validate_transition', new=mock_validate):
            # This should raise an exception due to our 10% rule
            with pytest.raises(ValueError) as excinfo:
                purchase.transition_to_state("DIFFERENCE_APPROVED", approver)
            
            assert "weight difference" in str(excinfo.value).lower()
        
        # State should remain unchanged
        assert purchase.state == "DELIVERED"
    
    def test_state_transition_timestamps_order(self, purchase_factory, user_factory):
        """Test that state change timestamps maintain proper chronological order."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Make several transitions in sequence
        states = ["SALES_APPROVED", "TRANSPORT_ASSIGNED", "DELIVERED"]
        
        # For DELIVERED state, we need additional fields
        purchase.delivered_weight = 990
        purchase.barnameh = "BN12345"
        
        # Perform the transitions
        for state in states:
            with patch.object(Purchase, 'save'):
                purchase.transition_to_state(state, approver)
        
        # Get all the state changes ordered by timestamp
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('timestamp')
        
        # Check that the timestamps are in increasing order
        timestamps = [change.timestamp for change in state_changes]
        assert timestamps == sorted(timestamps)
        
        # Check that the sequence of states matches our transitions
        state_sequence = ["INITIATED"] + states  # Add initial state
        recorded_states = [change.to_state for change in state_changes]
        assert recorded_states == state_sequence
    
    def test_rollback_state_transition(self, purchase_factory, user_factory):
        """Test ability to rollback to a previous state when needed."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # First transition to a new state
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("SALES_APPROVED", approver)
        
        assert purchase.state == "SALES_APPROVED"
        
        # Now rollback to the previous state
        with patch.object(Purchase, 'save'):
            purchase.transition_to_state("INITIATED", approver, reason="Rollback due to error")
        
        assert purchase.state == "INITIATED"
        
        # Check that both transitions are recorded
        state_changes = PurchaseStateChange.objects.filter(purchase=purchase).order_by('timestamp')
        assert state_changes.count() == 3  # Initial + forward + rollback
        
        # Check the rollback reason
        rollback = state_changes.last()
        assert rollback.from_state == "SALES_APPROVED"
        assert rollback.to_state == "INITIATED"
        assert "rollback" in rollback.reason.lower()
    
    def test_state_change_query_methods(self, purchase_factory, user_factory):
        """Test helper methods to query state change history."""
        purchase = purchase_factory(state="INITIATED")
        approver = user_factory(username="approver")
        
        # Make multiple transitions
        states = ["SALES_APPROVED", "TRANSPORT_ASSIGNED"]
        for state in states:
            with patch.object(Purchase, 'save'):
                purchase.transition_to_state(state, approver)
        
        # Test helper method to get last state change
        last_change = purchase.get_last_state_change()
        assert last_change.from_state == "SALES_APPROVED"
        assert last_change.to_state == "TRANSPORT_ASSIGNED"
        
        # Test helper method to check if purchase was ever in a state
        assert purchase.was_ever_in_state("SALES_APPROVED") is True
        assert purchase.was_ever_in_state("DELIVERED") is False
        
        # Test helper to get all changes by a specific user
        user_changes = purchase.get_state_changes_by_user(approver)
        assert user_changes.count() == 2  # Both transitions but not the initial state
        
        # Test helper to get transition timestamp for specific state
        sales_approved_time = purchase.get_state_transition_timestamp("SALES_APPROVED")
        assert sales_approved_time is not None
        
        never_reached_time = purchase.get_state_transition_timestamp("DELIVERED")
        assert never_reached_time is None 