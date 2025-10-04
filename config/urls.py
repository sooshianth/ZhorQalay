from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from authentication.views import home_view
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
    path('todo/', include('todo.urls')),
    path('cargos/', include('bki_cargos.urls')),
    path('bki/', include('bki_api.urls')),
    path('bki/barnameh/', include('bki_barnameh.urls')),
    path('whatsapp/', include(('whatsapp_api.urls', 'whatsapp_api'), namespace='whatsapp_api')),
    path('data-exflow/', include('data_exflow.urls')),
    path('table_filter/', include('table_filter.urls')),
    path('fledger/', include(('fledger.urls', 'fledger'), namespace='fledger')),
    path('crm-api/', include('crm_api.urls')),
    path('major/', include('major.urls')),
    path('proforma/', include('proforma_invoice.urls')),
    path('', include('authentication.urls')),
    # هدایت مسیرهای قدیمی به صفحه ورود جدید
    path('sales_agent_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    path('financial_manager_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    path('logistics_manager_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    path('support_agent_login/', RedirectView.as_view(pattern_name='unified_login', permanent=True)),
    
    path('whatsapp/', whatsapp_dashboard, name='whatsapp-dashboard'),
    path('sms/dashborad', sms_dashboard, name='sms-dashboard'),
]

# اضافه کردن URL های مربوط به media در حالت دیباگ
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
