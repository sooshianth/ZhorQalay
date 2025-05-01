from django.urls import path
from django.views.generic.base import RedirectView


from .views import (
    cargo_product_view,
    managers_login,
    managers_logout, 
    purchase_CRUD_view, 
    managers_profile_view, 
    purchase_list_view,
    notification_view,
)

urlpatterns = [
    path('cargo_products/', cargo_product_view.cargo_product_list, name='cargo_product_list'),
    path('financial_manager_login/', managers_login.financial_manager_login_view, name='financial_manager_login'),
    path('logistics_manager_login/', managers_login.logistics_manager_login_view, name='logistics_manager_login'),
    path('support_agent_login/', managers_login.support_agent_login_view, name='support_agent_login'),
    path('logout/', managers_logout.logout_view, name='logout'),

    path('logistics_manager_profile/', managers_profile_view.logistics_manager_profile_view, name='logistics_manager_profile'),
    path('financial_manager_profile/', managers_profile_view.financial_manager_profile_view, name='financial_manager_profile'),
    path('support_agent_profile/', managers_profile_view.support_agent_profile_view, name='support_agent_profile'),

    path('purchase_list/', purchase_list_view.purchase_list, name='purchase_list' ),

    path('purchase_CRUD/<int:purchase_id>/', purchase_CRUD_view.purchase_CRUD_view, name='purchase_CRUD'),
    path('purchase_delete/<int:purchase_id>/', purchase_CRUD_view.delete_purchase_view, name='purchase_delete' ),
    path('purchase_pdf/<int:purchase_id>/', purchase_CRUD_view.generate_purchase_pdf, name='purchase_pdf'),
    path('upload_purchase_document/<int:purchase_id>/', purchase_CRUD_view.upload_purchase_document, name='upload_purchase_document'),

    path('purchase_CRUD/notifications/', notification_view.get_notifications, name='get_notifications'),
    path('purchase_CRUD/notifications/<int:notification_id>/read/', notification_view.mark_notification_read, name='mark_notification_read'),


]