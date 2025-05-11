from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from CRM.views import home_view
from sms_api.views import sms_dashboard
from whatsapp_api.views import whatsapp_dashboard
from django.views.generic.base import RedirectView

urlpatterns = [
    path('ewdfsrgtyuiougyjgtrdthugghuji/', admin.site.urls),
    path('sales/', include('sales.urls')),
    path('chat/', include('chat.urls')),
    path('erp/', include('ERP.urls')),
    path('hr/', include('HR.urls')),
    path('sms/', include('sms_api.urls')),
    path('sms/dashborad', sms_dashboard, name='sms-dashboard'),
    path('', home_view.home_view, name='home_view'),
    path('login/', home_view.unified_login_view, name='unified_login'),
    
    # هدایت مسیرهای قدیمی به صفحه ورود جدید
    path('sales_agent_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    path('financial_manager_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    path('logistics_manager_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    path('support_agent_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    
    path('whatsapp/', include(('whatsapp_api.urls', 'whatsapp_api'), namespace='whatsapp_api')),
    path('whatsapp/', whatsapp_dashboard, name='whatsapp-dashboard'),
    path('bki/', include('bki_api.urls')),
]

# اضافه کردن URL های مربوط به media در حالت دیباگ
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
