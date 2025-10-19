# Logging Quick Reference Card

## Import Loggers

```python
import logging

# General logger (named after your module)
logger = logging.getLogger(__name__)

# Security logger
security_logger = logging.getLogger('security')

# Authentication logger
auth_logger = logging.getLogger('authentication')
```

## Log Levels (Lowest to Highest Priority)

| Level | Value | Method | Use Case |
|-------|-------|--------|----------|
| DEBUG | 10 | `logger.debug()` | Detailed diagnostic information |
| INFO | 20 | `logger.info()` | Confirmation that things work as expected |
| **ACTIVITY** | **25** | `logger.activity()` | **User actions and business events** |
| WARNING | 30 | `logger.warning()` | Something unexpected, but still working |
| **ALERT** | **35** | `logger.alert()` | **Security concerns needing attention** |
| ERROR | 40 | `logger.error()` | Serious problem occurred |
| **BREACH** | **45** | `logger.breach()` | **Critical security violation** |
| CRITICAL | 50 | `logger.critical()` | System cannot continue |

**Bold** = Custom levels added by this implementation

## Common Patterns

### 1. User Activity
```python
logger.activity(f"User completed checkout - Order #{order.id}")
logger.activity("File uploaded successfully")
logger.activity(f"Report generated: {report_type}")
```

### 2. Security Events
```python
security_logger.alert(f"Failed login attempt - Username: {username}")
security_logger.alert("Rate limit approaching for IP")
security_logger.breach("SQL injection attempt detected")
security_logger.breach(f"Unauthorized data access attempt")
```

### 3. Authentication
```python
auth_logger.info(f"User {username} logged in successfully")
auth_logger.warning(f"Invalid password for {username}")
auth_logger.alert(f"Account locked due to failed attempts: {username}")
```

### 4. General Information
```python
logger.info("Processing started")
logger.info(f"Email sent to {recipient}")
logger.info(f"Cache invalidated for key: {cache_key}")
```

### 5. Warnings
```python
logger.warning(f"Low disk space: {available_space}MB remaining")
logger.warning("Deprecated API endpoint accessed")
logger.warning(f"Slow query detected: {query_time}s")
```

### 6. Errors
```python
logger.error(f"Payment processing failed: {error_message}")
logger.error(f"External API timeout: {api_url}")
logger.error(f"Database connection lost", exc_info=True)
```

### 7. Critical Issues
```python
logger.critical("Database connection pool exhausted")
logger.critical("Application unable to start")
```

## Best Practices

### ✓ DO
```python
# Include relevant context
logger.info(f"Order {order_id} created by user {user.username}")

# Use appropriate log level
logger.activity("User logged in")  # User action
logger.alert("Suspicious login pattern")  # Security concern

# Log exceptions with traceback
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {str(e)}", exc_info=True)
```

### ✗ DON'T
```python
# Don't log sensitive data
logger.info(f"Password: {password}")  # BAD!
logger.info(f"Credit card: {cc_number}")  # BAD!

# Don't use wrong log level
logger.critical("User clicked button")  # BAD! Use activity()

# Don't log without context
logger.error("Error occurred")  # BAD! What error? Where?
```

## View Example

```python
def my_view(request):
    logger.activity("View accessed")
    
    try:
        # Your code here
        result = process_data(request.POST)
        logger.info(f"Data processed successfully: {result.id}")
        return JsonResponse({'status': 'success'})
        
    except ValidationError as e:
        logger.warning(f"Validation failed: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal error'}, status=500)
```

## Middleware (Automatic)

These are captured automatically by middleware:
- Username (full name + username)
- IP address (with proxy detection)
- Phone number (from session)
- Upload size (request size in bytes)
- Download size (response size in bytes)
- Request/response timing
- HTTP status codes

**You don't need to log these manually!**

## Log Format

Logs are written in this format (fields separated by `!@#`):
```
INFO !@# 2025-10-19 10:30:45 !@# myapp.views !@# my_view !@# 1234 !@# 5678 !@# John Doe - johndoe !@# 192.168.1.100 !@# 2048 !@# 1024 !@# User logged in !@# 09123456789
```

Fields:
1. Level name
2. Timestamp
3. Logger name
4. Function name
5. Process ID
6. Thread ID
7. Username
8. IP address
9. Download size
10. Upload size
11. Message
12. Phone number

## Log Files

- `logs/django.log` - General application logs
- `logs/security.log` - Security events (ALERT, BREACH)
- `logs/auth.log` - Authentication events

## Testing

```python
# In Django shell
from core.test_logging_setup import test_all_loggers
test_all_loggers()
```

## Common Mistakes

| Mistake | Correction |
|---------|-----------|
| `logger = logging.getLogger('mylogger')` | Use `logger = logging.getLogger(__name__)` |
| `logger.info("Error occurred")` | Use `logger.error()` for errors |
| `logger.critical("User clicked")` | Use `logger.activity()` for user actions |
| `logger.debug(f"Password: {pwd}")` | Never log sensitive data! |
| `logger.info("Failed")` | Add context: `logger.info(f"Payment failed: {reason}")` |

## Quick Search Commands

### Windows (PowerShell)
```powershell
# Find all errors
Select-String -Path "logs\django.log" -Pattern "ERROR"

# Find logs for user
Select-String -Path "logs\django.log" -Pattern "johndoe"

# Find security breaches
Select-String -Path "logs\security.log" -Pattern "BREACH"
```

### Unix/Linux/macOS
```bash
# Find all errors
grep "ERROR" logs/django.log

# Find logs for user
grep "johndoe" logs/django.log

# Find security breaches
grep "BREACH" logs/security.log

# Count errors by type
grep "ERROR" logs/django.log | wc -l
```

---

**For detailed documentation, see:** `LOGGING_GUIDE.md`
**For examples, see:** `core/logging_examples.py`
**For implementation details, see:** `LOGGING_IMPLEMENTATION_SUMMARY.md`
