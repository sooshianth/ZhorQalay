from django.urls import path
from . import views

urlpatterns = [
    path('', views.barnameh_list, name='barnameh_list'),
    path('detail/<int:barnameh_id>/', views.barnameh_detail, name='barnameh_detail'),
    path('create/', views.barnameh_create, name='barnameh_create'),
    path('edit/<int:barnameh_id>/', views.barnameh_edit, name='barnameh_edit'),
    path('delete/<int:barnameh_id>/', views.barnameh_delete, name='barnameh_delete'),
    path('upload-excel/', views.upload_excel, name='upload_excel'),
    path('send-to-bki/<int:barnameh_id>/', views.send_to_bki, name='send_to_bki'),
    path('bulk-send-to-bki/', views.bulk_send_to_bki, name='bulk_send_to_bki'),
    path('api/', views.barnameh_api, name='barnameh_api'),
    path('download-excel-template/', views.download_excel_template, name='download_excel_template'),
]

