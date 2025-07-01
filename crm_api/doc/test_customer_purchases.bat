@echo off
chcp 65001 >nul
echo ===================================
echo   تست فقط Customer Purchases API
echo ===================================
echo.

echo تست دریافت لیست خریدهای مشتری:
echo -----------------------------------
curl -X POST "http://127.0.0.1:8000/crm-api/customer-purchases/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\"}"
echo.
echo.

echo تست احراز هویت شماره تلفن:
echo -----------------------------------
curl -X POST "http://127.0.0.1:8000/crm-api/phone-validation/" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json" ^
  -d "{\"phone_number\": \"09132017353\"}"
echo.
echo.

echo ===================================
echo       تست کامل شد!
echo ===================================
pause 