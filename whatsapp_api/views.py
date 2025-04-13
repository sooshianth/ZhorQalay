from django.http import HttpResponse
from core._models import Customer
from whatsapp_api.utils import send_whatsapp_message

def test_whatsapp_sending(request):
    results = []
    customers = Customer.objects.filter(whatsapp_preference=True)[:10]  # 10 مشتری اول
    
    for customer in customers:
        success = send_whatsapp_message(customer)
        results.append(f"{customer.phone_number}: {'✅ موفق' if success else '❌ ناموفق'}")
    
    return HttpResponse("<br>".join(results))