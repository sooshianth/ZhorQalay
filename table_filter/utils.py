import re
import json
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q, Count, Max, Min, Avg, Sum
from django.utils.dateparse import parse_date, parse_datetime
from typing import Dict, List, Any, Tuple, Optional


class ColumnTypeDetector:
    """کلاس تشخیص نوع ستون‌ها"""
    
    @staticmethod
    def detect_field_type(model, field_name: str) -> str:
        """تشخیص نوع فیلد بر اساس مدل Django"""
        try:
            field = model._meta.get_field(field_name)
            
            # فیلدهای عددی
            if isinstance(field, (models.IntegerField, models.BigIntegerField, 
                                 models.SmallIntegerField, models.PositiveIntegerField,
                                 models.PositiveSmallIntegerField, models.PositiveBigIntegerField,
                                 models.FloatField, models.DecimalField)):
                return 'number'
            
            # فیلدهای تاریخ و زمان
            elif isinstance(field, (models.DateField, models.DateTimeField)):
                return 'date'
            
            # فیلدهای بولین
            elif isinstance(field, models.BooleanField):
                return 'boolean'
            
            # فیلدهای انتخابی
            elif hasattr(field, 'choices') and field.choices:
                return 'choice'
            
            # فیلدهای کلید خارجی
            elif isinstance(field, (models.ForeignKey, models.OneToOneField)):
                return 'text'  # یا می‌توان بر اساس مدل مرتبط تشخیص داد
            
            # فیلدهای متنی
            else:
                return 'text'
                
        except FieldDoesNotExist:
            # اگر فیلد در مدل وجود نداشت، سعی در تشخیص بر اساس نام
            return ColumnTypeDetector.detect_by_name(field_name)
    
    @staticmethod
    def detect_by_name(field_name: str) -> str:
        """تشخیص نوع بر اساس نام فیلد"""
        field_name_lower = field_name.lower()
        
        # الگوهای مختلف برای تشخیص نوع
        if any(pattern in field_name_lower for pattern in 
               ['date', 'time', 'تاریخ', 'زمان', 'created', 'updated']):
            return 'date'
        
        if any(pattern in field_name_lower for pattern in 
               ['price', 'amount', 'count', 'weight', 'quantity', 
                'قیمت', 'مبلغ', 'تعداد', 'وزن', 'مقدار', 'number', 'num']):
            return 'number'
        
        if any(pattern in field_name_lower for pattern in 
               ['status', 'state', 'وضعیت', 'حالت', 'type', 'نوع']):
            return 'status'
        
        if any(pattern in field_name_lower for pattern in 
               ['is_', 'has_', 'active', 'enabled', 'فعال', 'غیرفعال']):
            return 'boolean'
        
        return 'text'
    
    @staticmethod
    def detect_by_sample_data(values: List[Any]) -> str:
        """تشخیص نوع بر اساس نمونه داده‌ها"""
        if not values:
            return 'text'
        
        # فیلتر کردن مقادیر خالی
        clean_values = [v for v in values if v is not None and str(v).strip()]
        if not clean_values:
            return 'text'
        
        # تعداد نمونه‌ها برای هر نوع
        number_count = 0
        date_count = 0
        boolean_count = 0
        
        for value in clean_values[:10]:  # فقط 10 نمونه اول
            str_value = str(value).strip()
            
            # بررسی عدد
            if ColumnTypeDetector._is_number(str_value):
                number_count += 1
            
            # بررسی تاریخ
            elif ColumnTypeDetector._is_date(str_value):
                date_count += 1
            
            # بررسی بولین
            elif ColumnTypeDetector._is_boolean(str_value):
                boolean_count += 1
        
        total = len(clean_values[:10])
        
        # تصمیم‌گیری بر اساس درصد
        if number_count / total > 0.7:
            return 'number'
        elif date_count / total > 0.7:
            return 'date'
        elif boolean_count / total > 0.7:
            return 'boolean'
        else:
            return 'text'
    
    @staticmethod
    def _is_number(value: str) -> bool:
        """بررسی عددی بودن مقدار"""
        try:
            # حذف کاما و فاصله
            clean_value = re.sub(r'[,\s]', '', value)
            # تبدیل اعداد فارسی به انگلیسی
            clean_value = ColumnTypeDetector._persian_to_english_digits(clean_value)
            float(clean_value)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def _is_date(value: str) -> bool:
        """بررسی تاریخ بودن مقدار"""
        # الگوهای مختلف تاریخ
        date_patterns = [
            r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # 2023-12-01 یا 2023/12/01
            r'^\d{1,2}[-/]\d{1,2}[-/]\d{4}',  # 01-12-2023 یا 01/12/2023
            r'^\d{4}\/\d{1,2}\/\d{1,2}',      # 1402/09/10 (شمسی)
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, value):
                return True
        
        # تلاش برای پارس کردن با Django
        try:
            parse_date(value) or parse_datetime(value)
            return True
        except:
            return False
    
    @staticmethod
    def _is_boolean(value: str) -> bool:
        """بررسی بولین بودن مقدار"""
        boolean_values = {
            'true', 'false', 'yes', 'no', 'بله', 'خیر', 
            'فعال', 'غیرفعال', '1', '0', 'on', 'off'
        }
        return value.lower() in boolean_values
    
    @staticmethod
    def _persian_to_english_digits(text: str) -> str:
        """تبدیل اعداد فارسی به انگلیسی"""
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        english_digits = '0123456789'
        
        for persian, english in zip(persian_digits, english_digits):
            text = text.replace(persian, english)
        
        return text


