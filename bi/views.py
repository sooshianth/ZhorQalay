from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Avg, Q, F
from django.utils import timezone
from django.apps import apps
# Cache imports removed - focusing on direct data processing
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import json
from datetime import datetime, timedelta
from .models import Dashboard, Chart, Widget, Report, DataSource, MetricDefinition, KPI, Filter
from .utils.data_analyzer import DataAnalyzer
from .utils.chart_generator import ChartDataGenerator
from .utils.geo_analyzer import GeographicAnalyzer
from .serializers import DashboardSerializer, ChartSerializer, WidgetSerializer


class DashboardView(LoginRequiredMixin, TemplateView):
    """صفحه اصلی داشبورد"""
    template_name = 'bi/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard_id = self.kwargs.get('dashboard_id')
        
        if dashboard_id:
            dashboard = get_object_or_404(Dashboard.objects.filter(
                Q(owner=self.request.user) | Q(is_public=True) | Q(allowed_users=self.request.user)
            ), id=dashboard_id)
        else:
            # داشبورد پیش‌فرض کاربر یا اولین داشبورد عمومی
            dashboard = Dashboard.objects.filter(
                Q(owner=self.request.user) | Q(is_public=True)
            ).first()
        
        context.update({
            'dashboard': dashboard,
            'widgets': dashboard.widgets.filter(is_visible=True) if dashboard else [],
            'user_dashboards': Dashboard.objects.filter(
                Q(owner=self.request.user) | Q(allowed_users=self.request.user)
            ).distinct()
        })
        return context


class DashboardViewSet(viewsets.ModelViewSet):
    """API برای مدیریت داشبوردها"""
    serializer_class = DashboardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Dashboard.objects.filter(
            Q(owner=self.request.user) | Q(is_public=True) | Q(allowed_users=self.request.user)
        ).distinct()
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)
    
    @action(detail=True, methods=['get'])
    def widgets(self, request, pk=None):
        """دریافت ویجت‌های داشبورد"""
        dashboard = self.get_object()
        widgets = dashboard.widgets.filter(is_visible=True)
        data = []
        
        for widget in widgets:
            try:
                chart_data = ChartDataGenerator.generate_chart_data(
                    widget.chart, 
                    filters=request.GET.dict()
                )
                data.append({
                    'id': str(widget.id),
                    'title': widget.title,
                    'chart_type': widget.chart.chart_type,
                    'size': widget.size,
                    'position': {
                        'x': widget.position_x,
                        'y': widget.position_y,
                        'w': widget.width,
                        'h': widget.height
                    },
                    'data': chart_data,
                    'config': widget.widget_config
                })
            except Exception as e:
                data.append({
                    'id': str(widget.id),
                    'title': widget.title,
                    'error': str(e)
                })
        
        return Response(data)


