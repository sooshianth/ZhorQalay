import requests

# مثال اتصال از سرور CRM
response = requests.post(
    'http://127.0.0.1:8000/crm-api/purchase-info/',
    json={
        'phone_number': '09132017353',
        'purchase_number': '2148123'
    }
)

data = response.json()
if data['success']:
    purchase_info = data['data']['purchase']
    customer_info = data['data']['customer']
    # استفاده از داده‌ها...