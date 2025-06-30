import logging

class ExcludeRunserverAndHttpProtocol(logging.Filter):
    def filter(self, record):
        # Exclude logs from 'runserver', 'http_protocol', and 'django.server'
        return record.name not in ['runserver', 'http_protocol', 'django.server'] 