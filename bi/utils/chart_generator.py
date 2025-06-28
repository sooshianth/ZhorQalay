from typing import Dict, List, Any
from django.db.models import Count, Sum, Avg
from .data_analyzer import DataAnalyzer
from ..models import Chart, MetricDefinition
import random


class ChartDataGenerator:
    """کلاس تولید داده‌های نمودار برای کتابخانه‌های مختلف"""
    
    @staticmethod
    def generate_chart_data(chart: Chart, filters: Dict = None) -> Dict[str, Any]:
        """تولید داده‌های نمودار براساس نوع chart"""
        analyzer = DataAnalyzer(chart.data_source)
        
        # انتخاب روش تولید داده براساس نوع نمودار
        if chart.chart_type in ['line', 'bar', 'area']:
            return ChartDataGenerator._generate_basic_chart_data(chart, analyzer, filters)
        elif chart.chart_type in ['pie', 'doughnut']:
            return ChartDataGenerator._generate_pie_chart_data(chart, analyzer, filters)
        elif chart.chart_type == 'heatmap':
            return ChartDataGenerator._generate_heatmap_data(chart, analyzer, filters)
        elif chart.chart_type == 'map_iran':
            return ChartDataGenerator._generate_iran_map_data(chart, analyzer, filters)
        elif chart.chart_type == 'gauge':
            return ChartDataGenerator._generate_gauge_data(chart, analyzer, filters)
        elif chart.chart_type == 'kpi_card':
            return ChartDataGenerator._generate_kpi_card_data(chart, analyzer, filters)
        elif chart.chart_type == 'table':
            return ChartDataGenerator._generate_table_data(chart, analyzer, filters)
        elif chart.chart_type == 'scatter':
            return ChartDataGenerator._generate_scatter_data(chart, analyzer, filters)
        elif chart.chart_type == 'bubble':
            return ChartDataGenerator._generate_bubble_data(chart, analyzer, filters)
        elif chart.chart_type == 'funnel':
            return ChartDataGenerator._generate_funnel_data(chart, analyzer, filters)
        elif chart.chart_type == 'radar':
            return ChartDataGenerator._generate_radar_data(chart, analyzer, filters)
        elif chart.chart_type == 'treemap':
            return ChartDataGenerator._generate_treemap_data(chart, analyzer, filters)
        elif chart.chart_type == 'sankey':
            return ChartDataGenerator._generate_sankey_data(chart, analyzer, filters)
        # نمودارهای تخصصی ژورقالای
        elif chart.chart_type == 'purchase_timeline':
            return ChartDataGenerator._generate_purchase_timeline_data(chart, analyzer, filters)
        elif chart.chart_type == 'customer_activity':
            return ChartDataGenerator._generate_customer_activity_data(chart, analyzer, filters)
        elif chart.chart_type == 'product_performance':
            return ChartDataGenerator._generate_product_performance_data(chart, analyzer, filters)
        elif chart.chart_type == 'barnameh_status':
            return ChartDataGenerator._generate_barnameh_status_data(chart, analyzer, filters)
        elif chart.chart_type == 'sales_agent_comparison':
            return ChartDataGenerator._generate_sales_agent_comparison_data(chart, analyzer, filters)
        else:
            return ChartDataGenerator._generate_basic_chart_data(chart, analyzer, filters)
    
    @staticmethod
    def _generate_basic_chart_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودارهای خطی، ستونی و ناحیه‌ای"""
        if chart.time_period:
            raw_data = analyzer.generate_time_series_data(chart, filters)
        else:
            raw_data = analyzer.generate_grouped_data(chart, filters)
        
        # استخراج labels
        if chart.time_period:
            labels = [item['period'].strftime('%Y-%m-%d') if item['period'] else 'نامشخص' for item in raw_data]
        else:
            label_field = chart.group_by_field or chart.x_axis_field
            labels = [str(item[label_field]) if item[label_field] else 'نامشخص' for item in raw_data]
        
        # تولید datasets برای هر metric
        datasets = []
        colors = ChartDataGenerator._get_color_palette(len(chart.y_axis_metrics.all()))
        
        for i, metric in enumerate(chart.y_axis_metrics.all()):
            data_values = [item.get(metric.name, 0) for item in raw_data]
            
            dataset = {
                'label': metric.display_name,
                'data': data_values,
                'backgroundColor': colors[i]['background'],
                'borderColor': colors[i]['border'],
                'borderWidth': 2,
                'fill': chart.chart_type == 'area'
            }
            
            # تنظیمات خاص برای نوع نمودار
            if chart.chart_type == 'line':
                dataset.update({
                    'tension': 0.4,
                    'pointRadius': 4,
                    'pointHoverRadius': 6
                })
            elif chart.chart_type == 'bar':
                dataset.update({
                    'barThickness': 'flex',
                    'maxBarThickness': 40
                })
            
            datasets.append(dataset)
        
        return {
            'type': chart.chart_type,
            'data': {
                'labels': labels,
                'datasets': datasets
            },
            'options': ChartDataGenerator._get_chart_options(chart)
        }
    
    @staticmethod
    def _generate_pie_chart_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودار دایره‌ای"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        # استخراج labels و values
        label_field = chart.group_by_field or chart.x_axis_field
        labels = [str(item[label_field]) if item[label_field] else 'نامشخص' for item in raw_data]
        
        # استفاده از اولین metric برای pie chart
        metric = chart.y_axis_metrics.first()
        if metric:
            data_values = [item.get(metric.name, 0) for item in raw_data]
        else:
            data_values = [1] * len(labels)  # fallback
        
        colors = ChartDataGenerator._get_color_palette(len(labels))
        
        return {
            'type': chart.chart_type,
            'data': {
                'labels': labels,
                'datasets': [{
                    'data': data_values,
                    'backgroundColor': [color['background'] for color in colors],
                    'borderColor': [color['border'] for color in colors],
                    'borderWidth': 2
                }]
            },
            'options': ChartDataGenerator._get_pie_chart_options(chart)
        }
    
    @staticmethod
    def _generate_heatmap_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نقشه حرارتی"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        # تبدیل داده‌ها به فرمت heatmap
        heatmap_data = []
        for item in raw_data:
            x_value = item.get(chart.x_axis_field, 0)
            metric = chart.y_axis_metrics.first()
            y_value = item.get(metric.name if metric else 'count', 0)
            
            heatmap_data.append({
                'x': x_value,
                'y': y_value,
                'v': y_value  # value for color intensity
            })
        
        return {
            'type': 'heatmap',
            'data': heatmap_data,
            'options': {
                'responsive': True,
                'maintainAspectRatio': False,
                'scales': {
                    'x': {'type': 'linear', 'position': 'bottom'},
                    'y': {'type': 'linear'}
                }
            }
        }
    
    @staticmethod
    def _generate_iran_map_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نقشه ایران"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        # نقشه‌برداری نام استان‌ها به کدهای نقشه
        province_codes = {
            'تهران': 'IR-23',
            'اصفهان': 'IR-10',
            'فارس': 'IR-07',
            'خراسان رضوی': 'IR-09',
            'خوزستان': 'IR-06',
            'مازندران': 'IR-02',
            'کرمان': 'IR-08',
            'آذربایجان شرقی': 'IR-03',
            'گیلان': 'IR-01',
            'مرکزی': 'IR-00',
            'آذربایجان غربی': 'IR-04',
            'کرمانشاه': 'IR-05'
            # ... سایر استان‌ها
        }
        
        map_data = []
        for item in raw_data:
            province_name = str(item.get(chart.x_axis_field, ''))
            province_code = province_codes.get(province_name, province_name)
            
            metric = chart.y_axis_metrics.first()
            value = item.get(metric.name if metric else 'count', 0)
            
            map_data.append({
                'code': province_code,
                'name': province_name,
                'value': value
            })
        
        return {
            'type': 'map_iran',
            'data': map_data,
            'options': {
                'responsive': True,
                'colorScale': ['#e6f3ff', '#0066cc'],
                'borderColor': '#ffffff',
                'borderWidth': 1
            }
        }
    
    @staticmethod
    def _generate_gauge_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های سنج"""
        metric = chart.y_axis_metrics.first()
        if metric:
            value = analyzer.calculate_metric(metric, filters)
        else:
            value = 0
        
        return {
            'type': 'gauge',
            'data': {
                'value': value,
                'min': 0,
                'max': 100,  # باید قابل تنظیم باشد
                'unit': metric.unit if metric else ''
            },
            'options': {
                'responsive': True,
                'arc': {
                    'backgroundColor': '#e6e6e6',
                    'borderColor': '#cccccc',
                    'borderWidth': 2
                },
                'needle': {
                    'color': '#ff6b6b'
                }
            }
        }
    
    @staticmethod
    def _generate_kpi_card_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های کارت KPI"""
        metric = chart.y_axis_metrics.first()
        if metric:
            current_value = analyzer.calculate_metric(metric, filters)
            # محاسبه مقدار قبلی برای مقایسه
            previous_value = current_value * 0.9  # موقت
            change = ((current_value - previous_value) / previous_value * 100) if previous_value else 0
        else:
            current_value = 0
            change = 0
        
        return {
            'type': 'kpi_card',
            'data': {
                'value': current_value,
                'change': round(change, 2),
                'trend': 'up' if change > 0 else 'down' if change < 0 else 'stable',
                'unit': metric.unit if metric else '',
                'title': metric.display_name if metric else chart.name
            }
        }
    
    @staticmethod
    def _generate_table_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های جدول"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        # تعیین ستون‌ها
        columns = [{'field': chart.x_axis_field, 'title': chart.x_axis_field}]
        for metric in chart.y_axis_metrics.all():
            columns.append({
                'field': metric.name,
                'title': metric.display_name,
                'type': 'number'
            })
        
        return {
            'type': 'table',
            'data': {
                'columns': columns,
                'rows': raw_data
            },
            'options': {
                'pagination': True,
                'pageSize': 10,
                'sortable': True,
                'filterable': True
            }
        }
    
    @staticmethod
    def _generate_scatter_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودار پراکندگی"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        datasets = []
        metrics = list(chart.y_axis_metrics.all())
        
        if len(metrics) >= 2:
            x_metric = metrics[0]
            y_metric = metrics[1]
            
            scatter_data = []
            for item in raw_data:
                x_value = item.get(x_metric.name, 0)
                y_value = item.get(y_metric.name, 0)
                scatter_data.append({'x': x_value, 'y': y_value})
            
            datasets.append({
                'label': f'{x_metric.display_name} vs {y_metric.display_name}',
                'data': scatter_data,
                'backgroundColor': 'rgba(54, 162, 235, 0.6)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'pointRadius': 5
            })
        
        return {
            'type': 'scatter',
            'data': {'datasets': datasets},
            'options': ChartDataGenerator._get_chart_options(chart)
        }
    
    @staticmethod
    def _generate_bubble_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودار حبابی"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        datasets = []
        metrics = list(chart.y_axis_metrics.all())
        
        if len(metrics) >= 3:
            x_metric = metrics[0]
            y_metric = metrics[1]
            r_metric = metrics[2]  # radius
            
            bubble_data = []
            for item in raw_data:
                x_value = item.get(x_metric.name, 0)
                y_value = item.get(y_metric.name, 0)
                r_value = item.get(r_metric.name, 5)  # default radius
                
                bubble_data.append({
                    'x': x_value,
                    'y': y_value,
                    'r': max(r_value / 100, 3)  # scale radius
                })
            
            datasets.append({
                'label': 'داده‌ها',
                'data': bubble_data,
                'backgroundColor': 'rgba(255, 99, 132, 0.6)',
                'borderColor': 'rgba(255, 99, 132, 1)'
            })
        
        return {
            'type': 'bubble',
            'data': {'datasets': datasets},
            'options': ChartDataGenerator._get_chart_options(chart)
        }
    
    @staticmethod
    def _generate_funnel_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودار قیف"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        # مرتب‌سازی داده‌ها نزولی برای قیف
        metric = chart.y_axis_metrics.first()
        if metric:
            raw_data.sort(key=lambda x: x.get(metric.name, 0), reverse=True)
        
        label_field = chart.group_by_field or chart.x_axis_field
        labels = [str(item[label_field]) for item in raw_data]
        values = [item.get(metric.name, 0) for item in raw_data] if metric else []
        
        return {
            'type': 'funnel',
            'data': {
                'labels': labels,
                'values': values
            },
            'options': {
                'responsive': True,
                'maintainAspectRatio': False
            }
        }
    
    @staticmethod
    def _generate_radar_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودار رادار"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        label_field = chart.group_by_field or chart.x_axis_field
        labels = [str(item[label_field]) for item in raw_data]
        
        datasets = []
        colors = ChartDataGenerator._get_color_palette(len(chart.y_axis_metrics.all()))
        
        for i, metric in enumerate(chart.y_axis_metrics.all()):
            data_values = [item.get(metric.name, 0) for item in raw_data]
            
            datasets.append({
                'label': metric.display_name,
                'data': data_values,
                'backgroundColor': colors[i]['background'],
                'borderColor': colors[i]['border'],
                'borderWidth': 2,
                'pointBackgroundColor': colors[i]['border']
            })
        
        return {
            'type': 'radar',
            'data': {
                'labels': labels,
                'datasets': datasets
            },
            'options': {
                'responsive': True,
                'scales': {
                    'r': {
                        'beginAtZero': True
                    }
                }
            }
        }
    
    @staticmethod
    def _generate_treemap_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نقشه درختی"""
        raw_data = analyzer.generate_grouped_data(chart, filters)
        
        treemap_data = []
        metric = chart.y_axis_metrics.first()
        label_field = chart.group_by_field or chart.x_axis_field
        
        for item in raw_data:
            label = str(item[label_field])
            value = item.get(metric.name, 0) if metric else 1
            
            treemap_data.append({
                'name': label,
                'value': value,
                'color': ChartDataGenerator._get_random_color()
            })
        
        return {
            'type': 'treemap',
            'data': treemap_data,
            'options': {
                'responsive': True,
                'maintainAspectRatio': False
            }
        }
    
    @staticmethod
    def _generate_sankey_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """تولید داده‌های نمودار سنکی"""
        # این نیاز به منطق پیچیده‌تری دارد
        # فعلاً یک پیاده‌سازی ساده ارائه می‌دهیم
        return {
            'type': 'sankey',
            'data': {
                'nodes': [],
                'links': []
            },
            'options': {
                'responsive': True
            }
        }
    
    @staticmethod
    def _get_color_palette(count: int) -> List[Dict[str, str]]:
        """تولید پالت رنگی"""
        base_colors = [
            {'background': 'rgba(54, 162, 235, 0.6)', 'border': 'rgba(54, 162, 235, 1)'},
            {'background': 'rgba(255, 99, 132, 0.6)', 'border': 'rgba(255, 99, 132, 1)'},
            {'background': 'rgba(255, 205, 86, 0.6)', 'border': 'rgba(255, 205, 86, 1)'},
            {'background': 'rgba(75, 192, 192, 0.6)', 'border': 'rgba(75, 192, 192, 1)'},
            {'background': 'rgba(153, 102, 255, 0.6)', 'border': 'rgba(153, 102, 255, 1)'},
            {'background': 'rgba(255, 159, 64, 0.6)', 'border': 'rgba(255, 159, 64, 1)'},
        ]
        
        colors = []
        for i in range(count):
            colors.append(base_colors[i % len(base_colors)])
        
        return colors
    
    @staticmethod
    def _get_random_color() -> str:
        """تولید رنگ تصادفی"""
        import random
        return f"#{random.randint(0, 0xFFFFFF):06x}"
    
    @staticmethod
    def _get_chart_options(chart: Chart) -> Dict:
        """تنظیمات عمومی نمودار"""
        options = {
            'responsive': True,
            'maintainAspectRatio': False,
            'plugins': {
                'title': {
                    'display': True,
                    'text': chart.name,
                    'font': {'size': 16}
                },
                'legend': {
                    'display': True,
                    'position': 'top'
                }
            },
            'scales': {
                'x': {
                    'display': True,
                    'title': {
                        'display': True,
                        'text': chart.x_axis_field
                    }
                },
                'y': {
                    'display': True,
                    'title': {
                        'display': True,
                        'text': 'مقدار'
                    }
                }
            }
        }
        
        # ادغام تنظیمات سفارشی
        if chart.chart_config:
            options.update(chart.chart_config)
        
        return options
    
    @staticmethod
    def _get_pie_chart_options(chart: Chart) -> Dict:
        """تنظیمات نمودار دایره‌ای"""
        options = {
            'responsive': True,
            'maintainAspectRatio': False,
            'plugins': {
                'title': {
                    'display': True,
                    'text': chart.name,
                    'font': {'size': 16}
                },
                'legend': {
                    'display': True,
                    'position': 'right'
                }
            }
        }
        
        if chart.chart_config:
            options.update(chart.chart_config)
        
        return options

    # ==============================================
    # نمودارهای تخصصی ژورقالای
    # ==============================================
    
    @staticmethod
    def _generate_purchase_timeline_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """نمودار خط زمانی خریدها - تحلیل روند خریدها در زمان"""
        try:
            # فرض بر این است که model مربوط به Purchase است
            from django.db.models import TruncDate, TruncWeek, TruncMonth
            
            queryset = analyzer.model.objects.all()
            if filters:
                queryset = analyzer.apply_filters(queryset, filters)
            
            # گروه‌بندی براساس تاریخ ایجاد
            period_field = 'created_at'
            
            if chart.time_period == 'day':
                queryset = queryset.annotate(period=TruncDate(period_field))
            elif chart.time_period == 'week':
                queryset = queryset.annotate(period=TruncWeek(period_field))
            elif chart.time_period == 'month':
                queryset = queryset.annotate(period=TruncMonth(period_field))
            else:
                queryset = queryset.annotate(period=TruncDate(period_field))
            
            # محاسبه آمار خریدها
            data = queryset.values('period').annotate(
                total_purchases=Count('id'),
                total_amount=Sum('amount_paid'),
                total_weight=Sum('order_weight'),
                avg_price=Avg('customer_price')
            ).order_by('period')
            
            periods = []
            purchase_counts = []
            amounts = []
            weights = []
            avg_prices = []
            
            for item in data:
                periods.append(item['period'].strftime('%Y-%m-%d') if item['period'] else 'نامشخص')
                purchase_counts.append(item['total_purchases'] or 0)
                amounts.append(item['total_amount'] or 0)
                weights.append(item['total_weight'] or 0)
                avg_prices.append(item['avg_price'] or 0)
            
            return {
                'type': 'line',
                'data': {
                    'labels': periods,
                    'datasets': [
                        {
                            'label': 'تعداد خریدها',
                            'data': purchase_counts,
                            'borderColor': 'rgb(75, 192, 192)',
                            'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                            'yAxisID': 'y'
                        },
                        {
                            'label': 'مبلغ کل (میلیون ریال)',
                            'data': [amount/1000000 for amount in amounts],
                            'borderColor': 'rgb(255, 99, 132)',
                            'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                            'yAxisID': 'y1'
                        }
                    ]
                },
                'options': {
                    'responsive': True,
                    'interaction': {'mode': 'index', 'intersect': False},
                    'scales': {
                        'x': {'display': True, 'title': {'display': True, 'text': 'تاریخ'}},
                        'y': {'type': 'linear', 'display': True, 'position': 'left', 'title': {'display': True, 'text': 'تعداد'}},
                        'y1': {'type': 'linear', 'display': True, 'position': 'right', 'title': {'display': True, 'text': 'مبلغ (میلیون ریال)'}, 'grid': {'drawOnChartArea': False}}
                    }
                }
            }
        except Exception as e:
            return {'error': f'خطا در تولید نمودار timeline: {str(e)}'}
    
    @staticmethod  
    def _generate_customer_activity_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """نمودار فعالیت مشتریان - تحلیل رفتار خرید مشتریان"""
        try:
            queryset = analyzer.model.objects.all()
            if filters:
                queryset = analyzer.apply_filters(queryset, filters)
            
            # تحلیل مشتریان براساس تعداد خرید و میزان خرید
            customer_data = queryset.values('customer__name', 'customer__city').annotate(
                purchase_count=Count('id'),
                total_amount=Sum('amount_paid'),
                total_weight=Sum('order_weight'),
                avg_amount=Avg('amount_paid')
            ).order_by('-total_amount')[:20]  # ۲۰ مشتری برتر
            
            customers = []
            purchase_counts = []
            total_amounts = []
            
            for item in customer_data:
                customer_name = item['customer__name'] or 'نامشخص'
                city = item['customer__city'] or ''
                display_name = f"{customer_name} ({city})" if city else customer_name
                
                customers.append(display_name)
                purchase_counts.append(item['purchase_count'] or 0)
                total_amounts.append((item['total_amount'] or 0) / 1000000)  # تبدیل به میلیون ریال
            
            return {
                'type': 'bar',
                'data': {
                    'labels': customers,
                    'datasets': [
                        {
                            'label': 'تعداد خرید',
                            'data': purchase_counts,
                            'backgroundColor': 'rgba(54, 162, 235, 0.6)',
                            'borderColor': 'rgba(54, 162, 235, 1)',
                            'yAxisID': 'y'
                        },
                        {
                            'label': 'مبلغ کل (میلیون ریال)',
                            'data': total_amounts,
                            'backgroundColor': 'rgba(255, 99, 132, 0.6)',
                            'borderColor': 'rgba(255, 99, 132, 1)',
                            'yAxisID': 'y1'
                        }
                    ]
                },
                'options': {
                    'responsive': True,
                    'scales': {
                        'x': {'display': True, 'title': {'display': True, 'text': 'مشتریان'}},
                        'y': {'type': 'linear', 'display': True, 'position': 'left', 'title': {'display': True, 'text': 'تعداد خرید'}},
                        'y1': {'type': 'linear', 'display': True, 'position': 'right', 'title': {'display': True, 'text': 'مبلغ (میلیون ریال)'}, 'grid': {'drawOnChartArea': False}}
                    }
                }
            }
        except Exception as e:
            return {'error': f'خطا در تولید نمودار مشتریان: {str(e)}'}
    
    @staticmethod
    def _generate_product_performance_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """نمودار عملکرد محصولات - تحلیل فروش براساس نوع محصول"""
        try:
            queryset = analyzer.model.objects.all()
            if filters:
                queryset = analyzer.apply_filters(queryset, filters)
            
            # تحلیل محصولات براساس فروش
            product_data = queryset.values('cargo__product_type', 'cargo__country').annotate(
                total_sales=Count('id'),
                total_weight=Sum('order_weight'),
                total_amount=Sum('amount_paid'),
                avg_price=Avg('customer_price')
            ).order_by('-total_weight')
            
            labels = []
            weights = []
            amounts = []
            colors = ChartDataGenerator._get_color_palette(len(product_data))
            
            for i, item in enumerate(product_data):
                product_type = item['cargo__product_type'] or 'نامشخص'
                country = item['cargo__country'] or ''
                label = f"{product_type} ({country})" if country else product_type
                
                labels.append(label)
                weights.append((item['total_weight'] or 0) / 1000)  # تبدیل به تن
                amounts.append((item['total_amount'] or 0) / 1000000)  # تبدیل به میلیون ریال
            
            return {
                'type': 'doughnut',
                'data': {
                    'labels': labels,
                    'datasets': [{
                        'label': 'وزن فروش (تن)',
                        'data': weights,
                        'backgroundColor': [color['background'] for color in colors],
                        'borderColor': [color['border'] for color in colors],
                        'borderWidth': 2
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {'display': True, 'text': 'توزیع فروش محصولات'},
                        'legend': {'position': 'right'}
                    }
                }
            }
        except Exception as e:
            return {'error': f'خطا در تولید نمودار محصولات: {str(e)}'}
    
    @staticmethod
    def _generate_barnameh_status_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """نمودار وضعیت بارنامه‌ها"""
        try:
            queryset = analyzer.model.objects.all()
            if filters:
                queryset = analyzer.apply_filters(queryset, filters)
            
            # تحلیل وضعیت بارنامه‌ها
            status_data = queryset.values('status').annotate(
                count=Count('id'),
                total_tonnage=Sum('tonnage')
            ).order_by('status')
            
            statuses = []
            counts = []
            tonnages = []
            colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
            
            for i, item in enumerate(status_data):
                status_display = {
                    'BARNAMEH_INCOMPLETE': 'بارنامه ناقص',
                    'BARNAMEH_COMPLETE': 'بارنامه کامل', 
                    'PURCHASE_CLOSED': 'خرید بسته شده'
                }.get(item['status'], item['status'])
                
                statuses.append(status_display)
                counts.append(item['count'] or 0)
                tonnages.append(item['total_tonnage'] or 0)
            
            return {
                'type': 'pie',
                'data': {
                    'labels': statuses,
                    'datasets': [{
                        'label': 'تعداد بارنامه',
                        'data': counts,
                        'backgroundColor': colors[:len(statuses)],
                        'borderWidth': 2
                    }]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {'display': True, 'text': 'توزیع وضعیت بارنامه‌ها'},
                        'legend': {'position': 'bottom'}
                    }
                }
            }
        except Exception as e:
            return {'error': f'خطا در تولید نمودار بارنامه: {str(e)}'}
    
    @staticmethod
    def _generate_sales_agent_comparison_data(chart: Chart, analyzer: DataAnalyzer, filters: Dict = None) -> Dict:
        """نمودار مقایسه عملکرد کارشناسان فروش"""
        try:
            queryset = analyzer.model.objects.all()
            if filters:
                queryset = analyzer.apply_filters(queryset, filters)
            
            # تحلیل عملکرد کارشناسان فروش
            agent_data = queryset.values('unique_sales_agent__name').annotate(
                total_sales=Count('id'),
                total_amount=Sum('amount_paid'),
                total_weight=Sum('order_weight'),
                avg_amount=Avg('amount_paid')
            ).order_by('-total_amount')
            
            agents = []
            sales_counts = []
            amounts = []
            weights = []
            
            for item in agent_data:
                agent_name = item['unique_sales_agent__name'] or 'نامشخص'
                agents.append(agent_name)
                sales_counts.append(item['total_sales'] or 0)
                amounts.append((item['total_amount'] or 0) / 1000000)  # میلیون ریال
                weights.append((item['total_weight'] or 0) / 1000)  # تن
            
            return {
                'type': 'radar',
                'data': {
                    'labels': agents,
                    'datasets': [
                        {
                            'label': 'تعداد فروش',
                            'data': sales_counts,
                            'borderColor': 'rgb(54, 162, 235)',
                            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                            'pointBackgroundColor': 'rgb(54, 162, 235)'
                        },
                        {
                            'label': 'مبلغ فروش (میلیون ریال)',
                            'data': amounts,
                            'borderColor': 'rgb(255, 99, 132)',
                            'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                            'pointBackgroundColor': 'rgb(255, 99, 132)'
                        }
                    ]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'title': {'display': True, 'text': 'مقایسه عملکرد کارشناسان فروش'}
                    },
                    'scales': {
                        'r': {'beginAtZero': True}
                    }
                }
            }
        except Exception as e:
            return {'error': f'خطا در تولید نمودار کارشناسان: {str(e)}'} 