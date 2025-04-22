"""
این ماژول شامل توابع و کلاس‌های مربوط به مدیریت سفارش‌ها در مارکت‌پلیس می‌باشد.
این ماژول امکان ایجاد، مشاهده، پرداخت و پیگیری سفارش‌ها را فراهم می‌کند.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import Order, OrderItem, Product, Cart
from ..serializers import OrderSerializer, OrderItemSerializer
from .cart_view import clear_cart
import logging
import uuid
from django.utils import timezone

# تنظیم لاگر
logger = logging.getLogger(__name__)


class OrderView(APIView):
    """
    کلاس نمایش و مدیریت سفارش‌های کاربر
    
    این کلاس امکان ایجاد سفارش جدید، مشاهده سفارش‌های قبلی و پرداخت سفارش را فراهم می‌کند.
    """
    
    def get(self, request, order_id=None):
        """
        دریافت سفارش‌های کاربر
        
        این متد لیست سفارش‌های کاربر یا جزئیات یک سفارش خاص را برمی‌گرداند.
        
        فرآیند:
        1. اگر شناسه سفارش ارائه شده باشد، جزئیات آن سفارش را برمی‌گرداند
        2. در غیر این صورت، لیست تمام سفارش‌های کاربر را برمی‌گرداند
        
        ورودی:
            request: درخواست HTTP
            order_id (اختیاری): شناسه سفارش مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات سفارش‌ها یا جزئیات یک سفارش خاص
        """
        try:
            # دریافت کاربر جاری
            user = request.user
            
            # اگر شناسه سفارش ارائه شده باشد
            if order_id:
                try:
                    # دریافت سفارش مورد نظر
                    order = Order.objects.get(id=order_id, user=user)
                    serializer = OrderSerializer(order)
                    return Response(serializer.data)
                except Order.DoesNotExist:
                    return Response({
                        'error': f'سفارش با شناسه {order_id} یافت نشد'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                # دریافت تمام سفارش‌های کاربر
                orders = Order.objects.filter(user=user).order_by('-created_at')
                serializer = OrderSerializer(orders, many=True)
                return Response(serializer.data)
                
        except Exception as e:
            logger.error(f"خطا در دریافت سفارش‌های کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در دریافت سفارش‌ها: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request):
        """
        ایجاد سفارش جدید
        
        این متد یک سفارش جدید بر اساس محتویات سبد خرید فعال کاربر ایجاد می‌کند.
        
        فرآیند:
        1. بررسی وجود سبد خرید فعال و محتویات آن
        2. ایجاد سفارش جدید
        3. انتقال آیتم‌ها از سبد خرید به سفارش
        4. پاک کردن سبد خرید
        5. برگرداندن اطلاعات سفارش ایجاد شده
        
        ورودی:
            request: درخواست HTTP شامل:
                - delivery_address: آدرس تحویل سفارش (اجباری)
                - delivery_phone: شماره تماس برای تحویل (اجباری)
                - payment_method: روش پرداخت (اجباری)
                
        خروجی:
            پاسخ JSON شامل اطلاعات سفارش ایجاد شده یا پیام خطا
        """
        try:
            # دریافت داده‌های ورودی
            delivery_address = request.data.get('delivery_address')
            delivery_phone = request.data.get('delivery_phone')
            payment_method = request.data.get('payment_method')
            
            # اعتبارسنجی داده‌های ورودی
            if not delivery_address:
                return Response({
                    'error': 'آدرس تحویل الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not delivery_phone:
                return Response({
                    'error': 'شماره تماس برای تحویل الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not payment_method:
                return Response({
                    'error': 'روش پرداخت الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # دریافت کاربر جاری
            user = request.user
            
            # دریافت سبد خرید فعال کاربر
            try:
                cart = Cart.objects.get(user=user, status='active')
            except Cart.DoesNotExist:
                return Response({
                    'error': 'سبد خرید فعال یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # بررسی وجود آیتم در سبد خرید
            cart_items = cart.items.all()
            if not cart_items.exists():
                return Response({
                    'error': 'سبد خرید شما خالی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ایجاد کد پیگیری منحصر به فرد
            tracking_code = str(uuid.uuid4())[:8].upper()
            
            # ایجاد سفارش جدید
            order = Order.objects.create(
                user=user,
                total_amount=cart.total_amount,
                status='pending',
                tracking_code=tracking_code,
                delivery_address=delivery_address,
                delivery_phone=delivery_phone,
                payment_method=payment_method,
                created_by=user.username
            )
            
            # انتقال آیتم‌ها از سبد خرید به سفارش
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price=cart_item.product.price,
                    created_by=user.username
                )
            
            # پاک کردن سبد خرید
            clear_cart(user)
            
            # برگرداندن اطلاعات سفارش ایجاد شده
            serializer = OrderSerializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"خطا در ایجاد سفارش برای کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در ایجاد سفارش: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderPaymentView(APIView):
    """
    کلاس مدیریت پرداخت سفارش
    
    این کلاس امکان پرداخت سفارش و به‌روزرسانی وضعیت آن را فراهم می‌کند.
    """
    
    def post(self, request, order_id):
        """
        پرداخت سفارش
        
        این متد پرداخت سفارش را انجام می‌دهد و وضعیت آن را به‌روزرسانی می‌کند.
        
        فرآیند:
        1. دریافت و بررسی سفارش مورد نظر
        2. شبیه‌سازی پرداخت (در حالت واقعی با درگاه پرداخت ارتباط برقرار می‌شود)
        3. به‌روزرسانی وضعیت سفارش
        4. برگرداندن اطلاعات به‌روز شده سفارش
        
        ورودی:
            request: درخواست HTTP شامل:
                - payment_data: اطلاعات پرداخت (اختیاری)
            order_id: شناسه سفارش مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات به‌روز شده سفارش یا پیام خطا
        """
        try:
            # دریافت کاربر جاری
            user = request.user
            
            # دریافت سفارش مورد نظر
            try:
                order = Order.objects.get(id=order_id, user=user)
            except Order.DoesNotExist:
                return Response({
                    'error': f'سفارش با شناسه {order_id} یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # بررسی امکان پرداخت سفارش
            if order.status != 'pending':
                return Response({
                    'error': 'این سفارش قابل پرداخت نیست'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # در اینجا پرداخت واقعی با درگاه پرداخت انجام می‌شود
            # اما برای سادگی، فرض می‌کنیم پرداخت با موفقیت انجام شده است
            
            # به‌روزرسانی وضعیت سفارش
            order.status = 'paid'
            order.payment_date = timezone.now()
            order.updated_by = user.username
            order.save()
            
            # برگرداندن اطلاعات به‌روز شده سفارش
            serializer = OrderSerializer(order)
            return Response({
                'message': 'پرداخت با موفقیت انجام شد',
                'order': serializer.data
            })
            
        except Exception as e:
            logger.error(f"خطا در پرداخت سفارش {order_id} برای کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در پرداخت سفارش: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderCancelView(APIView):
    """
    کلاس لغو سفارش
    
    این کلاس امکان لغو سفارش توسط کاربر را فراهم می‌کند.
    """
    
    def post(self, request, order_id):
        """
        لغو سفارش
        
        این متد یک سفارش را لغو می‌کند.
        
        فرآیند:
        1. دریافت و بررسی سفارش مورد نظر
        2. بررسی امکان لغو سفارش (وضعیت سفارش)
        3. به‌روزرسانی وضعیت سفارش به 'لغو شده'
        4. برگرداندن اطلاعات به‌روز شده سفارش
        
        ورودی:
            request: درخواست HTTP
            order_id: شناسه سفارش مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات به‌روز شده سفارش یا پیام خطا
        """
        try:
            # دریافت کاربر جاری
            user = request.user
            
            # دریافت سفارش مورد نظر
            try:
                order = Order.objects.get(id=order_id, user=user)
            except Order.DoesNotExist:
                return Response({
                    'error': f'سفارش با شناسه {order_id} یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # بررسی امکان لغو سفارش
            if order.status in ['delivered', 'cancelled']:
                return Response({
                    'error': f'سفارش با وضعیت {order.status} قابل لغو نیست'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # به‌روزرسانی وضعیت سفارش
            order.status = 'cancelled'
            order.updated_by = user.username
            order.save()
            
            # برگرداندن اطلاعات به‌روز شده سفارش
            serializer = OrderSerializer(order)
            return Response({
                'message': 'سفارش با موفقیت لغو شد',
                'order': serializer.data
            })
            
        except Exception as e:
            logger.error(f"خطا در لغو سفارش {order_id} برای کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در لغو سفارش: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def update_order_status(order_id, new_status, updated_by):
    """
    به‌روزرسانی وضعیت سفارش
    
    این تابع وضعیت یک سفارش را به‌روزرسانی می‌کند.
    معمولاً توسط مدیر سیستم یا فرآیندهای خودکار استفاده می‌شود.
    
    فرآیند:
    1. دریافت سفارش مورد نظر
    2. بررسی معتبر بودن وضعیت جدید
    3. به‌روزرسانی وضعیت سفارش
    
    ورودی:
        order_id: شناسه سفارش
        new_status: وضعیت جدید سفارش
        updated_by: نام کاربری فردی که به‌روزرسانی را انجام می‌دهد
        
    خروجی:
        سفارش به‌روز شده در صورت موفقیت، None در صورت بروز خطا
    """
    try:
        # لیست وضعیت‌های مجاز
        valid_statuses = ['pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled']
        
        # بررسی معتبر بودن وضعیت جدید
        if new_status not in valid_statuses:
            logger.error(f"وضعیت نامعتبر {new_status} برای سفارش {order_id}")
            return None
        
        # دریافت سفارش مورد نظر
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            logger.error(f"سفارش با شناسه {order_id} یافت نشد")
            return None
        
        # به‌روزرسانی وضعیت سفارش
        order.status = new_status
        order.updated_by = updated_by
        order.save()
        
        # اگر وضعیت جدید 'تحویل شده' باشد، تاریخ تحویل را ثبت می‌کنیم
        if new_status == 'delivered':
            order.delivery_date = timezone.now()
            order.save()
        
        return order
        
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی وضعیت سفارش {order_id}: {str(e)}")
        return None


def get_order_stats(user=None, start_date=None, end_date=None):
    """
    دریافت آمار سفارش‌ها
    
    این تابع آمار و اطلاعات مربوط به سفارش‌ها را محاسبه و برمی‌گرداند.
    می‌تواند برای یک کاربر خاص یا همه کاربران استفاده شود.
    
    فرآیند:
    1. فیلتر کردن سفارش‌ها بر اساس پارامترهای ورودی
    2. محاسبه آمار مختلف مانند تعداد سفارش‌ها، مبلغ کل، توزیع وضعیت سفارش‌ها و ...
    
    ورودی:
        user (اختیاری): کاربر مورد نظر برای فیلتر کردن سفارش‌ها
        start_date (اختیاری): تاریخ شروع برای فیلتر کردن سفارش‌ها
        end_date (اختیاری): تاریخ پایان برای فیلتر کردن سفارش‌ها
        
    خروجی:
        دیکشنری شامل آمار و اطلاعات سفارش‌ها
    """
    try:
        # شروع با تمام سفارش‌ها
        orders = Order.objects.all()
        
        # فیلتر کردن بر اساس کاربر
        if user:
            orders = orders.filter(user=user)
        
        # فیلتر کردن بر اساس تاریخ
        if start_date:
            orders = orders.filter(created_at__gte=start_date)
        if end_date:
            orders = orders.filter(created_at__lte=end_date)
        
        # محاسبه آمار پایه
        total_orders = orders.count()
        total_amount = sum(order.total_amount for order in orders)
        avg_order_amount = total_amount / total_orders if total_orders > 0 else 0
        
        # محاسبه توزیع وضعیت سفارش‌ها
        status_distribution = {}
        for status_choice in ['pending', 'paid', 'processing', 'shipped', 'delivered', 'cancelled']:
            status_distribution[status_choice] = orders.filter(status=status_choice).count()
        
        # تجمیع نتایج
        stats = {
            'total_orders': total_orders,
            'total_amount': total_amount,
            'avg_order_amount': avg_order_amount,
            'status_distribution': status_distribution,
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"خطا در محاسبه آمار سفارش‌ها: {str(e)}")
        return None 