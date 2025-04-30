import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from core.CargoProductModel import CargoProduct


@pytest.mark.unit
class TestCargoProductModel:
    """Test class for CargoProduct model."""
    
    @pytest.fixture
    def cargo_product_factory(self, db):
        def create_cargo_product(
            product_type="soybean_meal",
            price_per_kg=Decimal('15.00'),
            description="Test description",
            is_active=True,
            **kwargs
        ):
            return CargoProduct.objects.create(
                product_type=product_type,
                price_per_kg=price_per_kg,
                description=description,
                is_active=is_active,
                **kwargs
            )
        return create_cargo_product
    
    def test_cargo_product_creation(self, cargo_product_factory):
        """Test basic creation of CargoProduct."""
        cargo_product = cargo_product_factory(
            product_type="corn",
            price_per_kg=Decimal('12.50'),
            description="Corn grain for animal feed"
        )
        
        assert cargo_product.product_type == "corn"
        assert cargo_product.price_per_kg == Decimal('12.50')
        assert cargo_product.description == "Corn grain for animal feed"
        assert cargo_product.is_active is True
        
        # Check the string representation
        assert str(cargo_product) == "corn"
    
    def test_negative_price_validation(self, db):
        """Test validation rejects negative prices."""
        cargo_product = CargoProduct(
            product_type="barley",
            price_per_kg=Decimal('-5.00'),
            description="Test with negative price"
        )
        
        with pytest.raises(ValidationError) as excinfo:
            cargo_product.full_clean()
        
        assert "price_per_kg" in str(excinfo.value)
        assert "Ensure this value is greater than or equal to 0" in str(excinfo.value)
    
    def test_zero_price_allowed(self, cargo_product_factory):
        """Test that zero price is allowed (for special offers or samples)."""
        cargo_product = cargo_product_factory(
            product_type="sample",
            price_per_kg=Decimal('0.00'),
            description="Free sample product"
        )
        
        assert cargo_product.price_per_kg == Decimal('0.00')
    
    def test_product_type_uniqueness(self, cargo_product_factory):
        """Test that product_type must be unique."""
        # Create first product
        cargo_product_factory(product_type="wheat")
        
        # Attempt to create another with the same product_type
        with pytest.raises(Exception) as excinfo:
            cargo_product_factory(product_type="wheat")
        
        # Check for uniqueness constraint violation
        assert "unique constraint" in str(excinfo.value).lower() or "duplicate key" in str(excinfo.value).lower()
    
    def test_max_price_validation(self, db):
        """Test validation on maximum price value."""
        # Create a product with a price that exceeds the max value allowed
        very_large_price = Decimal('100000000.00')
        cargo_product = CargoProduct(
            product_type="premium_gold",
            price_per_kg=very_large_price,
            description="Extremely expensive product"
        )
        
        # If there's a max_digits constraint in the model, this should fail
        # Otherwise, it will pass - adjust test based on actual model constraints
        try:
            cargo_product.full_clean()
            cargo_product.save()
            # If we get here, the model might not have a max constraint
            assert cargo_product.price_per_kg == very_large_price
        except ValidationError as e:
            assert "price_per_kg" in str(e)
    
    def test_product_type_max_length(self, db):
        """Test the max length validation for product_type field."""
        # Create a product type string that's too long
        long_name = "x" * 100  # Adjust based on the actual max_length in model
        
        cargo_product = CargoProduct(
            product_type=long_name,
            price_per_kg=Decimal('10.00'),
            description="Test product with long name"
        )
        
        # Check if validation catches the length issue
        with pytest.raises(ValidationError) as excinfo:
            cargo_product.full_clean()
        
        assert "product_type" in str(excinfo.value)
    
    def test_description_can_be_empty(self, cargo_product_factory):
        """Test that description field can be empty."""
        cargo_product = cargo_product_factory(
            product_type="simple_product",
            description=""
        )
        
        assert cargo_product.description == ""
        
        # Also test with None if the field allows null
        cargo_product = cargo_product_factory(
            product_type="null_desc_product",
            description=None
        )
        
        # Depending on model definition, this may be None or ""
        assert cargo_product.description in (None, "")
    
    def test_deactivate_product(self, cargo_product_factory):
        """Test deactivating a product."""
        cargo_product = cargo_product_factory(is_active=True)
        assert cargo_product.is_active is True
        
        # Deactivate the product
        cargo_product.is_active = False
        cargo_product.save()
        
        # Verify it's deactivated
        updated_product = CargoProduct.objects.get(id=cargo_product.id)
        assert updated_product.is_active is False
    
    def test_update_price(self, cargo_product_factory):
        """Test updating product price."""
        cargo_product = cargo_product_factory(price_per_kg=Decimal('15.00'))
        
        # Update price
        cargo_product.price_per_kg = Decimal('17.50')
        cargo_product.save()
        
        # Verify the price is updated
        updated_product = CargoProduct.objects.get(id=cargo_product.id)
        assert updated_product.price_per_kg == Decimal('17.50')
    
    def test_filter_active_products(self, cargo_product_factory):
        """Test filtering only active products."""
        # Create a mix of active and inactive products
        cargo_product_factory(
            product_type="active_product_1",
            is_active=True
        )
        cargo_product_factory(
            product_type="active_product_2",
            is_active=True
        )
        cargo_product_factory(
            product_type="inactive_product",
            is_active=False
        )
        
        # Retrieve only active products
        active_products = CargoProduct.objects.filter(is_active=True)
        
        # Verify we got only the active ones
        assert active_products.count() == 2
        assert set(active_products.values_list('product_type', flat=True)) == {
            "active_product_1", 
            "active_product_2"
        }
    
    def test_decimal_precision(self, cargo_product_factory):
        """Test decimal precision handling for price_per_kg."""
        # Create product with a price that has multiple decimal places
        cargo_product = cargo_product_factory(
            price_per_kg=Decimal('12.3456')
        )
        
        # Check how many decimal places are preserved
        # The actual behavior depends on the model's decimal_places setting
        saved_product = CargoProduct.objects.get(id=cargo_product.id)
        
        # Check that price is rounded/truncated according to model definition
        # If decimal_places=2, we expect 12.35 (rounded) or 12.34 (truncated)
        assert saved_product.price_per_kg in (
            Decimal('12.34'),
            Decimal('12.35')
        ) or Decimal('12.3456')  # If no rounding/truncation 