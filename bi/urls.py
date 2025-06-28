from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'bi'

# Router برای API های REST
router = DefaultRouter()
router.register(r'dashboards', views.DashboardViewSet, basename='dashboard')

urlpatterns = [
    # صفحات اصلی
    path('', views.DashboardView.as_view(), name='dashboard_home'),
    path('dashboard/<uuid:dashboard_id>/', views.DashboardView.as_view(), name='dashboard_detail'),

    
    # API های نمودارها
    path('api/chart/<uuid:chart_id>/data/', views.ChartDataView.as_view(), name='chart_data'),
    path('api/chart/<uuid:chart_id>/drill-down/', views.DrillDownView.as_view(), name='drill_down'),

    
    # API های KPI
    path('api/kpis/', views.KPIDataView.as_view(), name='kpi_data'),
    
    # API های جغرافیایی
    path('api/geo-analytics/', views.GeoAnalyticsView.as_view(), name='geo_analytics'),
    
    # API های گزارش
    path('api/report/<uuid:report_id>/generate/', views.ReportGeneratorView.as_view(), name='generate_report'),
    
    # API های فیلتر
    path('api/data-source/<int:data_source_id>/filters/', views.FilterOptionsView.as_view(), name='filter_options'),
    path('api/data-source/<int:data_source_id>/explore/', views.DataSourceExploreView.as_view(), name='explore_data_source'),
    
    # API صادرات
    path('api/export/', views.ExportView.as_view(), name='export_data'),
    
    # API های تخصصی ژورقالای
    path('api/specialized-chart/<str:chart_type>/', views.SpecializedChartsView.as_view(), name='specialized_chart'),
    path('api/analytics/<str:analysis_type>/', views.AnalyticsDataView.as_view(), name='analytics_data'),
    path('api/quick-stats/', views.DashboardQuickStatsView.as_view(), name='quick_stats'),

    
    # REST API Router
    path('api/', include(router.urls)),
]
