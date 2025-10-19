# Enhanced Logging System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DJANGO APPLICATION                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            MIDDLEWARE LAYER                              │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ LogContextMiddleware (Priority: FIRST)                   │          │
│  │ - Captures: user, IP, phone, upload/download sizes       │          │
│  │ - Sets thread-local context for all loggers              │          │
│  └──────────────────────────────────────────────────────────┘          │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ SecurityLoggingMiddleware                                │          │
│  │ - Logs ALL HTTP requests → security.log                  │          │
│  │ - Adds: action, method, endpoint, payload, status,       │          │
│  │   duration_ms, user_agent                                │          │
│  │ - Rate limiting (100 req/min)                            │          │
│  └──────────────────────────────────────────────────────────┘          │
│                              ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ LoginAttemptMiddleware                                   │          │
│  │ - Monitors /authentication/ paths                        │          │
│  │ - Logs suspicious activity → auth.log                    │          │
│  │ - Blocks IPs after 20 failed attempts                    │          │
│  └──────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          APPLICATION LOGGERS                             │
│                                                                          │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐ │
│  │ authentication     │  │ security           │  │ Existing Loggers │ │
│  │ Logger             │  │ Logger             │  │ (bki_*, core_*,  │ │
│  │                    │  │                    │  │  erp_*, etc.)    │ │
│  │ - Login success    │  │ - ALL requests     │  │                  │ │
│  │ - Login failed     │  │ - Rate limits      │  │ - Go to bugs.log │ │
│  │ - OTP wrong        │  │ - Exceptions       │  │ - Will migrate   │ │
│  │ - Too many tries   │  │ - Security events  │  │   later          │ │
│  └────────────────────┘  └────────────────────┘  └──────────────────┘ │
│           │                       │                        │            │
│           ▼                       ▼                        ▼            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOGGING FILTERS                                  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │ LogUserInfoFilter                                        │          │
│  │ - Adds user context to all log records                   │          │
│  │ - Fields: user_id, username, ip_address, user_phone,    │          │
│  │   method, endpoint, action, user_agent, status_code,    │          │
│  │   duration_ms, payload_summary, upload/download sizes   │          │
│  └──────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            FORMATTERS                                    │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │  security   │  │    auth     │  │    bugs     │  │ django_errors│ │
│  │  formatter  │  │  formatter  │  │  formatter  │  │  formatter   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              HANDLERS                                    │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│
│  │ security_    │  │  auth_file   │  │  bugs_file   │  │  django_   ││
│  │ file         │  │              │  │              │  │  errors_   ││
│  │              │  │              │  │              │  │  file      ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘│
│         │                 │                 │                 │        │
│         ▼                 ▼                 ▼                 ▼        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│
│  │ security.log │  │  auth.log    │  │  bugs.log    │  │ django.log ││
│  │              │  │              │  │              │  │            ││
│  │ - ALL HTTP   │  │ - Login      │  │ - App logs   │  │ - Django   ││
│  │   requests   │  │   attempts   │  │   (temp)     │  │   errors   ││
│  │ - Rate limit │  │ - OTP verify │  │ - bki_*      │  │   only     ││
│  │ - Exceptions │  │ - Blocks     │  │ - core_*     │  │            ││
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘│
│                                                                         │
│  ┌──────────────┐  ┌──────────────────────────────────────────────┐  │
│  │   console    │  │        circular_buffer (in-memory)           │  │
│  │   handler    │  │        - 5000 most recent logs               │  │
│  │              │  │        - For debugging & log viewer          │  │
│  └──────────────┘  └──────────────────────────────────────────────┘  │
│         │                              │                               │
│         ▼                              ▼                               │
│   Terminal Output               Memory (Debug)                         │
└─────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                            DATA FLOW EXAMPLE
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. User makes request: GET /api/orders/list?page=1                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. LogContextMiddleware captures:                                       │
│    - user: User(id=42, username='ali.ahmadi')                          │
│    - ip: 192.168.1.100                                                  │
│    - phone: 09123456789                                                 │
│    - upload: 0 bytes                                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. SecurityLoggingMiddleware.process_request():                        │
│    - method: GET                                                        │
│    - endpoint: /api/orders/list                                        │
│    - action: api_call (detected from 'api' in path)                   │
│    - user_agent: Mozilla/5.0...                                        │
│    - payload_summary: {"page":"1"}                                     │
│    - start_time: recorded                                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. Request processed by view, returns response with status 200         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. SecurityLoggingMiddleware.process_response():                       │
│    - status_code: 200                                                   │
│    - duration_ms: 45                                                    │
│    - download: 2048 bytes                                              │
│                                                                          │
│    Creates log with extra fields:                                      │
│    extra = {                                                            │
│        'user_id': 42,                                                   │
│        'action': 'api_call',                                           │
│        'status_code': 200,                                             │
│        'duration_ms': 45,                                              │
│        'payload_summary': '{"page":"1"}'                               │
│    }                                                                    │
│                                                                          │
│    security_logger.info("REQUEST - GET /api/orders/list", extra=extra)│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. LogUserInfoFilter adds more context:                                │
│    - username: "علی احمدی - ali.ahmadi"                                │
│    - user_phone: "09123456789"                                         │
│    - All other fields from thread-local storage                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 7. Security formatter formats the log:                                  │
│                                                                          │
│ INFO !@# 2025-10-19 14:30:22,345 !@# 42 !@# علی احمدی - ali.ahmadi    │
│ !@# api_call !@# GET !@# /api/orders/list !@# 192.168.1.100            │
│ !@# Mozilla/5.0 (Windows NT 10.0; Win64; x64)... !@# {"page":"1"}      │
│ !@# 200 !@# 45 !@# REQUEST - GET /api/orders/list !@# 09123456789      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 8. Handlers write to multiple destinations:                            │
│    ✓ security.log (file)                                               │
│    ✓ console (terminal)                                                │
│    ✓ circular_buffer (memory)                                          │
└─────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                          AUTHENTICATION FLOW
═══════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────┐
│ 1. User submits OTP code                                                │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. OTPLoginForm.verify_otp() called                                    │
│    - Checks rate limit (10 attempts)                                   │
│    - Verifies OTP code                                                 │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. If successful:                                                       │
│    extra = {'user_id': 42, 'action': 'login_success'}                 │
│    auth_logger.info("LOGIN SUCCESS - User: ali.ahmadi - Phone:         │
│                      09123456789", extra=extra)                        │
│                                                                          │
│    If failed:                                                           │
│    extra = {'user_id': 'Anonymous', 'action': 'login_failed'}         │
│    auth_logger.warning("LOGIN FAILED - Wrong OTP code for phone:       │
│                         09123456789", extra=extra)                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. LogUserInfoFilter adds context                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Auth formatter formats the log                                       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. Written to:                                                          │
│    ✓ auth.log                                                           │
│    ✓ console                                                            │
│    ✓ circular_buffer                                                    │
└─────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                              KEY BENEFITS
═══════════════════════════════════════════════════════════════════════════

✓ Separation of Concerns:
  - Security events → security.log
  - Authentication → auth.log
  - Framework errors → django.log
  - App logs → bugs.log

✓ Structured Logging:
  - All fields delimited by !@#
  - Easy to parse with log analysis tools
  - Ready for ELK Stack, Splunk, Graylog

✓ Automatic Context:
  - No manual field setting in most cases
  - Middleware captures everything
  - Thread-local storage for context

✓ Security:
  - Sensitive data automatically excluded
  - Rate limiting logged
  - Failed attempts tracked

✓ Performance:
  - Minimal overhead
  - Async logging possible
  - Circular buffer for debugging

✓ Compliance Ready:
  - Full audit trail
  - User actions tracked
  - Time-stamped events
