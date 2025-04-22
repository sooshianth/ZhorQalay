"""
این ماژول شامل توابع و کلاس‌های مربوط به مدیریت محصولات در مارکت‌پلیس می‌باشد.
این ماژول امکان مشاهده، جستجو، فیلتر و دریافت جزئیات محصولات را فراهم می‌کند.
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ..models import Product, ProductCategoryDL, ProductCategory, Category, Review
from ..serializers import ProductSerializer, ProductListSerializer, ReviewSerializer
import logging
from django.db.models import Q, Avg

logger = logging.getLogger(__name__)


class ProductView(APIView):
    """
    کلاس نمایش و مدیریت محصولات
    
    این کلاس امکان مشاهده لیست محصولات، فیلتر کردن، جستجو و دریافت جزئیات محصولات را فراهم می‌کند.
    """
    
    def get(self, request, product_id=None):
        """
        دریافت محصولات
        
        این متد لیست محصولات یا جزئیات یک محصول خاص را برمی‌گرداند.
        همچنین امکان فیلتر کردن محصولات بر اساس دسته‌بندی، قیمت و کلمات کلیدی را فراهم می‌کند.
        
        فرآیند:
        1. اگر شناسه محصول ارائه شده باشد، جزئیات آن محصول را برمی‌گرداند
        2. در غیر این صورت، لیست محصولات را با توجه به فیلترهای ارائه شده برمی‌گرداند
        
        ورودی:
            request: درخواست HTTP شامل پارامترهای زیر:
                - category_id: شناسه دسته‌بندی (اختیاری)
                - min_price: حداقل قیمت (اختیاری)
                - max_price: حداکثر قیمت (اختیاری)
                - search: کلمات کلیدی جستجو (اختیاری)
                - sort_by: معیار مرتب‌سازی (اختیاری)
            product_id (اختیاری): شناسه محصول مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات محصولات یا جزئیات یک محصول خاص
        """
        try:
            # اگر شناسه محصول ارائه شده باشد
            if product_id:
                try:
                    # دریافت محصول مورد نظر
                    product = Product.objects.get(id=product_id, is_active=True)
                    serializer = ProductSerializer(product)
                    
                    # افزایش تعداد بازدیدها
                    product.view_count += 1
                    product.save()
                    
                    return Response(serializer.data)
                except Product.DoesNotExist:
                    return Response({
                        'error': f'محصول با شناسه {product_id} یافت نشد'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            # دریافت پارامترهای فیلتر
            category_id = request.query_params.get('category_id')
            min_price = request.query_params.get('min_price')
            max_price = request.query_params.get('max_price')
            search_query = request.query_params.get('search')
            sort_by = request.query_params.get('sort_by', 'created_at')
            
            # شروع با تمام محصولات فعال
            products = Product.objects.filter(is_active=True)
            
            # فیلتر بر اساس دسته‌بندی
            if category_id:
                products = products.filter(category_id=category_id)
            
            # فیلتر بر اساس قیمت
            if min_price:
                products = products.filter(price__gte=float(min_price))
            if max_price:
                products = products.filter(price__lte=float(max_price))
            
            # جستجو در نام و توضیحات محصول
            if search_query:
                products = products.filter(
                    Q(name__icontains=search_query) | Q(description__icontains=search_query)
                )
            
            # مرتب‌سازی
            if sort_by == 'price_asc':
                products = products.order_by('price')
            elif sort_by == 'price_desc':
                products = products.order_by('-price')
            elif sort_by == 'newest':
                products = products.order_by('-created_at')
            elif sort_by == 'popularity':
                products = products.order_by('-view_count')
            
            # سریالایز کردن نتایج
            serializer = ProductSerializer(products, many=True)
            return Response({
                'count': products.count(),
                'results': serializer.data
            })
            
        except Exception as e:
            logger.error(f"خطا در دریافت محصولات: {str(e)}")
            return Response({
                'error': f'خطا در دریافت محصولات: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CategoryProductsView(APIView):
    """
    کلاس نمایش محصولات یک دسته‌بندی خاص
    
    این کلاس امکان مشاهده محصولات یک دسته‌بندی خاص را فراهم می‌کند.
    """
    
    def get(self, request, category_id):
        """
        دریافت محصولات یک دسته‌بندی
        
        این متد لیست محصولات یک دسته‌بندی خاص را برمی‌گرداند.
        
        فرآیند:
        1. دریافت دسته‌بندی مورد نظر
        2. دریافت محصولات آن دسته‌بندی
        3. برگرداندن لیست محصولات
        
        ورودی:
            request: درخواست HTTP
            category_id: شناسه دسته‌بندی مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات محصولات آن دسته‌بندی
        """
        try:
            # بررسی وجود دسته‌بندی
            try:
                category = Category.objects.get(id=category_id)
            except Category.DoesNotExist:
                return Response({
                    'error': f'دسته‌بندی با شناسه {category_id} یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # دریافت محصولات دسته‌بندی
            products = Product.objects.filter(category=category, is_active=True).order_by('-created_at')
            
            # سریالایز کردن نتایج
            serializer = ProductSerializer(products, many=True)
            return Response({
                'category': category.name,
                'count': products.count(),
                'products': serializer.data
            })
            
        except Exception as e:
            logger.error(f"خطا در دریافت محصولات دسته‌بندی {category_id}: {str(e)}")
            return Response({
                'error': f'خطا در دریافت محصولات دسته‌بندی: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductReviewView(APIView):
    """
    کلاس مدیریت نظرات محصول
    
    این کلاس امکان ثبت، مشاهده و مدیریت نظرات کاربران برای محصولات را فراهم می‌کند.
    """
    
    def get(self, request, product_id):
        """
        دریافت نظرات یک محصول
        
        این متد لیست نظرات ثبت شده برای یک محصول خاص را برمی‌گرداند.
        
        فرآیند:
        1. دریافت محصول مورد نظر
        2. دریافت نظرات آن محصول
        3. برگرداندن لیست نظرات
        
        ورودی:
            request: درخواست HTTP
            product_id: شناسه محصول مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات نظرات آن محصول
        """
        try:
            # بررسی وجود محصول
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except Product.DoesNotExist:
                return Response({
                    'error': f'محصول با شناسه {product_id} یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # دریافت نظرات محصول
            reviews = Review.objects.filter(product=product, is_approved=True).order_by('-created_at')
            
            # محاسبه میانگین امتیازات
            avg_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
            
            # سریالایز کردن نتایج
            serializer = ReviewSerializer(reviews, many=True)
            return Response({
                'product_id': product.id,
                'product_name': product.name,
                'avg_rating': avg_rating,
                'review_count': reviews.count(),
                'reviews': serializer.data
            })
            
        except Exception as e:
            logger.error(f"خطا در دریافت نظرات محصول {product_id}: {str(e)}")
            return Response({
                'error': f'خطا در دریافت نظرات محصول: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, product_id):
        """
        ثبت نظر جدید برای محصول
        
        این متد یک نظر جدید برای محصول ثبت می‌کند.
        
        فرآیند:
        1. دریافت محصول مورد نظر
        2. دریافت و اعتبارسنجی داده‌های نظر
        3. ثبت نظر جدید
        4. برگرداندن اطلاعات نظر ثبت شده
        
        ورودی:
            request: درخواست HTTP شامل:
                - rating: امتیاز (اجباری)
                - comment: متن نظر (اجباری)
            product_id: شناسه محصول مورد نظر
            
        خروجی:
            پاسخ JSON شامل اطلاعات نظر ثبت شده یا پیام خطا
        """
        try:
            # دریافت کاربر جاری
            user = request.user
            
            # بررسی وجود محصول
            try:
                product = Product.objects.get(id=product_id, is_active=True)
            except Product.DoesNotExist:
                return Response({
                    'error': f'محصول با شناسه {product_id} یافت نشد'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # دریافت داده‌های ورودی
            rating = request.data.get('rating')
            comment = request.data.get('comment')
            
            # اعتبارسنجی داده‌های ورودی
            if not rating:
                return Response({
                    'error': 'امتیاز الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if not comment:
                return Response({
                    'error': 'متن نظر الزامی است'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # تبدیل امتیاز به عدد
            try:
                rating = int(rating)
                if rating < 1 or rating > 5:
                    return Response({
                        'error': 'امتیاز باید بین 1 تا 5 باشد'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except (ValueError, TypeError):
                return Response({
                    'error': 'امتیاز باید یک عدد باشد'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # بررسی وجود نظر قبلی
            if Review.objects.filter(product=product, user=user).exists():
                return Response({
                    'error': 'شما قبلاً برای این محصول نظر ثبت کرده‌اید'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # ایجاد نظر جدید
            review = Review.objects.create(
                product=product,
                user=user,
                rating=rating,
                comment=comment,
                is_approved=False,  # نظر نیاز به تأیید دارد
                created_by=user.username
            )
            
            # سریالایز کردن نتیجه
            serializer = ReviewSerializer(review)
            return Response({
                'message': 'نظر شما با موفقیت ثبت شد و پس از تأیید نمایش داده خواهد شد',
                'review': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"خطا در ثبت نظر برای محصول {product_id} توسط کاربر {request.user.username}: {str(e)}")
            return Response({
                'error': f'خطا در ثبت نظر: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def get_related_products(product_id, limit=4):
    """
    دریافت محصولات مرتبط
    
    این تابع محصولات مرتبط با یک محصول خاص را برمی‌گرداند.
    معمولاً محصولات مرتبط، محصولات هم‌دسته یا مشابه هستند.
    
    فرآیند:
    1. دریافت محصول مورد نظر
    2. دریافت محصولات هم‌دسته
    3. محدود کردن نتایج و حذف محصول اصلی از نتایج
    
    ورودی:
        product_id: شناسه محصول مورد نظر
        limit: حداکثر تعداد محصولات مرتبط (پیش‌فرض 4)
        
    خروجی:
        لیست محصولات مرتبط
    """
    try:
        # دریافت محصول مورد نظر
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            logger.error(f"محصول با شناسه {product_id} یافت نشد")
            return []
        
        # دریافت محصولات هم‌دسته به غیر از محصول اصلی
        related_products = Product.objects.filter(
            category=product.category,
            is_active=True
        ).exclude(id=product_id).order_by('-created_at')[:limit]
        
        return related_products
        
    except Exception as e:
        logger.error(f"خطا در دریافت محصولات مرتبط با محصول {product_id}: {str(e)}")
        return []


def calculate_product_rating(product_id):
    """
    محاسبه امتیاز محصول
    
    این تابع میانگین امتیازات ثبت شده برای یک محصول را محاسبه می‌کند.
    
    فرآیند:
    1. دریافت محصول مورد نظر
    2. دریافت نظرات تأیید شده آن محصول
    3. محاسبه میانگین امتیازات
    
    ورودی:
        product_id: شناسه محصول مورد نظر
        
    خروجی:
        میانگین امتیازات محصول (عدد اعشاری)
    """
    try:
        # دریافت محصول مورد نظر
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            logger.error(f"محصول با شناسه {product_id} یافت نشد")
            return 0
        
        # دریافت نظرات تأیید شده
        approved_reviews = Review.objects.filter(product=product, is_approved=True)
        
        # اگر نظری وجود ندارد
        if not approved_reviews.exists():
            return 0
        
        # محاسبه میانگین امتیازات
        avg_rating = approved_reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        
        return round(avg_rating, 1)
        
    except Exception as e:
        logger.error(f"خطا در محاسبه امتیاز محصول {product_id}: {str(e)}")
        return 0


def get_product_stats(request):
    """
    دریافت آمار محصولات
    
    این تابع آماری از وضعیت محصولات را محاسبه و برمی‌گرداند.
    
    فرآیند:
    1. محاسبه تعداد کل محصولات
    2. محاسبه توزیع محصولات بر اساس دسته‌بندی
    3. محاسبه محدوده قیمت محصولات
    4. محاسبه توزیع وضعیت محصولات (فعال/غیرفعال)
    
    ورودی:
        request: درخواست HTTP
    
    خروجی:
        پاسخ JSON شامل آمار محصولات
    """
    try:
        # محاسبه تعداد کل محصولات
        total_products = Product.objects.count()
        
        # محاسبه توزیع محصولات بر اساس دسته‌بندی
        category_distribution = []
        categories = Category.objects.all()
        for category in categories:
            count = Product.objects.filter(category=category).count()
            if count > 0:
                category_distribution.append({
                    'category_id': category.id,
                    'category_name': category.name,
                    'count': count,
                    'percentage': round((count / total_products) * 100, 2) if total_products > 0 else 0
                })
        
        # محاسبه محدوده قیمت محصولات
        price_stats = {}
        if total_products > 0:
            price_stats = {
                'min_price': Product.objects.order_by('price').first().price if total_products > 0 else 0,
                'max_price': Product.objects.order_by('-price').first().price if total_products > 0 else 0,
                'avg_price': round(sum(product.price for product in Product.objects.all()) / total_products, 2) if total_products > 0 else 0
            }
        
        # محاسبه توزیع وضعیت محصولات
        active_count = Product.objects.filter(status='active').count()
        inactive_count = Product.objects.filter(status='inactive').count()
        status_distribution = {
            'active': {
                'count': active_count,
                'percentage': round((active_count / total_products) * 100, 2) if total_products > 0 else 0
            },
            'inactive': {
                'count': inactive_count,
                'percentage': round((inactive_count / total_products) * 100, 2) if total_products > 0 else 0
            }
        }
        
        # برگرداندن آمار محصولات
        return Response({
            'total_products': total_products,
            'category_distribution': category_distribution,
            'price_stats': price_stats,
            'status_distribution': status_distribution
        })
        
    except Exception as e:
        logger.error(f"خطا در محاسبه آمار محصولات: {str(e)}")
        return Response({
            'error': f'خطا در محاسبه آمار محصولات: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def bulk_update_product_status(request):
    """
    به‌روزرسانی گروهی وضعیت محصولات
    
    این تابع امکان تغییر وضعیت چندین محصول را به صورت همزمان فراهم می‌کند.
    
    فرآیند:
    1. دریافت لیست شناسه‌های محصولات و وضعیت جدید
    2. به‌روزرسانی وضعیت محصولات مشخص شده
    3. برگرداندن نتیجه عملیات
    
    ورودی:
        request: درخواست HTTP شامل:
            - product_ids: لیست شناسه‌های محصولات
            - new_status: وضعیت جدید ('active' یا 'inactive')
    
    خروجی:
        پاسخ JSON شامل گزارش عملیات به‌روزرسانی
    """
    try:
        # دریافت داده‌های ورودی
        data = request.data
        product_ids = data.get('product_ids', [])
        new_status = data.get('new_status')
        
        # بررسی داده‌های ورودی
        if not product_ids:
            return Response({
                'error': 'لیست شناسه‌های محصولات ارائه نشده است'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if new_status not in ['active', 'inactive']:
            return Response({
                'error': 'وضعیت جدید باید یکی از مقادیر "active" یا "inactive" باشد'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # یافتن محصولات با شناسه‌های مشخص شده
        products_to_update = Product.objects.filter(id__in=product_ids)
        found_product_ids = list(products_to_update.values_list('id', flat=True))
        
        # محاسبه شناسه‌های نامعتبر
        invalid_product_ids = [pid for pid in product_ids if pid not in found_product_ids]
        
        # به‌روزرسانی وضعیت محصولات
        update_count = products_to_update.update(
            status=new_status,
            updated_by=request.user.username
        )
        
        # برگرداندن گزارش عملیات
        return Response({
            'message': f'وضعیت {update_count} محصول به "{new_status}" تغییر یافت',
            'updated_count': update_count,
            'not_found_ids': invalid_product_ids
        })
        
    except Exception as e:
        logger.error(f"خطا در به‌روزرسانی گروهی وضعیت محصولات: {str(e)}")
        return Response({
            'error': f'خطا در به‌روزرسانی گروهی وضعیت محصولات: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 