# ⚠️ IMPORTANT: Custom Log Levels Import

## Critical Requirement

**If you use any custom log levels (`.activity()`, `.alert()`, `.breach()`), you MUST import them:**

```python
from core.logging_levels import *  # Import custom log levels
```

## Why This Is Necessary

The custom log levels are defined in `core/logging_levels.py` and are **not** part of Python's standard logging module. They are added as methods to the `logging.Logger` class at runtime.

Without this import, Python will raise an `AttributeError` when you try to use:
- `logger.activity()`
- `logger.alert()`
- `logger.breach()`

## Files That Already Have This Import

✅ `config/settings.py` - Imports at module level
✅ `config/middleware.py` - Uses `.alert()`
✅ `authentication/forms/forms.py` - Uses `.alert()`
✅ `core/logging_examples.py` - Uses `.activity()`, `.alert()`, `.breach()`
✅ `core/test_logging_setup.py` - Uses `.activity()`, `.alert()`, `.breach()`

## Standard Log Levels (No Import Needed)

These are built into Python and **don't** require the import:
- `logger.debug()`
- `logger.info()`
- `logger.warning()`
- `logger.error()`
- `logger.critical()`

## Quick Reference

### Custom Levels (NEED IMPORT)
```python
from core.logging_levels import *

logger = logging.getLogger(__name__)
logger.activity("User completed action")  # Level 25
logger.alert("Security concern detected")  # Level 35
logger.breach("Security breach!")          # Level 45
```

### Standard Levels (NO IMPORT NEEDED)
```python
import logging

logger = logging.getLogger(__name__)
logger.debug("Debug info")
logger.info("General info")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical failure")
```

## When Adding New Files

If you create a new Python file that uses custom log levels:

1. Add the import after other imports:
```python
import logging
from core.logging_levels import *  # Import custom log levels

logger = logging.getLogger(__name__)
```

2. Now you can use all log levels:
```python
logger.info("Standard level")
logger.activity("Custom level")  # Works!
logger.alert("Custom level")     # Works!
logger.breach("Custom level")    # Works!
```

## Common Mistake

❌ **WRONG** (will fail with AttributeError):
```python
import logging

logger = logging.getLogger(__name__)
logger.alert("This will crash!")  # AttributeError: 'Logger' object has no attribute 'alert'
```

✅ **CORRECT**:
```python
import logging
from core.logging_levels import *

logger = logging.getLogger(__name__)
logger.alert("This works!")  # Success!
```

## Technical Details

The `core.logging_levels` module:
1. Defines three custom log level numbers (25, 35, 45)
2. Registers them with the logging system using `logging.addLevelName()`
3. Adds methods to the `logging.Logger` class dynamically
4. Must be imported before the custom methods are available

The import must happen **before** you try to use the custom log levels, but it only needs to happen once per Python file/module.
