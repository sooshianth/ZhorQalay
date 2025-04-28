from django.contrib.auth import logout
from django.utils import timezone
from django.shortcuts import redirect
from datetime import timedelta
from django.conf import settings


class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_time = timezone.now()
            
            # Get the last activity time from the session
            last_activity = request.session.get('last_activity')
            
            if last_activity:
                # Convert string time to datetime object if stored as string
                if isinstance(last_activity, str):
                    last_activity = timezone.datetime.fromisoformat(last_activity)
                
                # Calculate inactivity duration
                inactive_time = current_time - last_activity
                
                # Check if user has been inactive longer than the timeout period
                if inactive_time > timedelta(seconds=settings.SESSION_COOKIE_AGE):
                    # Log the user out
                    logout(request)
                    # Redirect to home page
                    return redirect('/')
            
            # Update last activity time
            request.session['last_activity'] = current_time.isoformat()

        response = self.get_response(request)
        return response 