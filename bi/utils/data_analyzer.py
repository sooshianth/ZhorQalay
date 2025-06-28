from django.apps import apps
from django.db.models import Count, Sum, Avg, Max, Min, Q, F
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone
from datetime import datetime, timedelta
import json
from typing import Dict, List, Any, Optional
from ..models import DataSource, MetricDefinition, Chart, KPI, Filter


class DataAnalyzer:
    """کلاس اصلی برای تحلیل داده‌ها"""
    
    def __init__(self, data_source: DataSource):
        self.data_source = data_source
        self.model = self._get_model()
    
    def _get_model(self):
        """دریافت مدل Django براساس data_source"""
        if self.data_source.type == 'model':
            return apps.get_model(self.data_source.app_name, self.data_source.model_name)
        else:
            raise NotImplementedError("فعلاً فقط منابع داده مدل Django پشتیبانی می‌شود")
    
    def get_data_source_schema(self) -> Dict[str, Any]:
        """دریافت schema منبع داده"""
        fields = []
        for field in self.model._meta.fields:
            field_info = {
                'name': field.name,
                'type': field.__class__.__name__,
                'verbose_name': str(field.verbose_name),
                'null': field.null,
                'blank': field.blank,
            }
            
            # اطلاعات اضافی براساس نوع فیلد
            if hasattr(field, 'choices') and field.choices:
                field_info['choices'] = [{'value': k, 'label': v} for k, v in field.choices]
            
            if hasattr(field, 'max_length') and field.max_length:
                field_info['max_length'] = field.max_length
            
            fields.append(field_info)
        
        return {
            'model_name': self.model.__name__,
            'fields': fields,
            'verbose_name': self.model._meta.verbose_name,
            'verbose_name_plural': self.model._meta.verbose_name_plural
        }
    
    def get_sample_data(self, limit: int = 10) -> List[Dict]:
        """دریافت نمونه داده"""
        queryset = self.model.objects.all()[:limit]
        data = []
        
        for obj in queryset:
            obj_data = {}
            for field in self.model._meta.fields:
                value = getattr(obj, field.name)
                if hasattr(value, 'isoformat'):  # datetime objects
                    value = value.isoformat()
                elif value is None:
                    value = None
                else:
                    value = str(value)
                obj_data[field.name] = value
            data.append(obj_data)
        
        return data
    
    def get_record_count(self) -> int:
        """تعداد کل رکوردها"""
        return self.model.objects.count()
    
    def get_field_options(self, field_name: str, limit: int = 100) -> List[Dict]:
        """دریافت گزینه‌های یک فیلد"""
        field = self.model._meta.get_field(field_name)
        
        if hasattr(field, 'choices') and field.choices:
            return [{'value': k, 'label': v} for k, v in field.choices]
        
        # برای فیلدهای بدون choices، مقادیر منحصر به فرد را برمی‌گردانیم
        values = self.model.objects.values_list(field_name, flat=True).distinct()[:limit]
        return [{'value': val, 'label': str(val)} for val in values if val is not None]
    
    def apply_filters(self, queryset, filters: Dict[str, Any]):
        """اعمال فیلترها به queryset"""
        # ابتدا فیلتر زمانی را اعمال می‌کنیم
        if 'time_range' in filters:
            queryset = self.apply_time_filter(queryset, filters['time_range'])
        
        for field_name, filter_config in filters.items():
            if field_name == 'time_range':
                continue  # قبلاً اعمال شده
                
            if isinstance(filter_config, dict):
                operator = filter_config.get('operator', 'eq')
                value = filter_config.get('value')
                
                if operator == 'eq':
                    queryset = queryset.filter(**{field_name: value})
                elif operator == 'ne':
                    queryset = queryset.exclude(**{field_name: value})
                elif operator == 'gt':
                    queryset = queryset.filter(**{f"{field_name}__gt": value})
                elif operator == 'gte':
                    queryset = queryset.filter(**{f"{field_name}__gte": value})
                elif operator == 'lt':
                    queryset = queryset.filter(**{f"{field_name}__lt": value})
                elif operator == 'lte':
                    queryset = queryset.filter(**{f"{field_name}__lte": value})
                elif operator == 'contains':
                    queryset = queryset.filter(**{f"{field_name}__icontains": value})
                elif operator == 'startswith':
                    queryset = queryset.filter(**{f"{field_name}__istartswith": value})
                elif operator == 'endswith':
                    queryset = queryset.filter(**{f"{field_name}__iendswith": value})
                elif operator == 'in':
                    queryset = queryset.filter(**{f"{field_name}__in": value})
                elif operator == 'between' and isinstance(value, list) and len(value) == 2:
                    queryset = queryset.filter(**{f"{field_name}__range": value})
                elif operator == 'isnull':
                    queryset = queryset.filter(**{f"{field_name}__isnull": True})
                elif operator == 'isnotnull':
                    queryset = queryset.filter(**{f"{field_name}__isnull": False})
            else:
                # فیلتر ساده
                queryset = queryset.filter(**{field_name: filter_config})
        
        return queryset
    
    def apply_time_filter(self, queryset, time_range: str):
        """اعمال فیلتر زمانی"""
        now = timezone.now()
        today = now.date()
        
        # تعیین فیلد تاریخ مناسب
        date_field = 'created_at'
        model_fields = [f.name for f in self.model._meta.fields]
        if 'created_at' in model_fields:
            date_field = 'created_at'
        elif 'date' in model_fields:
            date_field = 'date'
        elif 'created_date' in model_fields:
            date_field = 'created_date'
        
        if time_range == 'today':
            queryset = queryset.filter(**{f"{date_field}__date": today})
        elif time_range == 'week':
            week_start = today - timedelta(days=7)
            queryset = queryset.filter(**{f"{date_field}__date__gte": week_start})
        elif time_range == 'month':
            month_start = today - timedelta(days=30)
            queryset = queryset.filter(**{f"{date_field}__date__gte": month_start})
        elif time_range == '30days':
            days_30_ago = today - timedelta(days=30)
            queryset = queryset.filter(**{f"{date_field}__date__gte": days_30_ago})
        elif time_range == '90days':
            days_90_ago = today - timedelta(days=90)
            queryset = queryset.filter(**{f"{date_field}__date__gte": days_90_ago})
        elif time_range == '6months':
            months_6_ago = today - timedelta(days=180)
            queryset = queryset.filter(**{f"{date_field}__date__gte": months_6_ago})
        elif time_range == 'year':
            year_start = today - timedelta(days=365)
            queryset = queryset.filter(**{f"{date_field}__date__gte": year_start})
        elif time_range == 'all':
            # بدون فیلتر زمانی
            pass
        
        return queryset
    
    def calculate_metric(self, metric: MetricDefinition, filters: Dict = None) -> float:
        """محاسبه یک شاخص"""
        queryset = self.model.objects.all()
        
        # اعمال فیلتر metric
        if metric.filter_expression:
            # اینجا باید فیلتر expression پارس شود
            pass
        
        # اعمال فیلترهای ارسالی
        if filters:
            queryset = self.apply_filters(queryset, filters)
        
        # محاسبه براساس نوع aggregation
        if metric.aggregation_type == 'sum':
            result = queryset.aggregate(value=Sum(metric.field_name))['value'] or 0
        elif metric.aggregation_type == 'avg':
            result = queryset.aggregate(value=Avg(metric.field_name))['value'] or 0
        elif metric.aggregation_type == 'count':
            result = queryset.count()
        elif metric.aggregation_type == 'count_distinct':
            result = queryset.values(metric.field_name).distinct().count()
        elif metric.aggregation_type == 'min':
            result = queryset.aggregate(value=Min(metric.field_name))['value'] or 0
        elif metric.aggregation_type == 'max':
            result = queryset.aggregate(value=Max(metric.field_name))['value'] or 0
        else:
            result = 0
        
        return float(result) if result else 0.0
    
    def generate_time_series_data(self, chart: Chart, filters: Dict = None) -> Dict:
        """تولید داده‌های time series"""
        queryset = self.model.objects.all()
        
        if filters:
            queryset = self.apply_filters(queryset, filters)
        
        # تعیین نوع truncate براساس time_period
        if chart.time_period == 'day':
            trunc_func = TruncDate
        elif chart.time_period == 'week':
            trunc_func = TruncWeek
        elif chart.time_period == 'month':
            trunc_func = TruncMonth
        elif chart.time_period == 'year':
            trunc_func = TruncYear
        else:
            trunc_func = TruncDate
        
        # گروه‌بندی براساس زمان
        data = queryset.annotate(
            period=trunc_func(chart.x_axis_field)
        ).values('period')
        
        # محاسبه metrics برای هر دوره
        for metric in chart.y_axis_metrics.all():
            if metric.aggregation_type == 'sum':
                data = data.annotate(**{metric.name: Sum(metric.field_name)})
            elif metric.aggregation_type == 'avg':
                data = data.annotate(**{metric.name: Avg(metric.field_name)})
            elif metric.aggregation_type == 'count':
                data = data.annotate(**{metric.name: Count('id')})
        
        return list(data.order_by('period'))
    
    def generate_grouped_data(self, chart: Chart, filters: Dict = None) -> Dict:
        """تولید داده‌های گروه‌بندی شده"""
        queryset = self.model.objects.all()
        
        if filters:
            queryset = self.apply_filters(queryset, filters)
        
        # گروه‌بندی براساس فیلد مشخص شده
        data = queryset.values(chart.group_by_field or chart.x_axis_field)
        
        # محاسبه metrics برای هر گروه
        for metric in chart.y_axis_metrics.all():
            if metric.aggregation_type == 'sum':
                data = data.annotate(**{metric.name: Sum(metric.field_name)})
            elif metric.aggregation_type == 'avg':
                data = data.annotate(**{metric.name: Avg(metric.field_name)})
            elif metric.aggregation_type == 'count':
                data = data.annotate(**{metric.name: Count('id')})
        
        return list(data.order_by(chart.group_by_field or chart.x_axis_field))
    
    def drill_down(self, chart: Chart, drill_point: Dict, drill_level: int = 1, filters: Dict = None) -> Dict:
        """عملیات drill-down"""
        # اضافه کردن فیلتر جدید براساس نقطه کلیک شده
        new_filters = filters.copy() if filters else {}
        
        # تعیین فیلد drill-down براساس تنظیمات chart
        drill_config = chart.drill_down_config or {}
        drill_field = drill_config.get(f'level_{drill_level}', chart.x_axis_field)
        
        new_filters[drill_field] = drill_point.get('value')
        
        # تولید داده‌های جدید با فیلترهای اضافه شده
        if chart.time_period:
            data = self.generate_time_series_data(chart, new_filters)
        else:
            data = self.generate_grouped_data(chart, new_filters)
        
        return {
            'data': data,
            'drill_level': drill_level,
            'filters_applied': new_filters,
            'can_drill_further': drill_level < len(drill_config)
        }
    
    def calculate_kpi_value(self, kpi: KPI, filters: Dict = None) -> float:
        """محاسبه مقدار فعلی KPI"""
        return self.calculate_metric(kpi.metric, filters)
    
    def calculate_kpi_previous_value(self, kpi: KPI, filters: Dict = None) -> float:
        """محاسبه مقدار قبلی KPI برای مقایسه"""
        # تعیین دوره قبل براساس comparison_period
        if kpi.comparison_period == 'day':
            previous_date = timezone.now() - timedelta(days=1)
        elif kpi.comparison_period == 'week':
            previous_date = timezone.now() - timedelta(weeks=1)
        elif kpi.comparison_period == 'month':
            previous_date = timezone.now() - timedelta(days=30)
        elif kpi.comparison_period == 'year':
            previous_date = timezone.now() - timedelta(days=365)
        else:
            previous_date = timezone.now() - timedelta(days=30)
        
        # اضافه کردن فیلتر زمانی
        time_filters = filters.copy() if filters else {}
        # اینجا باید فیلد تاریخ مشخص شود - معمولاً created_at یا similar
        date_field = 'created_at'  # این باید قابل تنظیم باشد
        time_filters[f'{date_field}__lte'] = previous_date
        
        return self.calculate_metric(kpi.metric, time_filters)
    
    def generate_report_data(self, report, filters: Dict = None) -> List[Dict]:
        """تولید داده‌های گزارش"""
        queryset = self.model.objects.all()
        
        if filters:
            queryset = self.apply_filters(queryset, filters)
        
        # اعمال فیلترهای گزارش
        if report.filters:
            queryset = self.apply_filters(queryset, report.filters)
        
        # اعمال grouping
        if report.grouping:
            queryset = queryset.values(*report.grouping)
            
            # اعمال aggregations
            for agg in report.aggregations:
                field_name = agg.get('field')
                agg_type = agg.get('type')
                agg_name = agg.get('name', f"{agg_type}_{field_name}")
                
                if agg_type == 'sum':
                    queryset = queryset.annotate(**{agg_name: Sum(field_name)})
                elif agg_type == 'avg':
                    queryset = queryset.annotate(**{agg_name: Avg(field_name)})
                elif agg_type == 'count':
                    queryset = queryset.annotate(**{agg_name: Count(field_name)})
        
        # اعمال sorting
        if report.sorting:
            sort_fields = []
            for sort_config in report.sorting:
                field = sort_config.get('field')
                direction = sort_config.get('direction', 'asc')
                if direction == 'desc':
                    field = f'-{field}'
                sort_fields.append(field)
            queryset = queryset.order_by(*sort_fields)
        
        # انتخاب ستون‌ها
        if report.columns:
            selected_fields = [col.get('field') for col in report.columns if col.get('field')]
            if selected_fields:
                queryset = queryset.values(*selected_fields)
        
        return list(queryset)
    
    def get_real_time_data(self, chart: Chart) -> Dict:
        """دریافت داده‌های زنده"""
        # برای اپلیکیشن ژورقالای، داده‌های زنده شامل آخرین خریدها یا تغییرات وضعیت می‌شود
        try:
            from datetime import timedelta
            from django.utils import timezone
            
            # آخرین ۲۴ ساعت
            last_24h = timezone.now() - timedelta(hours=24)
            
            if chart.data_source.model_name == 'Purchase':
                recent_data = self.model.objects.filter(
                    created_at__gte=last_24h
                ).aggregate(
                    new_purchases=Count('id'),
                    total_amount=Sum('amount_paid'),
                    avg_amount=Avg('amount_paid')
                )
                
                return {
                    'timestamp': timezone.now().isoformat(),
                    'data': recent_data,
                    'period': '24h'
                }
            else:
                return self.generate_grouped_data(chart)
                
        except Exception as e:
            return {'error': str(e)}
    
    # ==============================================
    # متدهای تخصصی ژورقالای  
    # ==============================================
    
    def get_purchase_analytics(self, filters: Dict = None) -> Dict:
        """تحلیل کامل خریدها"""
        try:
            queryset = self.model.objects.all()
            if filters:
                queryset = self.apply_filters(queryset, filters)
            
            # آمار کلی
            total_stats = queryset.aggregate(
                total_purchases=Count('id'),
                total_amount=Sum('amount_paid'),
                total_weight=Sum('order_weight'),
                avg_amount=Avg('amount_paid'),
                avg_weight=Avg('order_weight')
            )
            
            # آمار براساس وضعیت
            status_stats = queryset.values('state').annotate(
                count=Count('id'),
                total_amount=Sum('amount_paid')
            )
            
            # آمار براساس نوع محصول
            product_stats = queryset.values('cargo__product_type').annotate(
                count=Count('id'),
                total_weight=Sum('order_weight')
            )
            
            # آمار ماهانه
            from django.db.models import TruncMonth
            monthly_stats = queryset.annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                purchases=Count('id'),
                amount=Sum('amount_paid')
            ).order_by('month')
            
            return {
                'total_stats': total_stats,
                'status_breakdown': list(status_stats),
                'product_breakdown': list(product_stats),
                'monthly_trend': list(monthly_stats)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_customer_analytics(self, filters: Dict = None) -> Dict:
        """تحلیل کامل مشتریان"""
        try:
            queryset = self.model.objects.all()
            if filters:
                queryset = self.apply_filters(queryset, filters)
            
            # مشتریان برتر
            top_customers = queryset.values('customer__name', 'customer__city').annotate(
                purchase_count=Count('id'),
                total_amount=Sum('amount_paid'),
                avg_amount=Avg('amount_paid')
            ).order_by('-total_amount')[:10]
            
            # توزیع جغرافیایی
            city_distribution = queryset.values('customer__city').annotate(
                customer_count=Count('customer', distinct=True),
                purchase_count=Count('id'),
                total_amount=Sum('amount_paid')
            ).order_by('-total_amount')
            
            # تحلیل رفتار خرید
            purchase_behavior = queryset.aggregate(
                repeat_customers=Count('customer', distinct=True),
                avg_purchases_per_customer=Avg('customer__purchases_made__id'),
                first_time_buyers=Count('customer', filter=Q(customer__purchases_made__id=1))
            )
            
            return {
                'top_customers': list(top_customers),
                'city_distribution': list(city_distribution),
                'purchase_behavior': purchase_behavior
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_product_analytics(self, filters: Dict = None) -> Dict:
        """تحلیل کامل محصولات"""
        try:
            queryset = self.model.objects.all()
            if filters:
                queryset = self.apply_filters(queryset, filters)
            
            # عملکرد محصولات
            product_performance = queryset.values(
                'cargo__product_type', 
                'cargo__country'
            ).annotate(
                sales_count=Count('id'),
                total_weight=Sum('order_weight'),
                total_amount=Sum('amount_paid'),
                avg_price=Avg('customer_price')
            ).order_by('-total_weight')
            
            # ترندهای قیمت
            price_trends = queryset.values('cargo__product_type').annotate(
                min_price=Min('customer_price'),
                max_price=Max('customer_price'),
                avg_price=Avg('customer_price'),
                latest_price=F('customer_price')  # این باید بهبود یابد
            )
            
            # آمار موجودی
            inventory_stats = queryset.values('cargo__product_type').annotate(
                available_weight=Sum('cargo__weight'),
                sold_weight=Sum('order_weight')
            )
            
            return {
                'product_performance': list(product_performance),
                'price_trends': list(price_trends),
                'inventory_stats': list(inventory_stats)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_sales_agent_analytics(self, filters: Dict = None) -> Dict:
        """تحلیل کامل کارشناسان فروش"""
        try:
            queryset = self.model.objects.all()
            if filters:
                queryset = self.apply_filters(queryset, filters)
            
            # عملکرد کارشناسان
            agent_performance = queryset.values('unique_sales_agent__name').annotate(
                total_sales=Count('id'),
                total_amount=Sum('amount_paid'),
                total_weight=Sum('order_weight'),
                avg_amount=Avg('amount_paid'),
                customer_count=Count('customer', distinct=True)
            ).order_by('-total_amount')
            
            # مقایسه ماهانه
            from django.db.models import TruncMonth
            monthly_comparison = queryset.annotate(
                month=TruncMonth('created_at')
            ).values('month', 'unique_sales_agent__name').annotate(
                sales=Count('id'),
                amount=Sum('amount_paid')
            ).order_by('month', '-amount')
            
            return {
                'agent_performance': list(agent_performance),
                'monthly_comparison': list(monthly_comparison)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_geographic_analytics(self, filters: Dict = None) -> Dict:
        """تحلیل جغرافیایی ایران"""
        try:
            from .geo_analyzer import GeographicAnalyzer
            geo_analyzer = GeographicAnalyzer()
            
            queryset = self.model.objects.all()
            if filters:
                queryset = self.apply_filters(queryset, filters)
            
            # توزیع براساس شهر
            city_data = queryset.values('customer__city').annotate(
                sales_count=Count('id'),
                total_amount=Sum('amount_paid'),
                customer_count=Count('customer', distinct=True)
            ).order_by('-total_amount')
            
            # نقشه‌برداری به استان‌ها
            province_data = {}
            for item in city_data:
                city = item['customer__city']
                if city:
                    province = geo_analyzer.get_province_by_city(city)
                    if province not in province_data:
                        province_data[province] = {
                            'sales_count': 0,
                            'total_amount': 0,
                            'customer_count': 0
                        }
                    province_data[province]['sales_count'] += item['sales_count']
                    province_data[province]['total_amount'] += item['total_amount'] or 0
                    province_data[province]['customer_count'] += item['customer_count']
            
            # تبدیل به لیست برای نمودار
            province_list = []
            for province, data in province_data.items():
                province_list.append({
                    'province': province,
                    'sales_count': data['sales_count'],
                    'total_amount': data['total_amount'],
                    'customer_count': data['customer_count']
                })
            
            return {
                'city_distribution': list(city_data),
                'province_distribution': province_list
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_time_series_analytics(self, chart: Chart, period: str = 'day', filters: Dict = None) -> Dict:
        """تحلیل سری زمانی پیشرفته"""
        try:
            from django.db.models import TruncDate, TruncWeek, TruncMonth, TruncYear
            
            queryset = self.model.objects.all()
            if filters:
                queryset = self.apply_filters(queryset, filters)
            
            # انتخاب تابع truncate
            trunc_functions = {
                'day': TruncDate,
                'week': TruncWeek,
                'month': TruncMonth,
                'year': TruncYear
            }
            trunc_func = trunc_functions.get(period, TruncDate)
            
            # گروه‌بندی براساس زمان
            time_series = queryset.annotate(
                period=trunc_func('created_at')
            ).values('period').annotate(
                count=Count('id'),
                total_amount=Sum('amount_paid'),
                avg_amount=Avg('amount_paid'),
                total_weight=Sum('order_weight')
            ).order_by('period')
            
            # محاسبه رشد
            data_list = list(time_series)
            for i, item in enumerate(data_list):
                if i > 0:
                    prev_count = data_list[i-1]['count']
                    current_count = item['count']
                    growth = ((current_count - prev_count) / prev_count * 100) if prev_count else 0
                    item['growth_rate'] = round(growth, 2)
                else:
                    item['growth_rate'] = 0
            
            return {
                'time_series': data_list,
                'period': period,
                'total_periods': len(data_list)
            }
        except Exception as e:
            return {'error': str(e)} 