class TableFilterProcessor:
    """کلاس پردازش فیلترها و مرتب‌سازی"""
    
    def __init__(self, queryset, table_name: str):
        self.queryset = queryset
        self.model = queryset.model
        self.table_name = table_name
        self._original_queryset = queryset.all()
    
    def apply_filters(self, filter_config: Dict[str, Any]) -> models.QuerySet:
        """اعمال فیلترها روی queryset"""
        filtered_queryset = self.queryset
        
        for column_id, filter_data in filter_config.items():
            if not filter_data or not filter_data.get('values'):
                continue
            
            filter_type = filter_data.get('type', 'include')
            values = filter_data.get('values', [])
            
            if filter_type == 'include':
                filtered_queryset = self._apply_include_filter(
                    filtered_queryset, column_id, values
                )
            elif filter_type == 'exclude':
                filtered_queryset = self._apply_exclude_filter(
                    filtered_queryset, column_id, values
                )
        
        return filtered_queryset
    
    def _apply_include_filter(self, queryset: models.QuerySet, 
                            column_id: str, values: List[str]) -> models.QuerySet:
        """اعمال فیلتر شامل"""
        if not values:
            return queryset
        
        # تشخیص نوع فیلد
        field_type = ColumnTypeDetector.detect_field_type(self.model, column_id)
        
        if field_type == 'boolean':
            # تبدیل مقادیر بولین
            bool_values = []
            for value in values:
                if value.lower() in ['بله', 'true', '1', 'فعال']:
                    bool_values.append(True)
                elif value.lower() in ['خیر', 'false', '0', 'غیرفعال']:
                    bool_values.append(False)
            
            if bool_values:
                return queryset.filter(**{f'{column_id}__in': bool_values})
        
        elif field_type == 'number':
            # تبدیل مقادیر عددی
            numeric_values = []
            for value in values:
                try:
                    clean_value = re.sub(r'[,\s]', '', value)
                    clean_value = ColumnTypeDetector._persian_to_english_digits(clean_value)
                    numeric_values.append(Decimal(clean_value))
                except:
                    continue
            
            if numeric_values:
                return queryset.filter(**{f'{column_id}__in': numeric_values})
        
        elif field_type == 'date':
            # تبدیل مقادیر تاریخ
            date_values = []
            for value in values:
                try:
                    date_obj = parse_date(value) or parse_datetime(value)
                    if date_obj:
                        date_values.append(date_obj)
                except:
                    continue
            
            if date_values:
                return queryset.filter(**{f'{column_id}__in': date_values})
        
        else:
            # فیلتر متنی - جستجوی دقیق یا شامل
            q_objects = Q()
            for value in values:
                q_objects |= Q(**{f'{column_id}__icontains': value})
            
            return queryset.filter(q_objects)
        
        return queryset
    
    def _apply_exclude_filter(self, queryset: models.QuerySet,
                            column_id: str, values: List[str]) -> models.QuerySet:
        """اعمال فیلتر حذف"""
        # مشابه include اما با exclude
        include_result = self._apply_include_filter(self._original_queryset, column_id, values)
        return queryset.exclude(id__in=include_result.values_list('id', flat=True))
    
    def apply_sorting(self, sort_config: Dict[str, str]) -> models.QuerySet:
        """اعمال مرتب‌سازی"""
        if not sort_config:
            return self.queryset
        
        order_fields = []
        
        for column_id, direction in sort_config.items():
            if direction == 'desc':
                order_fields.append(f'-{column_id}')
            else:
                order_fields.append(column_id)
        
        if order_fields:
            return self.queryset.order_by(*order_fields)
        
        return self.queryset
    
    def get_column_values(self, column_id: str, limit: int = 1000) -> List[Dict]:
        """دریافت مقادیر منحصر به فرد یک ستون"""
        try:
            # استفاده از values_list برای عملکرد بهتر
            values = (self.queryset
                     .values_list(column_id, flat=True)
                     .distinct()
                     .order_by(column_id)[:limit])
            
            # تبدیل به لیست مقادیر با تعداد
            result = []
            for value in values:
                if value is not None:
                    count = self.queryset.filter(**{column_id: value}).count()
                    result.append({
                        'value': str(value),
                        'count': count,
                        'display': self._format_display_value(value, column_id)
                    })
            
            return result
            
        except Exception as e:
            print(f"Error getting column values for {column_id}: {e}")
            return []
    
    def _format_display_value(self, value: Any, column_id: str) -> str:
        """فرمت نمایش مقدار"""
        if value is None:
            return ''
        
        field_type = ColumnTypeDetector.detect_field_type(self.model, column_id)
        
        if field_type == 'boolean':
            return 'بله' if value else 'خیر'
        elif field_type == 'date':
            if hasattr(value, 'strftime'):
                return value.strftime('%Y/%m/%d')
        elif field_type == 'number':
            if isinstance(value, (int, float, Decimal)):
                return f"{value:,.0f}" if isinstance(value, int) else f"{value:,.2f}"
        
        return str(value)
    
    def get_table_stats(self) -> Dict[str, Any]:
        """دریافت آمار جدول"""
        total_count = self.queryset.count()
        
        stats = {
            'total_count': total_count,
            'columns': {}
        }
        
        # آمار برای هر ستون
        for field in self.model._meta.fields:
            field_name = field.name
            field_type = ColumnTypeDetector.detect_field_type(self.model, field_name)
            
            column_stats = {
                'type': field_type,
                'non_null_count': self.queryset.filter(**{f'{field_name}__isnull': False}).count()
            }
            
            # آمار اضافی برای فیلدهای عددی
            if field_type == 'number':
                try:
                    aggregates = self.queryset.aggregate(
                        min_val=Min(field_name),
                        max_val=Max(field_name),
                        avg_val=Avg(field_name),
                        sum_val=Sum(field_name)
                    )
                    column_stats.update(aggregates)
                except:
                    pass
            
            stats['columns'][field_name] = column_stats
        
        return stats


