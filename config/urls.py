from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from crm.views import home_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sales/', include('sales.urls')),
    path('crm/', include('crm.urls')),
    path('excel/', include('excel_manager.urls')),
    path('sms_api/', include('sms_api.urls')),
    path('', home_view.home_view, name='home_view'),
]

# اضافه کردن URL های مربوط به media در حالت دیباگ
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
