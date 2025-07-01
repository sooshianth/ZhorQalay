#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
نمونه ساده استفاده از CRM API
=============================
"""

import requests

# آدرس API
API_BASE = "http://127.0.0.1:8000/crm-api"

# شماره تلفن مشتری
phone_number = "09132017353"

# 1. بررسی اعتبار شماره تلفن
response = requests.post(f"{API_BASE}/phone-validation/", 
                        json={"phone_number": phone_number})
result = response.json()

if result['success'] and result['data']['has_access']:
    print(f"✅ شماره معتبر است - {len(result['data']['customers'])} مشتری")
    
    # 2. دریافت لیست خریدها
    response = requests.post(f"{API_BASE}/customer-purchases/", 
                            json={"phone_number": phone_number})
    purchases = response.json()
    
    if purchases['success']:
        print(f"🛒 {purchases['data']['total_purchases']} خرید یافت شد")
        
        # 3. نمایش همه خریدها
        for i, purchase in enumerate(purchases['data']['purchases'], 1):
            print(f"\n📦 خرید {i}: {purchase['purchase_number']}")
            print(f"   📅 تاریخ: {purchase['created_at']}")
            print(f"   📊 وضعیت: {purchase['state_display']}")
            print(f"   ⚖️ وزن سفارش: {purchase['order_weight']:,} کیلوگرم")
            print(f"   ⚖️ وزن تحویلی: {purchase['delivered_weight']:,} کیلوگرم")
            print(f"   💰 مبلغ: {purchase['amount_paid']:,} ریال")
            print(f"   🏷️ کوتاژ: {purchase['cargo_cottage']}")
            print(f"   🔑 نوع دسترسی: {', '.join(purchase['access_types'])}")
            
            # جزئیات بیشتر برای هر خرید
            detail_response = requests.post(f"{API_BASE}/purchase-info/", 
                                          json={"phone_number": phone_number, 
                                                "purchase_number": purchase['purchase_number']})
            details = detail_response.json()
            
            if details['success']:
                detail = details['data']['purchase']
                print(f"   👤 خریدار: {detail['buyer_name']}")
                print(f"   📱 تلفن بازارگاه: {detail['bazaargah_phone_number']}")
                print(f"   📱 تلفن تحویل: {detail['tahvil_phone_number']}")
                if detail['cargo']:
                    print(f"   🌾 محصول: {detail['cargo']['product_type_display']} {detail['cargo']['country_display']}")
                if detail['extelaf_weight']:
                    print(f"   ⚠️ اختلاف: {detail['extelaf_type']} - {detail['extelaf_weight']:,} کیلوگرم")
    else:
        print(f"❌ خطا: {purchases['error']}")
else:
    print("❌ شماره تلفن معتبر نیست")