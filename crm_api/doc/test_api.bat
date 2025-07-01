@echo off
chcp 65001 >nul
echo ===================================
echo        تست CRM API - نسخه 2.0
echo ===================================
echo.

echo 1. تست بررسی سلامت سرویس:
echo -----------------------------------
curl -X GET "http://127.0.0.1:8000/crm-api/health/" ^
  -H "Accept: application/json"
echo.
echo.

echo 2. تست احراز هویت شماره تلفن:
echo -----------------------------------
echo شماره تلفن معتبر:
curl -X POST "http://127.0.0.1:8000/crm-api/phone-validation/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\"}"
echo.
echo.

echo شماره تلفن نامعتبر:
curl -X POST "http://127.0.0.1:8000/crm-api/phone-validation/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09999999999\"}"
echo.
echo.

echo 3. تست دریافت لیست خریدهای مشتری:
echo -----------------------------------
echo شماره تلفن معتبر:
curl -X POST "http://127.0.0.1:8000/crm-api/customer-purchases/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\"}"
echo.
echo.

echo شماره تلفن نامعتبر:
curl -X POST "http://127.0.0.1:8000/crm-api/customer-purchases/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09999999999\"}"
echo.
echo.

echo 4. تست دریافت اطلاعات یک خرید خاص:
echo -----------------------------------
echo خرید معتبر:
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\", \"purchase_number\": \"2148123\"}"
echo.
echo.

echo خرید نامعتبر:
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\", \"purchase_number\": \"9999999\"}"
echo.
echo.

echo عدم دسترسی:
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09999999999\", \"purchase_number\": \"2148123\"}"
echo.
echo.

echo 5. تست پارامترهای ناقص:
echo -----------------------------------
echo بدون شماره تلفن:
curl -X POST "http://127.0.0.1:8000/crm-api/customer-purchases/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{}"
echo.
echo.

echo بدون شماره خرید:
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\"}"
echo.
echo.

echo 6. تست فرمت JSON نامعتبر:
echo -----------------------------------
curl -X POST "http://127.0.0.1:8000/crm-api/phone-validation/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "invalid_json"
echo.
echo.

echo ===================================
echo       تست کامل شد! 
echo   چک کنید که همه API ها درست کار کنند
echo ===================================
pause 