"""
این ماژول شامل توابع و کلاس‌های مربوط به مدیریت مشتریان در مارکت‌پلیس می‌باشد.
توابع این ماژول امکان مشاهده، ایجاد، ویرایش و حذف اطلاعات مشتریان را فراهم می‌کنند.
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import Customer, User
from ..serializers import CustomerSerializer, CustomerListSerializer
import logging

logger = logging.getLogger(__name__)


class CustomerListView(APIView):
    """
    کلاس مدیریت لیست مشتریان
    
    این کلاس امکان دریافت لیست مشتریان و ایجاد مشتری جدید را فراهم می‌کند.
    """

    def get(self, request):
        """
        دریافت لیست مشتریان
        
        این متد لیست مشتریان را با امکان فیلتر کردن برمی‌گرداند.
        
        فرآیند:
        1. دریافت و بررسی پارامترهای فیلتر از درخواست
        2. اعمال فیلترها روی مجموعه مشتریان
        3. سریال‌سازی و برگرداندن نتایج
        
        ورودی:
            request: درخواست HTTP که می‌تواند شامل پارامترهای فیلتر باشد:
                - name: نام مشتری (جستجوی فازی)
                - email: ایمیل مشتری
                - phone: شماره تلفن مشتری
                - status: وضعیت مشتری
                - province: استان
        
        خروجی:
            پاسخ JSON شامل لیست مشتریان فیلتر شده
        """
        try:
            # دریافت تمام مشتریان
            customers = Customer.objects.all()
            
            # فیلتر بر اساس پارامترهای موجود در درخواست
            name = request.query_params.get('name')
            if name:
                customers = customers.filter(name__icontains=name)
            
            email = request.query_params.get('email')
            if email:
                customers = customers.filter(email__icontains=email)
            
            phone = request.query_params.get('phone')
            if phone:
                customers = customers.filter(phone__icontains=phone)
            
            status_param = request.query_params.get('status')
            if status_param:
                customers = customers.filter(status=status_param)
            
            province = request.query_params.get('province')
            if province:
                customers = customers.filter(province=province)
            
            # سریال‌سازی و برگرداندن نتایج
            serializer = CustomerListSerializer(customers, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"خطا در دریافت لیست مشتریان: {str(e)}")
            return Response(
                {"error": f"خطا در دریافت لیست مشتریان: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request):
        """
        ایجاد مشتری جدید
        
        این متد یک مشتری جدید را با استفاده از داده‌های ارائه شده در درخواست ایجاد می‌کند.
        
        فرآیند:
        1. دریافت و اعتبارسنجی داده‌های مشتری
        2. ایجاد مشتری جدید
        3. برگرداندن اطلاعات مشتری ایجاد شده
        
        ورودی:
            request: درخواست HTTP شامل داده‌های مشتری:
                - name: نام مشتری
                - email: ایمیل مشتری
                - phone: شماره تلفن مشتری
                - address: آدرس مشتری
                - province: استان
                - city: شهر
                - postal_code: کد پستی
        
        خروجی:
            پاسخ JSON شامل اطلاعات مشتری ایجاد شده یا پیام خطا
        """
        try:
            # دریافت داده‌های مشتری
            data = request.data
            
            # بررسی وجود مشتری با ایمیل یکسان
            email = data.get('email')
            if email and Customer.objects.filter(email=email).exists():
                return Response(
                    {"error": f"مشتری با ایمیل {email} قبلاً در سیستم ثبت شده است"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # بررسی وجود مشتری با شماره تلفن یکسان
            phone = data.get('phone')
            if phone and Customer.objects.filter(phone=phone).exists():
                return Response(
                    {"error": f"مشتری با شماره تلفن {phone} قبلاً در سیستم ثبت شده است"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # سریال‌سازی و اعتبارسنجی داده‌ها
            serializer = CustomerSerializer(data=data)
            if serializer.is_valid():
                # ذخیره مشتری جدید
                customer = serializer.save()
                
                # برگرداندن اطلاعات مشتری ایجاد شده
                return Response(
                    CustomerSerializer(customer).data,
                    status=status.HTTP_201_CREATED
                )
            else:
                # برگرداندن خطاهای اعتبارسنجی
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"خطا در ایجاد مشتری جدید: {str(e)}")
            return Response(
                {"error": f"خطا در ایجاد مشتری: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomerDetailView(APIView):
    """
    کلاس مدیریت جزئیات مشتری
    
    این کلاس امکان مشاهده، ویرایش و حذف یک مشتری خاص را فراهم می‌کند.
    """
    
    def get(self, request, customer_id):
        """
        دریافت اطلاعات یک مشتری
        
        این متد جزئیات کامل یک مشتری را بر اساس شناسه آن برمی‌گرداند.
        
        فرآیند:
        1. یافتن مشتری با شناسه مشخص شده
        2. سریال‌سازی و برگرداندن اطلاعات مشتری
        
        ورودی:
            request: درخواست HTTP
            customer_id: شناسه مشتری
        
        خروجی:
            پاسخ JSON شامل اطلاعات کامل مشتری یا پیام خطا
        """
        try:
            # یافتن مشتری با شناسه مشخص شده
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return Response(
                    {"error": f"مشتری با شناسه {customer_id} یافت نشد"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # سریال‌سازی و برگرداندن اطلاعات مشتری
            serializer = CustomerSerializer(customer)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"خطا در دریافت اطلاعات مشتری با شناسه {customer_id}: {str(e)}")
            return Response(
                {"error": f"خطا در دریافت اطلاعات مشتری: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, customer_id):
        """
        بروزرسانی اطلاعات یک مشتری
        
        این متد اطلاعات یک مشتری موجود را با استفاده از داده‌های ارائه شده در درخواست بروزرسانی می‌کند.
        
        فرآیند:
        1. یافتن مشتری با شناسه مشخص شده
        2. دریافت و اعتبارسنجی داده‌های جدید
        3. بروزرسانی اطلاعات مشتری
        4. برگرداندن اطلاعات بروزرسانی شده مشتری
        
        ورودی:
            request: درخواست HTTP شامل داده‌های جدید مشتری
            customer_id: شناسه مشتری
        
        خروجی:
            پاسخ JSON شامل اطلاعات بروزرسانی شده مشتری یا پیام خطا
        """
        try:
            # یافتن مشتری با شناسه مشخص شده
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return Response(
                    {"error": f"مشتری با شناسه {customer_id} یافت نشد"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # دریافت داده‌های جدید
            data = request.data
            
            # بررسی یکتا بودن ایمیل در صورت تغییر
            email = data.get('email')
            if email and email != customer.email and Customer.objects.filter(email=email).exists():
                return Response(
                    {"error": f"مشتری دیگری با ایمیل {email} در سیستم ثبت شده است"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # بررسی یکتا بودن شماره تلفن در صورت تغییر
            phone = data.get('phone')
            if phone and phone != customer.phone and Customer.objects.filter(phone=phone).exists():
                return Response(
                    {"error": f"مشتری دیگری با شماره تلفن {phone} در سیستم ثبت شده است"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # سریال‌سازی و اعتبارسنجی داده‌ها
            serializer = CustomerSerializer(customer, data=data, partial=True)
            if serializer.is_valid():
                # ذخیره تغییرات مشتری
                updated_customer = serializer.save()
                
                # برگرداندن اطلاعات بروزرسانی شده مشتری
                return Response(CustomerSerializer(updated_customer).data)
            else:
                # برگرداندن خطاهای اعتبارسنجی
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"خطا در بروزرسانی مشتری با شناسه {customer_id}: {str(e)}")
            return Response(
                {"error": f"خطا در بروزرسانی مشتری: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, customer_id):
        """
        حذف یک مشتری
        
        این متد یک مشتری را بر اساس شناسه آن حذف می‌کند.
        
        فرآیند:
        1. یافتن مشتری با شناسه مشخص شده
        2. حذف مشتری
        3. برگرداندن تأییدیه حذف
        
        ورودی:
            request: درخواست HTTP
            customer_id: شناسه مشتری
        
        خروجی:
            پاسخ JSON حاوی تأییدیه حذف یا پیام خطا
        """
        try:
            # یافتن مشتری با شناسه مشخص شده
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return Response(
                    {"error": f"مشتری با شناسه {customer_id} یافت نشد"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # حذف مشتری
            customer_name = customer.name  # ذخیره نام مشتری قبل از حذف
            customer.delete()
            
            # برگرداندن تأییدیه حذف
            return Response({
                "message": f"مشتری '{customer_name}' با موفقیت حذف شد"
            })
            
        except Exception as e:
            logger.error(f"خطا در حذف مشتری با شناسه {customer_id}: {str(e)}")
            return Response(
                {"error": f"خطا در حذف مشتری: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
def get_customer_stats(request):
    """
    دریافت آمار مشتریان
    
    این تابع آمار کلی در مورد مشتریان را محاسبه و برمی‌گرداند،
    شامل تعداد کل مشتریان، آمار بر اساس استان و وضعیت.
    
    فرآیند:
    1. محاسبه تعداد کل مشتریان
    2. محاسبه تعداد مشتریان در هر استان
    3. محاسبه تعداد مشتریان در هر وضعیت
    
    خروجی:
        دیکشنری شامل آمار مشتریان
    """
    try:
        # محاسبه تعداد کل مشتریان
        total_customers = Customer.objects.count()
        
        # محاسبه آمار مشتریان بر اساس استان
        province_stats = {}
        provinces = Customer.objects.values_list('province', flat=True).distinct()
        for province in provinces:
            if province:  # اطمینان از خالی نبودن استان
                count = Customer.objects.filter(province=province).count()
                province_stats[province] = count
        
        # محاسبه آمار مشتریان بر اساس وضعیت
        status_stats = {}
        statuses = Customer.objects.values_list('status', flat=True).distinct()
        for status_value in statuses:
            count = Customer.objects.filter(status=status_value).count()
            status_stats[status_value] = count
        
        # برگرداندن آمار کلی
        return Response({
            'total_customers': total_customers,
            'by_province': province_stats,
            'by_status': status_stats
        })
        
    except Exception as e:
        logger.error(f"خطا در محاسبه آمار مشتریان: {str(e)}")
        return Response(
            {"error": f"خطا در محاسبه آمار مشتریان: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def link_customer_with_user(customer_id, user_id):
    """
    پیوند مشتری با کاربر
    
    این تابع یک مشتری را به یک کاربر پیوند می‌دهد تا امکان احراز هویت و دسترسی به سیستم را فراهم کند.
    
    فرآیند:
    1. یافتن مشتری و کاربر با شناسه‌های مشخص شده
    2. برقراری پیوند بین مشتری و کاربر
    3. برگرداندن اطلاعات مشتری به‌روزرسانی شده
    
    ورودی:
        customer_id: شناسه مشتری
        user_id: شناسه کاربر
    
    خروجی:
        دیکشنری شامل اطلاعات مشتری به‌روزرسانی شده یا پیام خطا
    """
    try:
        # یافتن مشتری با شناسه مشخص شده
        try:
            customer = Customer.objects.get(id=customer_id)
        except Customer.DoesNotExist:
            return {
                'error': f"مشتری با شناسه {customer_id} یافت نشد"
            }, 404
        
        # یافتن کاربر با شناسه مشخص شده
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {
                'error': f"کاربر با شناسه {user_id} یافت نشد"
            }, 404
        
        # بررسی استفاده قبلی از کاربر برای مشتری دیگر
        if Customer.objects.filter(user_id=user_id).exclude(id=customer_id).exists():
            return {
                'error': f"کاربر با شناسه {user_id} قبلاً به مشتری دیگری پیوند خورده است"
            }, 400
        
        # پیوند مشتری با کاربر
        customer.user = user
        customer.save()
        
        # برگرداندن اطلاعات مشتری به‌روزرسانی شده
        return {
            'message': f"مشتری '{customer.name}' با موفقیت به کاربر پیوند خورد",
            'customer': CustomerSerializer(customer).data
        }, 200
        
    except Exception as e:
        logger.error(f"خطا در پیوند مشتری با کاربر: {str(e)}")
        return {
            'error': f"خطا در پیوند مشتری با کاربر: {str(e)}"
        }, 500 