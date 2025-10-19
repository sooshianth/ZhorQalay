"""
Example usage of the professional logging system in Django views
"""
import logging
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from core.logging_levels import *  # Import custom log levels (ACTIVITY, ALERT, BREACH)

# Get loggers
logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')
auth_logger = logging.getLogger('authentication')


def example_view(request):
    """
    Example view showing different logging scenarios
    """
    
    # Log user activity
    logger.activity(f"User viewing example page")
    
    # Log general information
    logger.info("Example view accessed")
    
    # Log debug information (useful for development)
    logger.debug(f"Request method: {request.method}")
    
    # Return response...
    return HttpResponse("Example view")


def login_view(request):
    """
    Example login view with authentication logging
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Log successful login
            auth_logger.info(f"User {username} logged in successfully")
            logger.activity(f"User login: {username}")
            
            return redirect('dashboard')
        else:
            # Log failed login attempt
            auth_logger.warning(f"Failed login attempt for username: {username}")
            security_logger.alert(f"Failed login from IP - Username: {username}")
            
            # Could also increment failed attempt counter here
            
    return render(request, 'login.html')


def admin_action_view(request):
    """
    Example admin action with security logging
    """
    if not request.user.is_staff:
        # Log unauthorized access attempt
        security_logger.alert(f"Unauthorized admin access attempt by user: {request.user.username}")
        return HttpResponseForbidden("Access denied")
    
    # Log admin activity
    logger.activity(f"Admin {request.user.username} performed action")
    
    # Perform admin action...
    
    return HttpResponse("Action completed")


def payment_view(request):
    """
    Example payment processing with different log levels
    """
    try:
        # Log activity start
        logger.activity("Payment processing started")
        
        # Process payment
        amount = request.POST.get('amount')
        logger.info(f"Processing payment of {amount}")
        
        # Validate payment
        if not validate_payment(amount):
            logger.warning(f"Invalid payment amount: {amount}")
            return HttpResponse("Invalid payment", status=400)
        
        # Process the payment
        result = process_payment(amount)
        
        if result.success:
            logger.activity(f"Payment of {amount} completed successfully")
            logger.info(f"Transaction ID: {result.transaction_id}")
            return HttpResponse("Payment successful")
        else:
            logger.error(f"Payment processing failed: {result.error}")
            return HttpResponse("Payment failed", status=500)
            
    except Exception as e:
        # Log critical error
        logger.critical(f"Payment processing exception: {str(e)}", exc_info=True)
        return HttpResponse("Internal error", status=500)


def suspicious_activity_view(request):
    """
    Example of detecting and logging suspicious activity
    """
    # Check for suspicious patterns
    if detect_sql_injection(request):
        security_logger.breach(f"SQL injection attempt detected in request")
        return HttpResponseForbidden("Request blocked")
    
    if detect_xss_attempt(request):
        security_logger.breach(f"XSS attempt detected in request")
        return HttpResponseForbidden("Request blocked")
    
    # Check rate limiting manually
    cache_key = f"user_requests_{request.user.id}"
    request_count = cache.get(cache_key, 0)
    
    if request_count > 100:
        security_logger.alert(f"Rate limit exceeded - {request_count} requests")
        return HttpResponseForbidden("Too many requests")
    
    cache.set(cache_key, request_count + 1, timeout=60)
    
    # Normal processing...
    return HttpResponse("OK")


def data_export_view(request):
    """
    Example of logging data exports (important for audit trails)
    """
    export_type = request.GET.get('type', 'csv')
    
    # Log the export activity
    logger.activity(f"Data export requested - Type: {export_type}")
    
    # Check permissions
    if not request.user.has_perm('core.can_export_data'):
        security_logger.alert(f"Unauthorized data export attempt")
        return HttpResponseForbidden("No permission")
    
    # Generate export
    data = generate_export(export_type)
    
    # Log successful export with size
    logger.info(f"Data export completed - Type: {export_type}, Size: {len(data)} bytes")
    
    return HttpResponse(data, content_type='application/octet-stream')


def user_settings_update_view(request):
    """
    Example of logging configuration changes
    """
    if request.method == 'POST':
        old_settings = get_user_settings(request.user)
        new_settings = request.POST.dict()
        
        # Log the changes
        logger.activity(f"User settings updated")
        logger.info(f"Settings changed from {old_settings} to {new_settings}")
        
        # Save settings
        save_user_settings(request.user, new_settings)
        
        return redirect('settings')
    
    return render(request, 'settings.html')


# Helper functions (pseudo-code)
def validate_payment(amount):
    return True

def process_payment(amount):
    class Result:
        success = True
        transaction_id = "TXN123"
        error = None
    return Result()

def detect_sql_injection(request):
    return False

def detect_xss_attempt(request):
    return False

def generate_export(export_type):
    return b"export data"

def get_user_settings(user):
    return {}

def save_user_settings(user, settings):
    pass
