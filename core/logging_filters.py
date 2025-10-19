import logging
from collections import deque
from threading import Lock
from datetime import datetime

# Thread-local storage for user context
_thread_local = {}

def set_log_context(user, ip, user_phone, up=0, down=0, method='', endpoint='', user_agent='', action=''):
    """
    Set logging context for current thread with extended fields
    """
    _thread_local['user'] = user
    _thread_local['ip'] = ip
    _thread_local['up'] = up
    _thread_local['down'] = down
    _thread_local['user_phone'] = user_phone
    _thread_local['method'] = method
    _thread_local['endpoint'] = endpoint
    _thread_local['user_agent'] = user_agent
    _thread_local['action'] = action

def get_log_context():
    """
    Get logging context for current thread
    """
    return (
        _thread_local.get('user'),
        _thread_local.get('ip'),
        _thread_local.get('up', 0),
        _thread_local.get('down', 0),
        _thread_local.get('user_phone'),
        _thread_local.get('method', ''),
        _thread_local.get('endpoint', ''),
        _thread_local.get('user_agent', ''),
        _thread_local.get('action', '')
    )

class LogUserInfoFilter(logging.Filter):
    """
    Filter that adds user information to log records with extended fields
    """
    def filter(self, record):
        user, ip, upload_size, download_size, user_phone, method, endpoint, user_agent, action = get_log_context()
        
        # User info
        if user and user.is_authenticated:
            first_name = getattr(user, 'first_name', '')
            last_name = getattr(user, 'last_name', '')
            fn = first_name if first_name else '()'
            ln = last_name if last_name else '()'
            record.username = f"{fn} {ln} - {user.username}"
            record.user_id = getattr(user, 'id', 'Unknown')
            record.user_phone = user_phone or '-'
        else:
            record.username = 'Anonymous'
            record.user_id = 'Anonymous'
            record.user_phone = '-'

        # Request info
        record.log_ip = ip or '-'
        record.ip_address = ip or '-'
        record.upload_size = upload_size
        record.download_size = download_size
        record.method = method or '-'
        record.endpoint = endpoint or '-'
        record.user_agent = user_agent[:200] if user_agent else '-'  # Limit to 200 chars
        record.action = action or '-'
        
        # File info - extract filename from pathname
        import os
        if hasattr(record, 'pathname') and record.pathname:
            record.filename = os.path.basename(record.pathname)
        elif not hasattr(record, 'filename'):
            record.filename = 'unknown'
        
        # Add placeholders for fields that will be set by middleware/loggers
        if not hasattr(record, 'status_code'):
            record.status_code = '-'
        if not hasattr(record, 'duration_ms'):
            record.duration_ms = '-'
        if not hasattr(record, 'payload_summary'):
            record.payload_summary = '-'
        
        return True

class ExcludeRunserverAndHttpProtocol(logging.Filter):
    def filter(self, record):
        # Exclude logs from 'runserver', 'http_protocol', and 'django.server'
        return record.name not in ['runserver', 'http_protocol', 'django.server']


class CircularBufferHandler(logging.Handler):
    """
    A thread-safe circular buffer handler that stores log records in memory.
    """
    _instance = None
    _lock = Lock()
    
    def __new__(cls, capacity=1000):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CircularBufferHandler, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, capacity=1000):
        if self._initialized:
            return
            
        super().__init__()
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.buffer_lock = Lock()
        self._initialized = True
    
    def emit(self, record):
        """
        Store the log record in the circular buffer.
        """
        try:
            # Format the record
            msg = self.format(record)
            
            # Create a dictionary with log information
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created),
                'level': record.levelname,
                'logger': record.name,
                'message': msg,
                'pathname': record.pathname,
                'lineno': record.lineno,
                'funcName': record.funcName,
            }
            
            # Add to buffer (thread-safe)
            with self.buffer_lock:
                self.buffer.append(log_entry)
                
        except Exception:
            self.handleError(record)
    
    def get_logs(self, level=None, logger_name=None, limit=None):
        """
        Retrieve logs from the buffer with optional filtering.
        
        Args:
            level: Filter by log level (e.g., 'DEBUG', 'INFO', 'WARNING', 'ERROR')
            logger_name: Filter by logger name
            limit: Maximum number of logs to return (most recent)
        
        Returns:
            List of log entries
        """
        with self.buffer_lock:
            logs = list(self.buffer)
        
        # Apply filters
        if level:
            logs = [log for log in logs if log['level'] == level]
        
        if logger_name:
            logs = [log for log in logs if logger_name in log['logger']]
        
        # Apply limit (return most recent)
        if limit:
            logs = logs[-limit:]
        
        return logs
    
    def clear(self):
        """
        Clear all logs from the buffer.
        """
        with self.buffer_lock:
            self.buffer.clear()
    
    def get_stats(self):
        """
        Get statistics about the buffer.
        """
        with self.buffer_lock:
            total = len(self.buffer)
            levels = {}
            loggers = {}
            
            for log in self.buffer:
                # Count by level
                level = log['level']
                levels[level] = levels.get(level, 0) + 1
                
                # Count by logger
                logger = log['logger']
                loggers[logger] = loggers.get(logger, 0) + 1
            
            return {
                'total': total,
                'capacity': self.capacity,
                'levels': levels,
                'loggers': loggers,
            } 