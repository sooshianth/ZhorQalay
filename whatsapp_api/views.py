# whatsapp_api/views.py
from django.http import JsonResponse
from core._models import Customer
from .utils import send_whatsapp_message

def send_message_to_customer(request, customer_id):
    try:
        customer = Customer.objects.get(id=customer_id)
        success = send_whatsapp_message(customer)
        return JsonResponse({"status": "success" if success else "failed"})
    except Customer.DoesNotExist:
        return JsonResponse({"status": "not found"})
