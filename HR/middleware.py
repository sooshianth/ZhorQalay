import json
import logging

logger = logging.getLogger(__name__)

class DebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # تنظیم لاگر برای نمایش در کنسول
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # ثبت اطلاعات درخواست
        logger.debug(f"Processing request: {request.path}")
        if request.path == '/hr/attendance/pending/':
            logger.debug("Processing pending attendance request")
            
        # پردازش درخواست
        response = self.get_response(request)
        
        # ثبت اطلاعات پاسخ
        if hasattr(response, 'context_data') and response.context_data and request.path == '/hr/attendance/pending/':
            logger.debug("Checking pending_attendances data")
            if 'pending_attendances' in response.context_data:
                pending_data = response.context_data['pending_attendances']
                logger.debug(f"Found {len(pending_data)} pending attendances")
                for item in pending_data:
                    logger.debug(f"Attendance ID: {item.get('id')}, Time ranges: {item.get('time_ranges')}")
        
        return response 