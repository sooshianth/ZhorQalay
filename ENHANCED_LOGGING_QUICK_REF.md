# 🚀 Enhanced Logging - Quick Reference

## Log Files

| File | Content | Level |
|------|---------|-------|
| **security.log** | ALL HTTP requests | INFO+ |
| **auth.log** | ALL authentication attempts | INFO+ |
| **django.log** | Django framework errors ONLY | ERROR+ |
| **bugs.log** | Existing app logs (temporary) | DEBUG+ |

## Security Log Fields

```
levelname !@# timestamp !@# user_id !@# username !@# action !@# method !@# endpoint !@# ip_address !@# user_agent !@# payload_summary !@# status_code !@# duration_ms !@# message !@# user_phone
```

## Auth Log Fields  

```
levelname !@# timestamp !@# user_id !@# username !@# action !@# ip_address !@# user_agent !@# message !@# user_phone
```

## Quick Logging

### Authentication Events (auth.log)

```python
auth_logger = logging.getLogger('authentication')

# Add these fields
extra = {
    'user_id': user.id,  # or 'Anonymous'
    'action': 'login_success'  # or 'login_failed', 'password_reset', etc.
}

auth_logger.info("LOGIN SUCCESS - User: {username}", extra=extra)
```

### Security Events (security.log)

HTTP requests are **automatically logged**. Manual logging:

```python
security_logger = logging.getLogger('security')

extra = {
    'user_id': user.id,
    'action': 'data_export',
    'status_code': 200,
    'duration_ms': 150,
    'payload_summary': '{"type":"csv"}'
}

security_logger.info("Data exported", extra=extra)
```

## Action Types

Auto-detected from URL:
- `login` - /login paths
- `logout` - /logout paths  
- `create` - /create, /insert
- `update` - /update, /edit
- `delete` - /delete
- `view` - /view, /list
- `api_call` - /api/
- `request` - (default)

## Sensitive Keys (Auto-Hidden)

These are automatically masked:
```python
password, token, secret, api_key, csrf, 
csrfmiddlewaretoken, verification_code, otp
```

## Quick Analysis

### PowerShell

```powershell
# Failed logins
Select-String -Path "logs\auth.log" -Pattern "FAILED"

# Slow requests (>1s)
Select-String -Path "logs\security.log" -Pattern "!@# [1-9]\d{3,} !@# REQUEST"

# Today's requests by user 42
$today = (Get-Date).ToString("yyyy-MM-dd")
Select-String -Path "logs\security.log" -Pattern "!@# 42 !@#" | Where {$_ -match $today}

# Status code distribution
(Get-Content "logs\security.log" | Where {$_ -match "!@# (\d{3}) !@# \d+ !@# REQUEST"} | ForEach {$matches[1]}) | Group | Sort Count -Desc
```

## Migration Checklist

- [ ] Test security logging (make an HTTP request)
- [ ] Test auth logging (try login)
- [ ] Verify all fields in logs
- [ ] Check bugs.log for existing app logs
- [ ] Set up log rotation
- [ ] Configure log analysis tool
- [ ] Set up alerting

## Common Patterns

```python
# User action
logger.activity(f"User {user.username} completed checkout")

# Security event  
extra = {'user_id': user.id, 'action': 'unauthorized_access'}
security_logger.alert("Unauthorized access attempt", extra=extra)

# Auth event
extra = {'user_id': 'Anonymous', 'action': 'login_failed'}
auth_logger.warning("Failed login - wrong password", extra=extra)

# Error with context
logger.error(f"Payment failed - Order: {order_id}", exc_info=True)
```

## Pro Tips

✅ Always use `extra` dict for structured fields  
✅ Include action type in extra  
✅ Use appropriate log levels  
✅ Don't log sensitive data (passwords, tokens)  
✅ Add context (IDs, usernames) to messages  
✅ Use custom levels: ACTIVITY, ALERT, BREACH  

## Emergency Commands

```powershell
# Find all ALERT/BREACH today
$today = (Get-Date).ToString("yyyy-MM-dd")
Get-Content "logs\*.log" | Where {($_ -match "ALERT|BREACH") -and ($_ -match $today)}

# Count errors by type
Get-Content "logs\django.log" | Where {$_ -match "ERROR"} | ForEach {
    if ($_ -match "ERROR !@# .+? !@# (.+?) !@#") { $matches[1] }
} | Group | Sort Count -Desc

# Monitor real-time (requires tail)
Get-Content "logs\security.log" -Wait -Tail 50
```
