"""
این ماژول شامل توابع و کلاس‌های مربوط به مدیریت سبد خرید در مارکت‌پلیس می‌باشد.
این ماژول امکان مشاهده، افزودن، ویرایش و حذف آیتم‌ها در سبد خرید کاربر را فراهم می‌کند.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import Cart, CartItem, Product
from ..serializers import CartSerializer, CartItemSerializer
import logging

# تنظیم لاگر
logger = logging.getLogger(__name__)


class CartView(APIView):
    """
    کلاس نمایش و مدیریت سبد خرید کاربر
    
    این کلاس امکان مشاهده سبد خرید فعال کاربر و انجام عملیات روی آن را فراهم می‌کند.
    """
    
    def get(self, request):
        """
        دریافت سبد خرید کاربر
        
        این متد سبد خرید فعال کاربر را به همراه تمام آیتم‌های آن برمی‌گرداند.
        
        فرآیند:
        1. بررسی وجود سبد خرید فعال برای کاربر
        2. دریافت سبد خرید به همراه آیتم‌های آن
        3. سریال‌سازی و برگرداندن اطلاعات سبد خرید
        
        ورودی:
            request: درخواست HTTP
            
        خروجی:
            پاسخ JSON شامل اطلاعات سبد خرید فعال کاربر و آیتم‌های آن
        """
        try:
            # دریافت کاربر جاری
            user = request.user
            
            # جستجوی سبد خرید فعال کاربر
            cart, created = Cart.objects.get_or_create(
                user=user,
                status='active',
                defaults={'created_by': user.username}
            )
            
            # سریال‌سازی و برگرداندن اطلاعات سبد خرید
            serializer = CartSerializer(cart)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"خطا در دریافت سبد خرید کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در دریافت سبد خرید: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CartItemView(APIView):
    """
    کلاس مدیریت آیتم‌های سبد خرید
    
    این کلاس امکان افزودن، ویرایش و حذف آیتم‌ها در سبد خرید کاربر را فراهم می‌کند.
    """
    
    def post(self, request):
        """
        افزودن محصول به سبد خرید
        
        این متد یک محصول را به سبد خرید فعال کاربر اضافه می‌کند.
        
        فرآیند:
        1. دریافت و اعتبارسنجی اطلاعات محصول و تعداد آن
        2. بررسی وجود سبد خرید فعال برای کاربر
        3. بررسی وجود محصول
        4. اضافه کردن یا به‌روزرسانی آیتم در سبد خرید
        5. برگرداندن اطلاعات به‌روز شده سبد خرید
        
        ورودی:
            request: درخواست HTTP شامل:
                - product_id: شناسه محصول (اجباری)
                - quantity: تعداد محصول (اجباری)
                
        خروجی:
            پاسخ JSON شامل اطلاعات به‌روز شده سبد خرید یا پیام خطا
        """
        try:
            # دریافت داده‌های ورودی
            product_id = request.data.get('product_id')
            quantity = request.data.get('quantity')
            
            # اعتبارسنجی داده‌های ورودی
            if not product_id:
                return Response({
                    'error': 'شناسه محصول الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            if not quantity or int(quantity) <= 0:
                return Response({
                    'error': 'تعداد محصول باید بیشتر از صفر باشد'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # دریافت کاربر جاری
            user = request.user
            
            # بررسی وجود محصول
            try:
                product = Product.objects.get(id=product_id)
                
                # بررسی فعال بودن محصول
                if product.status != 'active':
                    return Response({
                        'error': 'این محصول در حال حاضر قابل خرید نیست'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Product.DoesNotExist:
                return Response({
                    'error': f'محصول با شناسه {product_id} یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # دریافت یا ایجاد سبد خرید فعال کاربر
            cart, created = Cart.objects.get_or_create(
                user=user,
                status='active',
                defaults={'created_by': user.username}
            )
            
            # بررسی وجود آیتم مشابه در سبد خرید
            cart_item, item_created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={
                    'quantity': int(quantity),
                    'created_by': user.username
                }
            )
            
            # اگر آیتم از قبل وجود داشته، تعداد آن را به‌روزرسانی کنیم
            if not item_created:
                cart_item.quantity = int(quantity)
                cart_item.updated_by = user.username
                cart_item.save()
            
            # به‌روزرسانی مبلغ کل سبد خرید
            update_cart_total(cart)
            
            # برگرداندن اطلاعات به‌روز شده سبد خرید
            return Response(CartSerializer(cart).data)
            
        except Exception as e:
            logger.error(f"خطا در افزودن محصول به سبد خرید کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در افزودن محصول به سبد خرید: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    def put(self, request, item_id):
        """
        به‌روزرسانی تعداد یک آیتم در سبد خرید
        
        این متد تعداد یک آیتم موجود در سبد خرید کاربر را به‌روزرسانی می‌کند.
        
        فرآیند:
        1. دریافت و اعتبارسنجی تعداد جدید
        2. یافتن آیتم مورد نظر در سبد خرید کاربر
        3. به‌روزرسانی تعداد آیتم
        4. به‌روزرسانی مبلغ کل سبد خرید
        5. برگرداندن اطلاعات به‌روز شده سبد خرید
        
        ورودی:
            request: درخواست HTTP شامل:
                - quantity: تعداد جدید محصول (اجباری)
            item_id: شناسه آیتم در سبد خرید
            
        خروجی:
            پاسخ JSON شامل اطلاعات به‌روز شده سبد خرید یا پیام خطا
        """
        try:
            # دریافت داده‌های ورودی
            quantity = request.data.get('quantity')
            
            # اعتبارسنجی داده‌های ورودی
            if not quantity or int(quantity) < 0:
                return Response({
                    'error': 'تعداد محصول باید صفر یا بیشتر باشد'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # دریافت کاربر جاری
            user = request.user
            
            # یافتن آیتم مورد نظر در سبد خرید کاربر
            try:
                cart = Cart.objects.get(user=user, status='active')
                cart_item = CartItem.objects.get(id=item_id, cart=cart)
            except Cart.DoesNotExist:
                return Response({
                    'error': 'سبد خرید فعالی برای شما یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            except CartItem.DoesNotExist:
                return Response({
                    'error': f'آیتم با شناسه {item_id} در سبد خرید شما یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # اگر تعداد صفر باشد، آیتم را حذف می‌کنیم
            if int(quantity) == 0:
                cart_item.delete()
            else:
                # به‌روزرسانی تعداد آیتم
                cart_item.quantity = int(quantity)
                cart_item.updated_by = user.username
                cart_item.save()
            
            # به‌روزرسانی مبلغ کل سبد خرید
            update_cart_total(cart)
            
            # برگرداندن اطلاعات به‌روز شده سبد خرید
            return Response(CartSerializer(cart).data)
            
        except Exception as e:
            logger.error(f"خطا در به‌روزرسانی آیتم سبد خرید کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در به‌روزرسانی آیتم سبد خرید: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def delete(self, request, item_id):
        """
        حذف یک آیتم از سبد خرید
        
        این متد یک آیتم را از سبد خرید کاربر حذف می‌کند.
        
        فرآیند:
        1. یافتن آیتم مورد نظر در سبد خرید کاربر
        2. حذف آیتم از سبد خرید
        3. به‌روزرسانی مبلغ کل سبد خرید
        4. برگرداندن اطلاعات به‌روز شده سبد خرید
        
        ورودی:
            request: درخواست HTTP
            item_id: شناسه آیتم در سبد خرید
            
        خروجی:
            پاسخ JSON شامل اطلاعات به‌روز شده سبد خرید یا پیام خطا
        """
        try:
            # دریافت کاربر جاری
            user = request.user
            
            # یافتن آیتم مورد نظر در سبد خرید کاربر
            try:
                cart = Cart.objects.get(user=user, status='active')
                cart_item = CartItem.objects.get(id=item_id, cart=cart)
            except Cart.DoesNotExist:
                return Response({
                    'error': 'سبد خرید فعالی برای شما یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            except CartItem.DoesNotExist:
                return Response({
                    'error': f'آیتم با شناسه {item_id} در سبد خرید شما یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # ذخیره نام محصول قبل از حذف
            product_name = cart_item.product.name
            
            # حذف آیتم از سبد خرید
            cart_item.delete()
            
            # به‌روزرسانی مبلغ کل سبد خرید
            update_cart_total(cart)
            
            # برگرداندن پیام موفقیت و اطلاعات به‌روز شده سبد خرید
            response_data = CartSerializer(cart).data
            response_data['message'] = f'محصول "{product_name}" از سبد خرید حذف شد'
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"خطا در حذف آیتم از سبد خرید کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در حذف آیتم از سبد خرید: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def update_cart_total(cart):
    """
    به‌روزرسانی مبلغ کل سبد خرید
    
    این تابع مبلغ کل سبد خرید را بر اساس آیتم‌های موجود در آن محاسبه و به‌روزرسانی می‌کند.
    
    فرآیند:
    1. دریافت تمام آیتم‌های سبد خرید
    2. محاسبه مبلغ کل بر اساس قیمت و تعداد هر آیتم
    3. ذخیره مبلغ کل در سبد خرید
    
    ورودی:
        cart: شیء سبد خرید که باید مبلغ کل آن به‌روزرسانی شود
    """
    try:
        # دریافت تمام آیتم‌های سبد خرید
        cart_items = CartItem.objects.filter(cart=cart)
        
        # محاسبه مبلغ کل
        total_amount = sum(item.product.price * item.quantity for item in cart_items)
        
        # به‌روزرسانی مبلغ کل سبد خرید
        cart.total_amount = total_amount
        cart.save()
        
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی مبلغ کل سبد خرید: {str(e)}")
        # در اینجا استثنا را دوباره پرتاب می‌کنیم تا لایه بالاتر بتواند آن را مدیریت کند
        raise


def clear_cart(user):
    """
    پاک کردن سبد خرید کاربر
    
    این تابع تمام آیتم‌های موجود در سبد خرید فعال کاربر را حذف می‌کند.
    معمولاً پس از تکمیل سفارش استفاده می‌شود.
    
    فرآیند:
    1. یافتن سبد خرید فعال کاربر
    2. حذف تمام آیتم‌های موجود در سبد خرید
    3. صفر کردن مبلغ کل سبد خرید
    
    ورودی:
        user: کاربری که سبد خرید آن باید پاک شود
        
    خروجی:
        True در صورت موفقیت، False در صورت بروز خطا
    """
    try:
        # یافتن سبد خرید فعال کاربر
        try:
            cart = Cart.objects.get(user=user, status='active')
        except Cart.DoesNotExist:
            # اگر سبد خرید وجود نداشت، نیازی به پاک کردن نیست
            return True
        
        # حذف تمام آیتم‌های موجود در سبد خرید
        CartItem.objects.filter(cart=cart).delete()
        
        # صفر کردن مبلغ کل سبد خرید
        cart.total_amount = 0
        cart.save()
        
        return True
        
    except Exception as e:
        logger.error(f"خطا در پاک کردن سبد خرید کاربر {user.username}: {str(e)}")
        return False 