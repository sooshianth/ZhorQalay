from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Dashboard, Chart, Widget, Report, DataSource, 
    MetricDefinition, KPI, Filter, UserPreference
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = '__all__'


class MetricDefinitionSerializer(serializers.ModelSerializer):
    data_source = DataSourceSerializer(read_only=True)
    data_source_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = MetricDefinition
        fields = '__all__'


class FilterSerializer(serializers.ModelSerializer):
    data_source = DataSourceSerializer(read_only=True)
    data_source_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Filter
        fields = '__all__'


class ChartSerializer(serializers.ModelSerializer):
    data_source = DataSourceSerializer(read_only=True)
    data_source_id = serializers.IntegerField(write_only=True)
    y_axis_metrics = MetricDefinitionSerializer(many=True, read_only=True)
    y_axis_metrics_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    
    class Meta:
        model = Chart
        fields = '__all__'
    
    def create(self, validated_data):
        y_axis_metrics_ids = validated_data.pop('y_axis_metrics_ids', [])
        chart = Chart.objects.create(**validated_data)
        
        if y_axis_metrics_ids:
            metrics = MetricDefinition.objects.filter(id__in=y_axis_metrics_ids)
            chart.y_axis_metrics.set(metrics)
        
        return chart
    
    def update(self, instance, validated_data):
        y_axis_metrics_ids = validated_data.pop('y_axis_metrics_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if y_axis_metrics_ids is not None:
            metrics = MetricDefinition.objects.filter(id__in=y_axis_metrics_ids)
            instance.y_axis_metrics.set(metrics)
        
        return instance


class WidgetSerializer(serializers.ModelSerializer):
    chart = ChartSerializer(read_only=True)
    chart_id = serializers.UUIDField(write_only=True)
    
    class Meta:
        model = Widget
        fields = '__all__'


class DashboardSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    allowed_users = UserSerializer(many=True, read_only=True)
    allowed_users_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    widgets = WidgetSerializer(many=True, read_only=True)
    widgets_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Dashboard
        fields = '__all__'
    
    def get_widgets_count(self, obj):
        return obj.widgets.filter(is_visible=True).count()
    
    def create(self, validated_data):
        allowed_users_ids = validated_data.pop('allowed_users_ids', [])
        dashboard = Dashboard.objects.create(**validated_data)
        
        if allowed_users_ids:
            users = User.objects.filter(id__in=allowed_users_ids)
            dashboard.allowed_users.set(users)
        
        return dashboard
    
    def update(self, instance, validated_data):
        allowed_users_ids = validated_data.pop('allowed_users_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if allowed_users_ids is not None:
            users = User.objects.filter(id__in=allowed_users_ids)
            instance.allowed_users.set(users)
        
        return instance


class ReportSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    data_source = DataSourceSerializer(read_only=True)
    data_source_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Report
        fields = '__all__'


class KPISerializer(serializers.ModelSerializer):
    metric = MetricDefinitionSerializer(read_only=True)
    metric_id = serializers.IntegerField(write_only=True)
    current_value = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = KPI
        fields = '__all__'
    
    def get_current_value(self, obj):
        # این مقدار باید از DataAnalyzer محاسبه شود
        return 0
    
    def get_status(self, obj):
        # وضعیت براساس آستانه‌ها
        return 'normal'


class UserPreferenceSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    default_dashboard = DashboardSerializer(read_only=True)
    default_dashboard_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = UserPreference
        fields = '__all__'


class ChartDataSerializer(serializers.Serializer):
    """Serializer برای داده‌های نمودار"""
    labels = serializers.ListField(child=serializers.CharField())
    datasets = serializers.ListField(child=serializers.DictField())
    options = serializers.DictField(required=False)
    
    def to_representation(self, instance):
        return {
            'labels': instance.get('labels', []),
            'datasets': instance.get('datasets', []),
            'options': instance.get('options', {})
        }


class FilterOptionsSerializer(serializers.Serializer):
    """Serializer برای گزینه‌های فیلتر"""
    field_name = serializers.CharField()
    options = serializers.ListField(child=serializers.DictField())


class DrillDownRequestSerializer(serializers.Serializer):
    """Serializer برای درخواست drill-down"""
    point = serializers.DictField()
    level = serializers.IntegerField(default=1)
    filters = serializers.DictField(default=dict)


class ExportRequestSerializer(serializers.Serializer):
    """Serializer برای درخواست صادرات"""
    type = serializers.ChoiceField(choices=['dashboard', 'chart', 'report'])
    format = serializers.ChoiceField(choices=['pdf', 'excel', 'csv', 'json'])
    data_id = serializers.UUIDField()
    filters = serializers.DictField(default=dict)
    options = serializers.DictField(default=dict)


class DashboardLayoutSerializer(serializers.Serializer):
    """Serializer برای layout داشبورد"""
    widgets = serializers.ListField(
        child=serializers.DictField()
    )
    
    def validate_widgets(self, value):
        required_fields = ['id', 'x', 'y', 'w', 'h']
        for widget in value:
            for field in required_fields:
                if field not in widget:
                    raise serializers.ValidationError(f"فیلد {field} برای ویجت الزامی است")
        return value


class DateRangeSerializer(serializers.Serializer):
    """Serializer برای محدوده تاریخ"""
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد")
        return data 