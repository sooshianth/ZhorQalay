import logging
import os


class FilenameFormatter(logging.Formatter):
    """
    Custom formatter that ensures filename is extracted from pathname
    """
    def format(self, record):
        # Force extract filename from pathname before formatting
        if hasattr(record, 'pathname') and record.pathname:
            record.filename = os.path.basename(record.pathname)
        else:
            record.filename = 'unknown'
        
        # Now call parent format
        return super().format(record)
