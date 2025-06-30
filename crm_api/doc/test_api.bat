@echo off
chcp 65001 >nul
echo === Test CRM API ===
echo.
echo 1. تست دریافت اطلاعات خرید:
echo.

rem تست دریافت اطلاعات خرید
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\", \"purchase_number\": \"2148123\"}"

echo.
echo.
echo 2. تست دریافت لیست خریدهای مشتری:
echo.

rem تست دریافت لیست خریدها
curl -X POST "http://127.0.0.1:8000/crm-api/customer-purchases/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\"}"

echo.
echo.
echo 3. تست با شماره نامعتبر:
echo.

rem تست با شماره نامعتبر
curl -X POST "http://127.0.0.1:8000/crm-api/purchase-info/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09999999999\", \"purchase_number\": \"9999999\"}"

echo.
echo.
echo تست کامل شد!
pause 