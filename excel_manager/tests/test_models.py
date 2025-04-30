import pytest
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from excel_manager.models import ExcelFile, BGExcelFile, ExcelProcessingLog
from django.utils import timezone
from core.CargoProductModel import CargoProduct
from unittest.mock import patch, MagicMock


@pytest.mark.unit
class TestExcelFile:
    @pytest.fixture
    def user_factory(self, db):
        def create_user(username="testuser", password="password123", email="test@example.com", **kwargs):
            from django.contrib.auth.models import User
            return User.objects.create_user(
                username=username, 
                password=password, 
                email=email, 
                **kwargs
            )
        return create_user
    
    @pytest.fixture
    def excel_file_factory(self, db, user_factory):
        def create_excel_file(
            user=None,
            title="Test Excel File",
            file_type="other",
            description="Test description",
            is_processed=False,
            is_approved=False,
            approved_by=None,
            approved_at=None
        ):
            if user is None:
                user = user_factory()
                
            # Create a simple test file
            file_content = b"test,data\n1,2\n3,4"
            excel_file = SimpleUploadedFile("test_file.xlsx", file_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            return ExcelFile.objects.create(
                user=user,
                title=title,
                file=excel_file,
                file_type=file_type,
                description=description,
                is_processed=is_processed,
                is_approved=is_approved,
                approved_by=approved_by,
                approved_at=approved_at
            )
        return create_excel_file
    
    def test_excel_file_creation(self, excel_file_factory):
        """Test the basic creation of an Excel file."""
        excel = excel_file_factory(
            title="Test Excel",
            file_type="customer",
            description="Test description file"
        )
        
        assert excel.title == "Test Excel"
        assert excel.file_type == "customer"
        assert excel.description == "Test description file"
        assert excel.is_processed is False
        assert excel.is_approved is False
        assert excel.created_at is not None
        assert excel.updated_at is not None
        
        # Clean up the created file
        if os.path.exists(excel.file.path):
            os.remove(excel.file.path)
    
    @patch('os.path.exists')
    @patch('os.rename')
    def test_change_file_name(self, mock_rename, mock_exists, excel_file_factory):
        """Test changing the file name."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Create Excel file
        excel = excel_file_factory(title="Original File")
        
        # Test changing file name
        result = excel.change_file_name("new_file.xlsx")
        
        assert result is True
        mock_rename.assert_called_once()
        assert "new_file.xlsx" in excel.file.name
    
    def test_return_path(self, excel_file_factory):
        """Test returning the file path."""
        excel = excel_file_factory()
        
        # Check path exists
        path = excel.return_path()
        assert path is not None
        assert os.path.exists(path)
        
        # Clean up
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.unit
class TestBGExcelFile:
    @pytest.fixture
    def user_factory(self, db):
        def create_user(username="testuser", password="password123", email="test@example.com", **kwargs):
            from django.contrib.auth.models import User
            return User.objects.create_user(
                username=username, 
                password=password, 
                email=email, 
                **kwargs
            )
        return create_user
    
    @pytest.fixture
    def cargo_factory(self, db):
        def create_cargo(product_type='soybean_meal', vendor_weight=1000, **kwargs):
            return CargoProduct.objects.create(
                product_type=product_type,
                vendor_weight=vendor_weight,
                purchaser_weight=vendor_weight,
                **kwargs
            )
        return create_cargo
    
    @pytest.fixture
    def bg_excel_file_factory(self, db, user_factory, cargo_factory):
        def create_bg_excel_file(
            user=None,
            title="Test BG Excel File",
            description="Test BG description",
            cargo=None
        ):
            if user is None:
                user = user_factory()
                
            if cargo is None:
                cargo = cargo_factory()
                
            # Create a simple test file
            file_content = b"test,data\n1,2\n3,4"
            excel_file = SimpleUploadedFile("bg_test_file.xlsx", file_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            return BGExcelFile.objects.create(
                user=user,
                title=title,
                file=excel_file,
                description=description,
                cargo=cargo
            )
        return create_bg_excel_file
    
    def test_bg_excel_file_creation(self, bg_excel_file_factory, cargo_factory):
        """Test the basic creation of a Bazaargah Excel file."""
        cargo = cargo_factory(product_type='corn')
        excel = bg_excel_file_factory(
            title="Bazaargah Excel",
            description="Bazaargah file description",
            cargo=cargo
        )
        
        assert excel.title == "Bazaargah Excel"
        assert excel.file_type == "bge"  # Should be automatically set
        assert excel.description == "Bazaargah file description"
        assert excel.cargo == cargo
        assert excel.cargo.product_type == 'corn'
        assert excel.created_at is not None
        
        # Clean up the created file
        if os.path.exists(excel.file.path):
            os.remove(excel.file.path)


@pytest.mark.unit
class TestExcelProcessingLog:
    @pytest.fixture
    def excel_file_factory(self, db, user_factory):
        def create_excel_file(
            user=None,
            title="Test Excel File",
            file_type="other"
        ):
            if user is None:
                user = user_factory()
                
            # Create a simple test file
            file_content = b"test,data\n1,2\n3,4"
            excel_file = SimpleUploadedFile("test_file.xlsx", file_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            return ExcelFile.objects.create(
                user=user,
                title=title,
                file=excel_file,
                file_type=file_type
            )
        return create_excel_file
    
    @pytest.fixture
    def user_factory(self, db):
        def create_user(username="testuser", password="password123", email="test@example.com", **kwargs):
            from django.contrib.auth.models import User
            return User.objects.create_user(
                username=username, 
                password=password, 
                email=email, 
                **kwargs
            )
        return create_user
    
    @pytest.fixture
    def processing_log_factory(self, db, excel_file_factory, user_factory):
        def create_processing_log(
            excel_file=None,
            processed_by=None,
            success=True,
            records_processed=100,
            records_updated=80,
            records_failed=20,
            log_message="Processing completed with minor issues"
        ):
            if excel_file is None:
                excel_file = excel_file_factory()
                
            if processed_by is None:
                processed_by = user_factory(username="processor")
                
            return ExcelProcessingLog.objects.create(
                excel_file=excel_file,
                processed_by=processed_by,
                success=success,
                records_processed=records_processed,
                records_updated=records_updated,
                records_failed=records_failed,
                log_message=log_message
            )
        return create_processing_log
    
    def test_processing_log_creation(self, processing_log_factory, excel_file_factory, user_factory):
        """Test the basic creation of an Excel processing log."""
        excel = excel_file_factory(title="Excel for Processing")
        user = user_factory(username="excel_processor")
        
        log = processing_log_factory(
            excel_file=excel,
            processed_by=user,
            records_processed=200,
            records_updated=150,
            records_failed=50,
            log_message="Processed with some failures"
        )
        
        assert log.excel_file == excel
        assert log.processed_by == user
        assert log.success is True
        assert log.records_processed == 200
        assert log.records_updated == 150
        assert log.records_failed == 50
        assert log.log_message == "Processed with some failures"
        assert log.processed_at is not None
        
        # Clean up the created file
        if os.path.exists(excel.file.path):
            os.remove(excel.file.path)
    
    def test_processing_log_str(self, processing_log_factory):
        """Test the string representation of a processing log."""
        log = processing_log_factory()
        
        assert log.excel_file.title in str(log)
        assert str(log.processed_at) in str(log) 