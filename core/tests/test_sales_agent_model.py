import pytest
from django.utils import timezone
from datetime import timedelta
from core.SalesAgentModel import SalesAgent
from core.CustomerModel import Customer
from core.PurchaseModel import Purchase
from unittest.mock import patch
from django.core.cache import cache


@pytest.mark.unit
class TestSalesAgent:
    def test_sales_agent_creation(self, sales_agent_factory):
        """Test basic sales agent creation."""
        agent = sales_agent_factory(
            name="Test Agent",
            phone_number="9123456789",
            factor_code="TA",
            target_monthly_sales=10000.0
        )
        
        assert agent.name == "Test Agent"
        assert agent.phone_number == "9123456789"
        assert agent.factor_code == "TA"
        assert agent.target_monthly_sales == 10000.0
    
    def test_get_all_customers(self, sales_agent_factory, customer_factory):
        """Test retrieving all customers for a sales agent."""
        agent = sales_agent_factory()
        
        # Create customers and assign to agent
        customer1 = customer_factory(name="Customer 1")
        customer2 = customer_factory(name="Customer 2")
        customer3 = customer_factory(name="Customer 3")
        
        customer1.sales_agent.add(agent)
        customer2.sales_agent.add(agent)
        customer3.sales_agent.add(agent)
        
        customers = agent.get_all_customers()
        
        assert customers.count() == 3
        assert customer1 in customers
        assert customer2 in customers
        assert customer3 in customers
    
    # Mock Purchase model for testing
    @pytest.fixture
    def mock_purchase(self, monkeypatch):
        class MockPurchase:
            def __init__(self, customer, state, created_at, amount_paid=1000, order_weight=1000):
                self.customer = customer
                self.state = state
                self.created_at = created_at
                self.amount_paid = amount_paid
                self.order_weight = order_weight
            
            def __str__(self):
                return f"Purchase for {self.customer.name} ({self.state})"
        
        return MockPurchase
    
    def test_get_sales_in_period(self, sales_agent_factory, customer_factory, mock_purchase, monkeypatch):
        """Test retrieving sales in a specific time period."""
        agent = sales_agent_factory()
        customer = customer_factory()
        customer.sales_agent.add(agent)
        
        now = timezone.now()
        
        # Create mock purchases with various states and dates
        purchases = [
            mock_purchase(customer, "PAYMENT_VERIFIED", now - timedelta(days=5), 1000, 1000),
            mock_purchase(customer, "DELIVERED", now - timedelta(days=10), 2000, 2000),
            mock_purchase(customer, "INITIATED", now - timedelta(days=2), 500, 500),  # Unpaid
            mock_purchase(customer, "ARCHIVED", now - timedelta(days=15), 3000, 3000),  # Archived
        ]
        
        # Patch customer's purchases_made.filter to return our mocked purchases
        def mock_filter(filters):
            results = []
            for purchase in purchases:
                # Simplified filter logic for testing
                if "state__in" in str(filters) and purchase.state in str(filters):
                    if "ARCHIVED" in str(filters) and purchase.state == "ARCHIVED":
                        results.append(purchase)
                    elif "~Q(state='ARCHIVED')" in str(filters) and purchase.state != "ARCHIVED":
                        results.append(purchase)
                    
                # Check date filter
                if "created_at__gte" in str(filters) and "created_at__lte" in str(filters):
                    start_date = now - timedelta(days=20)  # Approximate for test
                    end_date = now
                    if start_date <= purchase.created_at <= end_date:
                        if purchase not in results:
                            results.append(purchase)
            
            return results
        
        monkeypatch.setattr(customer.purchases_made, "filter", mock_filter)
        
        # Test getting paid, non-archived sales
        paid_sales = agent.get_sales_in_period(
            start_date=now - timedelta(days=20), 
            end_date=now, 
            paid_only=True, 
            archived=False
        )
        
        assert len(paid_sales) == 2
        assert any(p.state == "PAYMENT_VERIFIED" for p in paid_sales)
        assert any(p.state == "DELIVERED" for p in paid_sales)
        
        # Test getting all sales including unpaid
        all_sales = agent.get_sales_in_period(
            start_date=now - timedelta(days=20), 
            end_date=now, 
            paid_only=False, 
            archived=False
        )
        
        assert len(all_sales) == 3  # Includes INITIATED
        
        # Test getting archived sales
        archived_sales = agent.get_sales_in_period(
            start_date=now - timedelta(days=20), 
            end_date=now, 
            paid_only=True, 
            archived=True
        )
        
        assert len(archived_sales) == 1
        assert archived_sales[0].state == "ARCHIVED"
    
    def test_get_this_month_sales(self, sales_agent_factory, monkeypatch):
        """Test retrieving sales for the current month."""
        agent = sales_agent_factory()
        
        # Mock the get_sales_in_period method
        def mock_get_sales_in_period(start_date=None, end_date=None, paid_only=True, archived=False):
            return ["sale1", "sale2", "sale3"]
        
        monkeypatch.setattr(agent, "get_sales_in_period", mock_get_sales_in_period)
        
        sales = agent.get_this_month_sales()
        assert len(sales) == 3
    
    def test_get_this_month_sales_stats(self, sales_agent_factory, monkeypatch):
        """Test retrieving sales statistics for the current month with caching."""
        agent = sales_agent_factory(target_monthly_sales=10000.0)
        
        # Clear cache first
        cache.clear()
        
        # Mock the get_this_month_sales method
        class MockSale:
            def __init__(self, amount, weight):
                self.amount_paid = amount
                self.order_weight = weight
        
        sales = [
            MockSale(1000, 1000),
            MockSale(2000, 2000),
            MockSale(3000, 3000)
        ]
        
        monkeypatch.setattr(agent, "get_this_month_sales", lambda: sales)
        
        # Get stats
        stats = agent.get_this_month_sales_stats()
        
        assert stats["amount"] == 6000
        assert stats["weight"] == 6.0  # 6000/1000 converted to tons
        assert stats["count"] == 3
        assert stats["average"] == 2000
        assert stats["target_achievement"] == 60.0  # 6000/10000*100
        
        # Check that stats are cached
        # Modify the mock to return different values
        new_sales = [
            MockSale(5000, 5000),
            MockSale(5000, 5000)
        ]
        monkeypatch.setattr(agent, "get_this_month_sales", lambda: new_sales)
        
        # If cached, should return the original stats
        cached_stats = agent.get_this_month_sales_stats()
        assert cached_stats["amount"] == 6000
        
        # Clear cache and check for new values
        cache.clear()
        new_stats = agent.get_this_month_sales_stats()
        assert new_stats["amount"] == 10000
    
    def test_get_potential_sales(self, sales_agent_factory, customer_factory, mock_purchase, monkeypatch):
        """Test retrieving potential sales (unpaid)."""
        agent = sales_agent_factory()
        customer = customer_factory()
        customer.sales_agent.add(agent)
        
        now = timezone.now()
        
        # Create mock purchases with various states
        purchases = [
            mock_purchase(customer, "INITIATED", now - timedelta(days=2)),
            mock_purchase(customer, "SMS_SENT", now - timedelta(days=3)),
            mock_purchase(customer, "PAYMENT_VERIFIED", now - timedelta(days=5)),  # Paid
        ]
        
        # Patch customer's purchases_made.filter
        def mock_filter(filters):
            results = []
            for purchase in purchases:
                if purchase.state in ["INITIATED", "SMS_SENT", "BAZAARGAH_CONFIRMED"]:
                    if "created_at__gte" in str(filters) and "created_at__lte" in str(filters):
                        results.append(purchase)
            return results
        
        monkeypatch.setattr(customer.purchases_made, "filter", mock_filter)
        
        potential_sales = agent.get_potential_sales()
        assert len(potential_sales) == 2
        assert all(p.state in ["INITIATED", "SMS_SENT"] for p in potential_sales)


@pytest.mark.unit
class TestPhoneAssignment:
    # Tests for the PhoneAssignment model would go here
    pass 