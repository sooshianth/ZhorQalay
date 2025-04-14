from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from crm.views import home_view
from sms_api.views import sms_dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sales/', include('sales.urls')),
    path('crm/', include('crm.urls')),
    path('excel/', include('excel_manager.urls')),
    path('sms/', include('sms_api.urls')),
    path('sms/dashborad', sms_dashboard, name='sms-dashboard'),
    path('', home_view.home_view, name='home_view'),
]

# اضافه کردن URL های مربوط به media در حالت دیباگ
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
