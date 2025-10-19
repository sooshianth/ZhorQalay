import logging
from collections import deque
from threading import Lock
from datetime import datetime

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