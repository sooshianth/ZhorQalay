from django.apps import apps
from django.db.models import Count, Sum, Avg, Q
from typing import Dict, List, Any
import json


class GeographicAnalyzer:
    """کلاس تحلیل‌های جغرافیایی برای نقشه ایران"""
    
    def __init__(self):
        # نقشه‌برداری نام استان‌ها به کدهای استاندارد
        self.province_mapping = {
            'تهران': {'code': 'IR-23', 'lat': 35.6892, 'lng': 51.3890},
            'اصفهان': {'code': 'IR-10', 'lat': 32.6546, 'lng': 51.6680},
            'فارس': {'code': 'IR-07', 'lat': 29.5918, 'lng': 52.5837},
            'خراسان رضوی': {'code': 'IR-09', 'lat': 36.2605, 'lng': 59.6168},
            'خوزستان': {'code': 'IR-06', 'lat': 31.3183, 'lng': 48.6706},
            'مازندران': {'code': 'IR-02', 'lat': 36.5659, 'lng': 53.0586},
            'کرمان': {'code': 'IR-08', 'lat': 30.2839, 'lng': 57.0834},
            'آذربایجان شرقی': {'code': 'IR-03', 'lat': 38.0804, 'lng': 46.2919},
            'گیلان': {'code': 'IR-01', 'lat': 37.2808, 'lng': 49.5906},
            'مرکزی': {'code': 'IR-00', 'lat': 34.0917, 'lng': 49.6892},
            'آذربایجان غربی': {'code': 'IR-04', 'lat': 37.4549, 'lng': 45.0000},
            'کرمانشاه': {'code': 'IR-05', 'lat': 34.3142, 'lng': 47.0650},
            'قم': {'code': 'IR-25', 'lat': 34.6401, 'lng': 50.8764},
            'قزوین': {'code': 'IR-26', 'lat': 36.2688, 'lng': 50.0041},
            'گلستان': {'code': 'IR-27', 'lat': 36.8427, 'lng': 54.4391},
            'خراسان شمالی': {'code': 'IR-28', 'lat': 37.4747, 'lng': 57.1000},
            'خراسان جنوبی': {'code': 'IR-29', 'lat': 32.8734, 'lng': 59.2044},
            'البرز': {'code': 'IR-30', 'lat': 35.9968, 'lng': 50.9276},
            'کردستان': {'code': 'IR-12', 'lat': 35.3150, 'lng': 46.9886},
            'همدان': {'code': 'IR-13', 'lat': 34.7992, 'lng': 48.5146},
            'چهارمحال و بختیاری': {'code': 'IR-14', 'lat': 31.9613, 'lng': 50.8450},
            'لرستان': {'code': 'IR-15', 'lat': 33.4942, 'lng': 48.3558},
            'ایلام': {'code': 'IR-16', 'lat': 33.6374, 'lng': 46.4227},
            'کهگیلویه و بویراحمد': {'code': 'IR-17', 'lat': 30.6515, 'lng': 51.6058},
            'بوشهر': {'code': 'IR-18', 'lat': 28.9684, 'lng': 50.8204},
            'زنجان': {'code': 'IR-19', 'lat': 36.6736, 'lng': 48.4787},
            'سمنان': {'code': 'IR-20', 'lat': 35.5769, 'lng': 53.3920},
            'یزد': {'code': 'IR-21', 'lat': 31.8974, 'lng': 54.3569},
            'هرمزگان': {'code': 'IR-22', 'lat': 27.1865, 'lng': 56.2808},
            'اردبیل': {'code': 'IR-24', 'lat': 38.2498, 'lng': 48.3000},
            'سیستان و بلوچستان': {'code': 'IR-11', 'lat': 27.5342, 'lng': 60.5820}
        }
    
    def get_sales_by_province(self, filters: Dict = None) -> List[Dict]:
        """تحلیل فروش براساس استان"""
        try:
            # دریافت مدل مشتری
            Customer = apps.get_model('core', 'Customer')
            Purchase = apps.get_model('core', 'Purchase')
            
            # کوئری برای دریافت آمار فروش هر استان
            queryset = Customer.objects.all()
            
            if filters:
                queryset = self._apply_filters(queryset, filters)
            
            # گروه‌بندی براساس شهر مشتریان
            province_data = queryset.values('city').annotate(
                customer_count=Count('id'),
                total_purchases=Count('purchases_made'),
                total_amount=Sum('purchases_made__amount_paid')
            ).order_by('-customer_count')
            
            # تبدیل شهر به استان و تولید داده‌های نقشه
            result = []
            for item in province_data:
                city = item['city'] or 'نامشخص'
                province = self._city_to_province(city)
                
                if province in self.province_mapping:
                    province_info = self.province_mapping[province]
                    result.append({
                        'province': province,
                        'code': province_info['code'],
                        'lat': province_info['lat'],
                        'lng': province_info['lng'],
                        'customer_count': item['customer_count'] or 0,
                        'total_purchases': item['total_purchases'] or 0,
                        'total_amount': item['total_amount'] or 0
                    })
            
            return result
            
        except Exception as e:
            print(f"Error in get_sales_by_province: {e}")
            return []
    
    def get_sales_by_city(self, filters: Dict = None) -> List[Dict]:
        """تحلیل فروش براساس شهر"""
        try:
            Customer = apps.get_model('core', 'Customer')
            
            queryset = Customer.objects.all()
            
            if filters:
                queryset = self._apply_filters(queryset, filters)
            
            city_data = queryset.values('city').annotate(
                customer_count=Count('id'),
                total_purchases=Count('purchases_made'),
                total_amount=Sum('purchases_made__amount_paid')
            ).order_by('-customer_count')
            
            result = []
            for item in city_data:
                city = item['city'] or 'نامشخص'
                coordinates = self._get_city_coordinates(city)
                
                result.append({
                    'city': city,
                    'province': self._city_to_province(city),
                    'lat': coordinates['lat'],
                    'lng': coordinates['lng'],
                    'customer_count': item['customer_count'] or 0,
                    'total_purchases': item['total_purchases'] or 0,
                    'total_amount': item['total_amount'] or 0
                })
            
            return result
            
        except Exception as e:
            print(f"Error in get_sales_by_city: {e}")
            return []
    
    def generate_heatmap_data(self, filters: Dict = None) -> List[Dict]:
        """تولید داده‌های نقشه حرارتی"""
        try:
            Customer = apps.get_model('core', 'Customer')
            
            queryset = Customer.objects.exclude(city__isnull=True).exclude(city='')
            
            if filters:
                queryset = self._apply_filters(queryset, filters)
            
            # گروه‌بندی براساس موقعیت جغرافیایی
            heatmap_data = []
            
            city_data = queryset.values('city').annotate(
                intensity=Count('id')
            )
            
            for item in city_data:
                city = item['city']
                coordinates = self._get_city_coordinates(city)
                
                if coordinates['lat'] and coordinates['lng']:
                    heatmap_data.append({
                        'lat': coordinates['lat'],
                        'lng': coordinates['lng'],
                        'intensity': item['intensity'],
                        'city': city
                    })
            
            return heatmap_data
            
        except Exception as e:
            print(f"Error in generate_heatmap_data: {e}")
            return []
    
    def get_product_distribution_by_region(self, filters: Dict = None) -> List[Dict]:
        """توزیع محصولات براساس منطقه"""
        try:
            Purchase = apps.get_model('core', 'Purchase')
            
            queryset = Purchase.objects.select_related('customer', 'cargo')
            
            if filters:
                queryset = self._apply_filters(queryset, filters)
            
            # گروه‌بندی براساس نوع محصول و استان
            region_product_data = []
            
            # دریافت داده‌ها براساس شهر مشتری و نوع محصول
            data = queryset.values(
                'customer__city',
                'cargo__product_type'
            ).annotate(
                total_weight=Sum('order_weight'),
                purchase_count=Count('id'),
                total_amount=Sum('amount_paid')
            )
            
            for item in data:
                city = item['customer__city'] or 'نامشخص'
                product_type = item['cargo__product_type'] or 'نامشخص'
                province = self._city_to_province(city)
                
                region_product_data.append({
                    'city': city,
                    'province': province,
                    'product_type': product_type,
                    'total_weight': item['total_weight'] or 0,
                    'purchase_count': item['purchase_count'] or 0,
                    'total_amount': item['total_amount'] or 0
                })
            
            return region_product_data
            
        except Exception as e:
            print(f"Error in get_product_distribution_by_region: {e}")
            return []
    
    def get_sales_trends_by_region(self, time_period: str = 'month', filters: Dict = None) -> List[Dict]:
        """روندهای فروش براساس منطقه و زمان"""
        try:
            from django.db.models.functions import TruncMonth, TruncYear, TruncWeek
            
            Purchase = apps.get_model('core', 'Purchase')
            
            queryset = Purchase.objects.select_related('customer')
            
            if filters:
                queryset = self._apply_filters(queryset, filters)
            
            # انتخاب تابع truncate براساس دوره زمانی
            if time_period == 'month':
                trunc_func = TruncMonth
            elif time_period == 'year':
                trunc_func = TruncYear
            elif time_period == 'week':
                trunc_func = TruncWeek
            else:
                trunc_func = TruncMonth
            
            # گروه‌بندی براساس زمان و استان
            trend_data = queryset.annotate(
                period=trunc_func('created_at')
            ).values(
                'period',
                'customer__city'
            ).annotate(
                purchase_count=Count('id'),
                total_amount=Sum('amount_paid'),
                total_weight=Sum('order_weight')
            ).order_by('period', 'customer__city')
            
            result = []
            for item in trend_data:
                city = item['customer__city'] or 'نامشخص'
                province = self._city_to_province(city)
                
                result.append({
                    'period': item['period'].strftime('%Y-%m') if item['period'] else 'نامشخص',
                    'city': city,
                    'province': province,
                    'purchase_count': item['purchase_count'] or 0,
                    'total_amount': item['total_amount'] or 0,
                    'total_weight': item['total_weight'] or 0
                })
            
            return result
            
        except Exception as e:
            print(f"Error in get_sales_trends_by_region: {e}")
            return []
    
    def _city_to_province(self, city: str) -> str:
        """تبدیل شهر به استان"""
        # نقشه‌برداری ساده شهرها به استان‌ها
        city_to_province_map = {
            'تهران': 'تهران',
            'کرج': 'البرز',
            'اصفهان': 'اصفهان',
            'شیراز': 'فارس',
            'مشهد': 'خراسان رضوی',
            'اهواز': 'خوزستان',
            'تبریز': 'آذربایجان شرقی',
            'کرمان': 'کرمان',
            'رشت': 'گیلان',
            'ساری': 'مازندران',
            'ارومیه': 'آذربایجان غربی',
            'کرمانشاه': 'کرمانشاه',
            'قم': 'قم',
            'قزوین': 'قزوین',
            'گرگان': 'گلستان',
            'بجنورد': 'خراسان شمالی',
            'بیرجند': 'خراسان جنوبی',
            'سنندج': 'کردستان',
            'همدان': 'همدان',
            'شهرکرد': 'چهارمحال و بختیاری',
            'خرم‌آباد': 'لرستان',
            'ایلام': 'ایلام',
            'یاسوج': 'کهگیلویه و بویراحمد',
            'بوشهر': 'بوشهر',
            'زنجان': 'زنجان',
            'سمنان': 'سمنان',
            'یزد': 'یزد',
            'بندرعباس': 'هرمزگان',
            'اردبیل': 'اردبیل',
            'زاهدان': 'سیستان و بلوچستان'
        }
        
        # جستجوی دقیق
        if city in city_to_province_map:
            return city_to_province_map[city]
        
        # جستجوی جزئی
        for city_key, province in city_to_province_map.items():
            if city_key in city:
                return province
        
        return 'نامشخص'
    
    def _get_city_coordinates(self, city: str) -> Dict[str, float]:
        """دریافت مختصات جغرافیایی شهر"""
        # مختصات شهرهای اصلی ایران
        city_coordinates = {
            'تهران': {'lat': 35.6892, 'lng': 51.3890},
            'کرج': {'lat': 35.8327, 'lng': 50.9916},
            'اصفهان': {'lat': 32.6546, 'lng': 51.6680},
            'شیراز': {'lat': 29.5918, 'lng': 52.5837},
            'مشهد': {'lat': 36.2605, 'lng': 59.6168},
            'اهواز': {'lat': 31.3183, 'lng': 48.6706},
            'تبریز': {'lat': 38.0804, 'lng': 46.2919},
            'کرمان': {'lat': 30.2839, 'lng': 57.0834},
            'رشت': {'lat': 37.2808, 'lng': 49.5906},
            'ساری': {'lat': 36.5659, 'lng': 53.0586},
            'ارومیه': {'lat': 37.5527, 'lng': 45.0761},
            'کرمانشاه': {'lat': 34.3142, 'lng': 47.0650},
            'قم': {'lat': 34.6401, 'lng': 50.8764},
            'قزوین': {'lat': 36.2688, 'lng': 50.0041},
            'گرگان': {'lat': 36.8427, 'lng': 54.4391}
        }
        
        if city in city_coordinates:
            return city_coordinates[city]
        
        # اگر شهر پیدا نشد، مختصات استان مربوطه را برگردان
        province = self._city_to_province(city)
        if province in self.province_mapping:
            return {
                'lat': self.province_mapping[province]['lat'],
                'lng': self.province_mapping[province]['lng']
            }
        
        # مختصات پیش‌فرض (مرکز ایران)
        return {'lat': 32.4279, 'lng': 53.6880}
    
    def _apply_filters(self, queryset, filters: Dict):
        """اعمال فیلترها به queryset"""
        for field_name, value in filters.items():
            if value is not None:
                if isinstance(value, dict):
                    operator = value.get('operator', 'eq')
                    filter_value = value.get('value')
                    
                    if operator == 'eq':
                        queryset = queryset.filter(**{field_name: filter_value})
                    elif operator == 'in':
                        queryset = queryset.filter(**{f"{field_name}__in": filter_value})
                    elif operator == 'gte':
                        queryset = queryset.filter(**{f"{field_name}__gte": filter_value})
                    elif operator == 'lte':
                        queryset = queryset.filter(**{f"{field_name}__lte": filter_value})
                else:
                    queryset = queryset.filter(**{field_name: value})
        
        return queryset 

    def get_province_by_city(self, city: str) -> str:
        """دریافت استان براساس شهر - برای استفاده در data_analyzer"""
        return self._city_to_province(city)
    
    def get_iran_map_data_for_chart(self, data: List[Dict], value_field: str = 'value') -> Dict:
        """تولید داده‌های نقشه ایران برای نمودار"""
        map_data = []
        
        for item in data:
            province = item.get('province', 'نامشخص')
            value = item.get(value_field, 0)
            
            if province in self.province_mapping:
                province_info = self.province_mapping[province]
                map_data.append({
                    'code': province_info['code'],
                    'name': province,
                    'value': value,
                    'lat': province_info['lat'],
                    'lng': province_info['lng']
                })
        
        return {
            'type': 'iran_map',
            'data': map_data,
            'options': {
                'responsive': True,
                'colorScale': ['#e6f3ff', '#0066cc'],
                'borderColor': '#ffffff',
                'borderWidth': 1
            }
        } 