# Professional Logging Guide

## Overview

This Django application now has a comprehensive professional logging system designed for analysis with specialized log management systems (like ELK Stack, Splunk, Graylog, etc.).

## Features

### 1. Custom Logging Levels

In addition to standard Python logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL), we have added three custom levels:

- **ACTIVITY** (Level 25): For logging user activities and business logic events
- **ALERT** (Level 35): For security alerts and suspicious activities that need attention
- **BREACH** (Level 45): For security breaches and critical security violations

### 2. Structured Log Format

All logs follow a consistent format with fields separated by `!@#` for easy parsing:

```
{levelname} !@# {asctime} !@# {name} !@# {funcName} !@# {process:d} !@# {thread:d} !@# {username} !@# {log_ip} !@# {download_size} !@# {upload_size} !@# {message} !@# {user_phone}
```

Fields:
- **levelname**: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL, ACTIVITY, ALERT, BREACH)
- **asctime**: Timestamp
- **name**: Logger name
- **funcName**: Function name where log was generated
- **process**: Process ID
- **thread**: Thread ID
- **username**: User's full name and username (or '-' if anonymous)
- **log_ip**: Client IP address (or '-' if not available)
- **download_size**: Response size in bytes
- **upload_size**: Request size in bytes
- **message**: The actual log message
- **user_phone**: User's phone number (or '-' if not available)

### 3. Log Files

Logs are written to the `logs/` directory:

- **django.log**: General application logs
- **security.log**: Security-related logs (failed logins, rate limiting, unauthorized access, etc.)
- **auth.log**: Authentication-related logs

### 4. Middleware Components

#### LogContextMiddleware
Automatically captures user context (username, IP, phone number, upload/download sizes) for all requests.

#### SecurityLoggingMiddleware
- Logs all HTTP requests and responses
- Implements rate limiting (100 requests per minute per IP)
- Logs suspicious status codes (401, 403, 404, 5xx)
- Tracks request processing time

#### LoginAttemptMiddleware
- Monitors failed login attempts
- Blocks IPs with more than 20 failed attempts in 1 hour
- Logs suspicious login activity

#### AdminSessionManagementMiddleware
- Validates admin sessions
- Ensures admin phone numbers are still authorized
- Logs unauthorized admin access attempts

## Usage Examples

### Basic Logging

```python
import logging

logger = logging.getLogger(__name__)

# Standard levels
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")
```

### Custom Levels

```python
import logging

logger = logging.getLogger(__name__)

# Custom levels
logger.activity("User completed checkout process")
logger.alert("Suspicious activity detected: Multiple failed login attempts")
logger.breach("Security breach: Unauthorized access to sensitive data")
```

### Security Logging

```python
import logging

security_logger = logging.getLogger('security')

# Security events
security_logger.alert(f"Failed login attempt from IP {ip_address}")
security_logger.breach(f"SQL injection attempt detected: {request_data}")
```

### Authentication Logging

```python
import logging

auth_logger = logging.getLogger('authentication')

# Authentication events
auth_logger.info(f"User {username} logged in successfully")
auth_logger.warning(f"Invalid password for user {username}")
```

## Log Analysis

The structured format with `!@#` separators makes it easy to parse logs with tools like:

### Using grep/awk (Unix-like systems)

```bash
# Find all ALERT level logs
grep "ALERT" logs/security.log

# Extract all IPs from security logs
awk -F '!@#' '{print $8}' logs/security.log | sort | uniq

# Find logs for specific user
grep "john.doe" logs/django.log
```

### Using PowerShell (Windows)

```powershell
# Find all ALERT level logs
Select-String -Path "logs\security.log" -Pattern "ALERT"

# Extract user information
Get-Content "logs\django.log" | ForEach-Object { ($_ -split '!@#')[7] } | Sort-Object -Unique
```

### Log Management Systems

For production environments, consider integrating with:

1. **ELK Stack** (Elasticsearch, Logstash, Kibana)
   - Use Filebeat to ship logs
   - Parse fields using Logstash grok patterns
   - Visualize in Kibana dashboards

2. **Splunk**
   - Configure log file monitoring
   - Create custom field extractions for `!@#` delimiter
   - Build security dashboards

3. **Graylog**
   - Set up log input from file
   - Create extractors for structured fields
   - Configure alerts for ALERT and BREACH levels

## Best Practices

1. **Use appropriate log levels**
   - DEBUG: Detailed information for diagnosing problems
   - INFO: Confirmation that things are working as expected
   - ACTIVITY: User actions and business events
   - WARNING: Something unexpected but not an error
   - ALERT: Security concerns that need attention
   - ERROR: Due to a more serious problem
   - BREACH: Critical security violations
   - CRITICAL: System failures

2. **Include context in messages**
   ```python
   logger.info(f"Order {order_id} created by user {user.username}")
   ```

3. **Don't log sensitive data**
   ```python
   # Bad
   logger.info(f"Password: {password}")
   
   # Good
   logger.info("Password validation successful")
   ```

4. **Use appropriate loggers**
   ```python
   # For security events
   security_logger = logging.getLogger('security')
   
   # For your module
   logger = logging.getLogger(__name__)
   ```

## Configuration

Logging configuration is in `config/settings.py`. You can adjust:

- Log levels for different handlers
- File locations
- Formatters
- Circular buffer capacity (in-memory logs)

## Troubleshooting

### Logs not appearing
1. Check that the `logs/` directory exists and is writable
2. Verify log level configuration in settings.py
3. Ensure the logger name matches your configuration

### Performance issues
1. Consider using async logging handlers for high-volume applications
2. Adjust log levels (use INFO or WARNING in production instead of DEBUG)
3. Implement log rotation with `RotatingFileHandler`

## Future Enhancements

Consider adding:
- Log rotation (daily/size-based)
- Remote logging (syslog, cloud services)
- Encrypted logs for sensitive data
- Real-time alerting integration
- Performance metrics logging
