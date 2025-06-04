from django.contrib.auth import logout
from django.utils import timezone
from django.shortcuts import redirect
from datetime import timedelta
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse


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
    
# class RestrictAdminAccessMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         # اگر درخواست به مسیر /ewdfsrgtyuiougyjgtrdthugghuji/ یا زیرمسیرهای آن باشد
#         if request.path.startswith('/ewdfsrgtyuiougyjgtrdthugghuji/'):
#             # اگر کاربر لاگین نکرده یا سوپریوزر نیست، مستقیماً ریدایرکت شود
#             if not request.user.is_authenticated or not request.user.is_superuser:
#                 return HttpResponseRedirect(reverse('home_view'))
#             # اگر از مسیر درست نیامده باشد (یعنی admin_access_allowed در session نباشد)
#             if not request.session.get('admin_access_allowed', False):
#                 return HttpResponseRedirect(reverse('home_view'))

#         response = self.get_response(request)
#         return response