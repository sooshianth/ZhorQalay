"""
Test script to verify the professional logging setup

Run this from Django shell:
python manage.py shell < test_logging_setup.py

Or import in shell:
from core.test_logging_setup import test_all_loggers
test_all_loggers()
"""
import logging
from core.logging_levels import *  # Import custom log levels (ACTIVITY, ALERT, BREACH)


def test_standard_levels():
    """Test standard logging levels"""
    logger = logging.getLogger('test.standard')
    
    print("\n=== Testing Standard Logging Levels ===")
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")
    logger.critical("This is a CRITICAL message")
    print("✓ Standard levels test completed")


def test_custom_levels():
    """Test custom logging levels"""
    logger = logging.getLogger('test.custom')
    
    print("\n=== Testing Custom Logging Levels ===")
    logger.activity("This is an ACTIVITY message (level 25)")
    logger.alert("This is an ALERT message (level 35)")
    logger.breach("This is a BREACH message (level 45)")
    print("✓ Custom levels test completed")


def test_security_logger():
    """Test security logger"""
    security_logger = logging.getLogger('security')
    
    print("\n=== Testing Security Logger ===")
    security_logger.info("Security test: Normal activity")
    security_logger.alert("Security test: Suspicious activity detected")
    security_logger.breach("Security test: Critical security breach")
    print("✓ Security logger test completed")


def test_auth_logger():
    """Test authentication logger"""
    auth_logger = logging.getLogger('authentication')
    
    print("\n=== Testing Authentication Logger ===")
    auth_logger.info("Auth test: User login successful")
    auth_logger.warning("Auth test: Failed login attempt")
    auth_logger.alert("Auth test: Multiple failed login attempts")
    print("✓ Authentication logger test completed")


def test_middleware_logger():
    """Test middleware logger"""
    middleware_logger = logging.getLogger('core.middleware')
    
    print("\n=== Testing Middleware Logger ===")
    middleware_logger.info("Middleware test: Request received")
    middleware_logger.warning("Middleware test: Rate limit approaching")
    middleware_logger.alert("Middleware test: Rate limit exceeded")
    print("✓ Middleware logger test completed")


def test_log_context():
    """Test log context filter"""
    from core.logging_filters import set_log_context, get_log_context
    
    print("\n=== Testing Log Context ===")
    
    # Create a mock user object
    class MockUser:
        is_authenticated = True
        username = "testuser"
        first_name = "Test"
        last_name = "User"
    
    # Set context
    set_log_context(
        user=MockUser(),
        ip="192.168.1.100",
        user_phone="09123456789",
        up=1024,
        down=2048
    )
    
    # Get context
    user, ip, up, down, phone = get_log_context()
    print(f"Context set successfully:")
    print(f"  - User: {user.username if user else 'None'}")
    print(f"  - IP: {ip}")
    print(f"  - Phone: {phone}")
    print(f"  - Upload: {up} bytes")
    print(f"  - Download: {down} bytes")
    
    # Test logger with context
    logger = logging.getLogger('test.context')
    logger.info("This message should include user context information")
    print("✓ Log context test completed")


def check_log_files():
    """Check if log files exist and are writable"""
    import os
    from pathlib import Path
    from django.conf import settings
    
    print("\n=== Checking Log Files ===")
    
    base_dir = Path(settings.BASE_DIR)
    log_dir = base_dir / 'logs'
    
    if not log_dir.exists():
        print(f"⚠ Warning: Log directory does not exist: {log_dir}")
        print(f"Creating log directory...")
        log_dir.mkdir(exist_ok=True)
        print(f"✓ Log directory created")
    else:
        print(f"✓ Log directory exists: {log_dir}")
    
    # Check log files
    log_files = ['django.log', 'security.log', 'auth.log']
    for log_file in log_files:
        log_path = log_dir / log_file
        if log_path.exists():
            size = log_path.stat().st_size
            print(f"✓ {log_file} exists ({size} bytes)")
        else:
            print(f"⚠ {log_file} does not exist yet (will be created on first log)")
    
    print("✓ Log files check completed")


def test_all_loggers():
    """Run all logging tests"""
    print("\n" + "="*60)
    print("PROFESSIONAL LOGGING SYSTEM TEST")
    print("="*60)
    
    try:
        test_standard_levels()
        test_custom_levels()
        test_security_logger()
        test_auth_logger()
        test_middleware_logger()
        test_log_context()
        check_log_files()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY! ✓")
        print("="*60)
        print("\nCheck the following log files for output:")
        print("  - logs/django.log")
        print("  - logs/security.log")
        print("  - logs/auth.log")
        print("\n")
        
    except Exception as e:
        print(f"\n⚠ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # This won't work directly, needs Django environment
    print("Please run this from Django shell:")
    print("  python manage.py shell")
    print("  >>> from core.test_logging_setup import test_all_loggers")
    print("  >>> test_all_loggers()")