class FilterValueExtractor:
    """کلاس استخراج مقادیر از سلول‌های HTML"""
    
    @staticmethod
    def extract_from_html(html_content: str, column_type: str = 'text') -> str:
        """استخراج مقدار از محتوای HTML"""
        if not html_content:
            return ''
        
        # حذف تگ‌های HTML
        import re
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if column_type == 'boolean':
            # بررسی آیکون‌ها و کلاس‌ها
            if 'fa-check' in html_content or 'fa-star' in html_content:
                return 'بله'
            elif 'fa-times' in html_content or 'fa-star-o' in html_content:
                return 'خیر'
        
        return text
    
    @staticmethod
    def extract_from_cell_data(cell_data: Dict[str, Any], column_type: str = 'text') -> str:
        """استخراج مقدار از داده‌های سلول"""
        # اگر data-value موجود است
        if 'data_value' in cell_data:
            return str(cell_data['data_value'])
        
        # اگر محتوای متنی موجود است
        if 'text' in cell_data:
            return FilterValueExtractor.extract_from_html(cell_data['text'], column_type)
        
        return ''


class FilterConfigurationManager:
    """مدیریت تنظیمات فیلتر جداول"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
    
    def get_or_create_column_config(self, column_id: str, column_name: str, 
                                  model_class=None) -> 'TableFilterConfiguration':
        """دریافت یا ایجاد تنظیمات ستون"""
        from .models import TableFilterConfiguration
        
        config, created = TableFilterConfiguration.objects.get_or_create(
            table_name=self.table_name,
            column_id=column_id,
            defaults={
                'column_name': column_name,
                'column_type': self._detect_column_type(column_id, model_class),
                'is_filterable': True,
                'is_sortable': True,
                'is_visible': True,
            }
        )
        
        return config
    
    def _detect_column_type(self, column_id: str, model_class=None) -> str:
        """تشخیص نوع ستون"""
        if model_class:
            return ColumnTypeDetector.detect_field_type(model_class, column_id)
        else:
            return ColumnTypeDetector.detect_by_name(column_id)
    
    def get_table_configuration(self) -> List['TableFilterConfiguration']:
        """دریافت تنظیمات کامل جدول"""
        from .models import TableFilterConfiguration
        
        return TableFilterConfiguration.objects.filter(
            table_name=self.table_name
        ).order_by('column_order', 'column_id')
    
    def update_column_order(self, column_orders: Dict[str, int]):
        """بروزرسانی ترتیب ستون‌ها"""
        from .models import TableFilterConfiguration
        
        for column_id, order in column_orders.items():
            TableFilterConfiguration.objects.filter(
                table_name=self.table_name,
                column_id=column_id
            ).update(column_order=order)
    
    def toggle_column_visibility(self, column_id: str, is_visible: bool):
        """تغییر وضعیت نمایش ستون"""
        from .models import TableFilterConfiguration
        
        TableFilterConfiguration.objects.filter(
            table_name=self.table_name,
            column_id=column_id
        ).update(is_visible=is_visible)


class UserFilterStateManager:
    """مدیریت وضعیت فیلتر کاربران"""
    
    def __init__(self, user, table_name: str):
        self.user = user
        self.table_name = table_name
    
    def save_filter_state(self, filter_state: Dict, sort_state: Dict = None,
                         column_visibility: Dict = None):
        """ذخیره وضعیت فیلتر کاربر"""
        from .models import UserTableFilterState
        
        state, created = UserTableFilterState.objects.get_or_create(
            user=self.user,
            table_name=self.table_name,
            defaults={
                'filter_state_json': json.dumps(filter_state, ensure_ascii=False),
                'sort_state_json': json.dumps(sort_state or {}, ensure_ascii=False),
                'column_visibility_json': json.dumps(column_visibility or {}, ensure_ascii=False),
            }
        )
        
        if not created:
            state.filter_state = filter_state
            if sort_state is not None:
                state.sort_state = sort_state
            if column_visibility is not None:
                state.column_visibility = column_visibility
            state.save()
        
        return state
    
    def get_filter_state(self) -> Tuple[Dict, Dict, Dict]:
        """دریافت وضعیت فیلتر کاربر"""
        from .models import UserTableFilterState
        
        try:
            state = UserTableFilterState.objects.get(
                user=self.user,
                table_name=self.table_name
            )
            return state.filter_state, state.sort_state, state.column_visibility
        except UserTableFilterState.DoesNotExist:
            return {}, {}, {}
    
    def clear_filter_state(self):
        """پاک کردن وضعیت فیلتر کاربر"""
        from .models import UserTableFilterState
        
        UserTableFilterState.objects.filter(
            user=self.user,
            table_name=self.table_name
        ).delete()


def get_model_from_table_name(table_name: str):
    """دریافت مدل بر اساس نام جدول"""
    # این تابع باید بر اساس نحوه نام‌گذاری جداول در پروژه شما تنظیم شود
    
    # نمونه: اگر table_name به صورت "app_name.model_name" باشد
    if '.' in table_name:
        app_name, model_name = table_name.split('.', 1)
        try:
            return apps.get_model(app_name, model_name)
        except:
            pass
    
    # جستجو در همه اپلیکیشن‌ها
    for app_config in apps.get_app_configs():
        for model in app_config.get_models():
            if model._meta.model_name == table_name.lower():
                return model
            if f"{model._meta.app_label}_{model._meta.model_name}" == table_name.lower():
                return model
    
    return None 