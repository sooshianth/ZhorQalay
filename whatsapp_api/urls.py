from django.urls import path
from . import views

urlpatterns = [
    path("send/<int:customer_id>/", views.send_message_to_customer),
]