class ChartDataView(LoginRequiredMixin, TemplateView):
    """API برای دریافت داده‌های نمودار"""
    
    def get(self, request, chart_id):
        chart = get_object_or_404(Chart, id=chart_id)
        filters = request.GET.dict()
        
        try:
            chart_data = ChartDataGenerator.generate_chart_data(chart, filters)
            return JsonResponse(chart_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class DrillDownView(LoginRequiredMixin, TemplateView):
    """API برای drill-down"""
    
    def post(self, request, chart_id):
        chart = get_object_or_404(Chart, id=chart_id)
        drill_data = json.loads(request.body)
        
        try:
            analyzer = DataAnalyzer(chart.data_source)
            result = analyzer.drill_down(
                chart=chart,
                drill_point=drill_data.get('point'),
                drill_level=drill_data.get('level', 1),
                filters=drill_data.get('filters', {})
            )
            
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class KPIDataView(LoginRequiredMixin, TemplateView):
    """API برای داده‌های KPI"""
    
    def get(self, request):
        kpis = KPI.objects.filter(is_active=True)
        kpi_data = []
        
        for kpi in kpis:
            try:
                analyzer = DataAnalyzer(kpi.metric.data_source)
                current_value = analyzer.calculate_kpi_value(kpi)
                previous_value = analyzer.calculate_kpi_previous_value(kpi)
                
                # محاسبه تغییر
                change = 0
                if previous_value and previous_value != 0:
                    change = ((current_value - previous_value) / previous_value) * 100
                
                # تعیین وضعیت
                status = 'normal'
                if kpi.critical_threshold and current_value <= kpi.critical_threshold:
                    status = 'critical'
                elif kpi.warning_threshold and current_value <= kpi.warning_threshold:
                    status = 'warning'
                elif kpi.target_value and current_value >= kpi.target_value:
                    status = 'good'
                
                kpi_data.append({
                    'id': kpi.id,
                    'name': kpi.display_name,
                    'value': current_value,
                    'formatted_value': kpi.format_string.format(value=current_value),
                    'change': round(change, 2),
                    'status': status,
                    'trend': kpi.trend_type,
                    'icon': kpi.icon,
                    'color_config': kpi.color_config
                })
            except Exception as e:
                kpi_data.append({
                    'id': kpi.id,
                    'name': kpi.display_name,
                    'error': str(e)
                })
        
        return JsonResponse({'kpis': kpi_data})


class GeoAnalyticsView(LoginRequiredMixin, TemplateView):
    """تحلیل‌های جغرافیایی"""
    
    def get(self, request):
        try:
            geo_analyzer = GeographicAnalyzer()
            
            # تحلیل براساس استان
            province_data = geo_analyzer.get_sales_by_province()
            
            # تحلیل براساس شهر
            city_data = geo_analyzer.get_sales_by_city()
            
            # نقشه حرارتی
            heatmap_data = geo_analyzer.generate_heatmap_data()
            
            return JsonResponse({
                'provinces': province_data,
                'cities': city_data,
                'heatmap': heatmap_data
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class ReportGeneratorView(LoginRequiredMixin, TemplateView):
    """تولید گزارش‌ها"""
    
    def post(self, request, report_id):
        report = get_object_or_404(Report, id=report_id)
        filters = json.loads(request.body).get('filters', {})
        
        try:
            analyzer = DataAnalyzer(report.data_source)
            report_data = analyzer.generate_report_data(report, filters)
            
            return JsonResponse({
                'data': report_data,
                'metadata': {
                    'generated_at': timezone.now().isoformat(),
                    'filters_applied': filters,
                    'total_records': len(report_data)
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class FilterOptionsView(LoginRequiredMixin, TemplateView):
    """دریافت گزینه‌های فیلتر"""
    
    def get(self, request, data_source_id):
        data_source = get_object_or_404(DataSource, id=data_source_id)
        field_name = request.GET.get('field')
        
        if not field_name:
            return JsonResponse({'error': 'فیلد مشخص نشده'}, status=400)
        
        try:
            analyzer = DataAnalyzer(data_source)
            options = analyzer.get_field_options(field_name)
            
            return JsonResponse({'options': options})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)





class DataSourceExploreView(LoginRequiredMixin, TemplateView):
    """کاوش منابع داده"""
    
    def get(self, request, data_source_id):
        data_source = get_object_or_404(DataSource, id=data_source_id)
        
        try:
            analyzer = DataAnalyzer(data_source)
            schema = analyzer.get_data_source_schema()
            sample_data = analyzer.get_sample_data(limit=10)
            
            return JsonResponse({
                'schema': schema,
                'sample_data': sample_data,
                'record_count': analyzer.get_record_count()
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)





class ExportView(LoginRequiredMixin, TemplateView):
    """صادرات داده‌ها"""
    
    def post(self, request):
        export_data = json.loads(request.body)
        export_type = export_data.get('type')  # dashboard, chart, report
        export_format = export_data.get('format')  # pdf, excel, csv
        
        try:
            if export_type == 'dashboard':
                # صادرات داشبورد
                pass
            elif export_type == 'chart':
                # صادرات نمودار
                pass
            elif export_type == 'report':
                # صادرات گزارش
                pass
            
            return JsonResponse({'message': 'در حال آماده‌سازی فایل...'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# ==============================================
# View های تخصصی ژورقالای
# ==============================================

class SpecializedChartsView(LoginRequiredMixin, TemplateView):
    """View ویژه برای نمودارهای تخصصی ژورقالای"""
    
    def get(self, request, chart_type):
        """دریافت داده‌های نمودارهای تخصصی"""
        try:
            from core.PurchaseModel import Purchase
            from bi.models import DataSource
            
            # ایجاد DataSource برای Purchase model
            purchase_data_source, created = DataSource.objects.get_or_create(
                name='Purchase Data',
                type='model',
                app_name='core',
                model_name='Purchase'
            )
            
            # ایجاد Chart object موقت
            chart = type('Chart', (), {
                'chart_type': chart_type,
                'data_source': purchase_data_source,
                'time_period': request.GET.get('time_period', 'month'),
                'name': f'نمودار {chart_type}'
            })()
            
            filters = {k: v for k, v in request.GET.items() if k != 'time_period'}
            
            chart_data = ChartDataGenerator.generate_chart_data(chart, filters)
            
            return JsonResponse(chart_data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class AnalyticsDataView(LoginRequiredMixin, TemplateView):
    """API برای تحلیل‌های پیشرفته"""
    
    def get(self, request, analysis_type):
        """دریافت تحلیل‌های مختلف"""
        try:
            from bi.models import DataSource
            
            # ایجاد DataSource برای Purchase model
            purchase_data_source, created = DataSource.objects.get_or_create(
                name='Purchase Data',
                type='model',
                app_name='core',
                model_name='Purchase'
            )
            
            analyzer = DataAnalyzer(purchase_data_source)
            filters = request.GET.dict()
            
            if analysis_type == 'purchase':
                data = analyzer.get_purchase_analytics(filters)
            elif analysis_type == 'customer':
                data = analyzer.get_customer_analytics(filters)
            elif analysis_type == 'product':
                data = analyzer.get_product_analytics(filters)
            elif analysis_type == 'sales_agent':
                data = analyzer.get_sales_agent_analytics(filters)
            elif analysis_type == 'geographic':
                data = analyzer.get_geographic_analytics(filters)
            else:
                return JsonResponse({'error': 'نوع تحلیل نامشخص'}, status=400)
            
            return JsonResponse(data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class DashboardQuickStatsView(LoginRequiredMixin, TemplateView):
    """آمار سریع برای داشبورد اصلی"""
    
    def get(self, request):
        """دریافت آمار کلی سیستم"""
        try:
            from core.PurchaseModel import Purchase
            from core.CustomerModel import Customer
            from core.CargoProductModel import CargoProduct
            from bki_barnameh.models.BarnamehModel import Barnameh
            from django.utils import timezone
            from datetime import timedelta
            
            # محاسبه آمار کلی
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            this_month = today.replace(day=1)
            
            stats = {
                # آمار خریدها
                'purchases': {
                    'total': Purchase.objects.count(),
                    'today': Purchase.objects.filter(created_at__date=today).count(),
                    'this_month': Purchase.objects.filter(created_at__gte=this_month).count(),
                    'pending': Purchase.objects.filter(state__in=['INITIATED', 'SMS_SENT']).count(),
                    'completed': Purchase.objects.filter(state='FULLY_SETTLED').count()
                },
                
                # آمار مالی
                'financial': {
                    'total_revenue': Purchase.objects.aggregate(
                        total=Sum('amount_paid')
                    )['total'] or 0,
                    'today_revenue': Purchase.objects.filter(
                        created_at__date=today
                    ).aggregate(total=Sum('amount_paid'))['total'] or 0,
                    'avg_order_value': Purchase.objects.aggregate(
                        avg=Avg('amount_paid')
                    )['avg'] or 0
                },
                
                # آمار مشتریان
                'customers': {
                    'total': Customer.objects.count(),
                    'active': Customer.objects.filter(is_active=True).count(),
                    'new_today': Customer.objects.filter(created_at__date=today).count(),
                    'with_purchases': Customer.objects.filter(
                        purchases_made__isnull=False
                    ).distinct().count()
                },
                
                # آمار محصولات
                'products': {
                    'total': CargoProduct.objects.count(),
                    'active': CargoProduct.objects.filter(status=True).count(),
                    'low_stock': CargoProduct.objects.filter(weight__lt=50000).count(),
                    'total_inventory': CargoProduct.objects.aggregate(
                        total=Sum('weight')
                    )['total'] or 0
                },
                
                # آمار بارنامه‌ها
                'barnameh': {
                    'total': Barnameh.objects.count(),
                    'complete': Barnameh.objects.filter(status='BARNAMEH_COMPLETE').count(),
                    'incomplete': Barnameh.objects.filter(status='BARNAMEH_INCOMPLETE').count(),
                    'today': Barnameh.objects.filter(barnameh_created_at__date=today).count()
                }
            }
            
            return JsonResponse(stats)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)



