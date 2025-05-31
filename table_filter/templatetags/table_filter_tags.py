from django import template
from django.utils.safestring import mark_safe
from django.templatetags.static import static
import json

register = template.Library()


@register.simple_tag
def table_filter_scripts():
    """
    Load table filter CSS and JavaScript files
    """
    return mark_safe("""
        <link rel="stylesheet" href="/static/table_filter/css/table_filter.css">
        <script src="/static/table_filter/js/table_filter.js"></script>
    """)


@register.simple_tag
def table_filter_init(table_selector='table', **kwargs):
    """
    Initialize table filter for specific table selector with configuration
    
    Usage:
    {% table_filter_init 'table' enable_toast=True enable_summary=True %}
    {% table_filter_init '#my-table' column_config='{}' %}
    """
    config = {
        'tableSelector': table_selector,
        'enableToast': kwargs.get('enable_toast', True),
        'enableIndicators': kwargs.get('enable_indicators', True),
        'enableSummary': kwargs.get('enable_summary', True),
        'enableClearAll': kwargs.get('enable_clear_all', True),
        'autoDetectColumns': kwargs.get('auto_detect_columns', True),
        'filterButtonClass': kwargs.get('filter_button_class', 'filter-dropdown-btn'),
    }
    
    # اضافه کردن تنظیمات ستون‌ها اگر ارائه شده باشد
    if 'column_config' in kwargs:
        config['columnConfig'] = kwargs['column_config']
    
    config_str = str(config).replace("'", '"').replace('True', 'true').replace('False', 'false')
    
    script = f"""
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            window.tableFilterInstance = createTableFilter({config_str});
        }});
    </script>
    """
    
    return mark_safe(script)


@register.simple_tag
def enable_table_filter():
    """Enable table filtering functionality"""
    return mark_safe("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Table filter functionality will be loaded here
                console.log('Table filter enabled');
            });
        </script>
    """)


@register.simple_tag
def table_filter_column(column_id, column_name=None, column_type='text'):
    """
    Add filter-specific attributes to table header
    
    Usage:
    <th {% table_filter_column 'customer' 'نام مشتری' 'text' %}>نام مشتری</th>
    <th {% table_filter_column 'amount' 'مبلغ' 'number' %}>مبلغ</th>
    """
    attrs = f'class="column-{column_id}"'
    
    if column_name:
        attrs += f' data-column-name="{column_name}"'
    
    if column_type:
        attrs += f' data-column-type="{column_type}"'
    
    return mark_safe(attrs)


@register.filter
def add_table_filter_classes(table_class=''):
    """
    Add necessary classes to table for filter functionality
    
    Usage:
    <table class="{{ 'table table-striped'|add_table_filter_classes }}">
    """
    base_classes = 'table-filterable enable-filter'
    
    if table_class:
        return f"{table_class} {base_classes}"
    else:
        return base_classes


@register.simple_tag
def auto_table_filter(class_name='enable-filter'):
    """
    Auto-enable table filter for tables with specific class
    
    Usage:
    {% auto_table_filter 'my-filter-class' %}
    """
    script = f"""
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            const tables = document.querySelectorAll('.{class_name}');
            tables.forEach(function(table) {{
                if (!table.id) {{
                    table.id = 'auto-table-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
                }}
                new TableFilter({{
                    tableSelector: '#' + table.id,
                    enableToast: true,
                    enableIndicators: true,
                    enableSummary: true,
                    enableClearAll: true
                }});
            }});
        }});
    </script>
    """
    
    return mark_safe(script)


@register.inclusion_tag('table_filter/table_filter_config.html')
def table_filter_config(config_dict):
    """
    Generate JavaScript configuration from Python dictionary
    
    Usage:
    {% table_filter_config my_config_dict %}
    """
    return {'config': config_dict}


@register.simple_tag
def table_filter_quick_setup(table_id, columns_config=None):
    """
    Quick setup for table filter with minimal configuration
    
    Usage:
    {% table_filter_quick_setup 'myTable' %}
    {% table_filter_quick_setup 'purchaseTable' columns_config %}
    """
    base_config = {
        'tableSelector': f'#{table_id}',
        'enableToast': True,
        'enableIndicators': True,
        'enableSummary': True,
        'enableClearAll': True,
    }
    
    if columns_config:
        base_config['columnConfig'] = columns_config
    
    config_str = str(base_config).replace("'", '"').replace('True', 'true').replace('False', 'false')
    
    script = f"""
    <script>
        document.addEventListener('DOMContentLoaded', function() {{
            window.{table_id}Filter = createTableFilter({config_str});
        }});
    </script>
    """
    
    return mark_safe(script)


@register.simple_tag
def bulk_edit_scripts():
    """Load bulk edit CSS and JavaScript files"""
    return mark_safe("""
        <link rel="stylesheet" href="/static/table_filter/css/bulk_edit.css">
        <script src="/static/table_filter/js/bulk_edit.js"></script>
    """)


@register.simple_tag
def enable_bulk_edit():
    """Enable bulk edit functionality"""
    return mark_safe("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Initialize bulk edit manager
                if (typeof bulkEditManager !== 'undefined') {
                    bulkEditManager.init();
                    console.log('Bulk edit manager initialized');
                } else {
                    console.warn('Bulk edit manager not found');
                }
            });
        </script>
    """)


@register.simple_tag
def table_filter_with_bulk_edit():
    """Enable both table filter and bulk edit functionality"""
    return mark_safe("""
        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Initialize table filter
                console.log('Table filter enabled');
                
                // Initialize bulk edit
                if (typeof bulkEditManager !== 'undefined') {
                    bulkEditManager.init();
                    console.log('Bulk edit manager initialized');
                } else {
                    console.warn('Bulk edit manager not found');
                }
            });
        </script>
    """)


@register.simple_tag
def edit_history_scripts():
    """Load edit history CSS and JavaScript files"""
    return mark_safe("""
        <link rel="stylesheet" href="/static/table_filter/css/edit_history.css">
        <script src="/static/table_filter/js/edit_history.js"></script>
    """)


@register.simple_tag
def enable_edit_history(app_name='', model_name=''):
    """Enable edit history functionality"""
    config = {
        'app_name': app_name,
        'model_name': model_name
    }
    
    config_str = str(config).replace("'", '"')
    
    return mark_safe(f"""
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                // Initialize edit history manager
                if (typeof editHistoryManager !== 'undefined') {{
                    // تنظیم فیلترهای اولیه
                    editHistoryManager.filters.app_name = '{app_name}';
                    editHistoryManager.filters.model_name = '{model_name}';
                    
                    editHistoryManager.init();
                    console.log('Edit history manager initialized with config:', {config_str});
                }} else {{
                    console.warn('Edit history manager not found');
                }}
            }});
        </script>
    """)


@register.filter
def get_item(dictionary, key):
    """دریافت آیتم از دیکشنری با کلید"""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def object_fields(obj):
    """دریافت فیلدهای یک آبجکت به صورت قابل نمایش"""
    fields = []
    if obj is None:
        return fields
    
    # حذف فیلدهای خاص و متدها
    exclude = ['_state', 'id', 'pk', 'DoesNotExist', 'MultipleObjectsReturned']
    
    for field in obj._meta.fields:
        if field.name not in exclude:
            value = getattr(obj, field.name, '')
            
            # بررسی وجود متد get_FIELD_display برای فیلدهای choice
            if hasattr(obj, f'get_{field.name}_display'):
                display_value = getattr(obj, f'get_{field.name}_display')()
                if display_value:
                    value = display_value
            
            # تبدیل نوع‌های خاص
            if isinstance(value, bool):
                value = 'بله' if value else 'خیر'
            elif value is None:
                value = ''
                
            fields.append({
                'name': field.verbose_name or field.name,
                'value': value
            })
    
    return fields


@register.simple_tag
def highlight_changes(old_value, new_value):
    """هایلایت تفاوت‌های بین مقادیر قدیمی و جدید"""
    if old_value is None:
        old_value = ''
    if new_value is None:
        new_value = ''
    
    try:
        # تبدیل رشته‌های JSON به دیکشنری
        if isinstance(old_value, str) and old_value.startswith('{'):
            try:
                old_value = json.loads(old_value)
                old_value = json.dumps(old_value, indent=2, ensure_ascii=False)
            except:
                pass
            
        if isinstance(new_value, str) and new_value.startswith('{'):
            try:
                new_value = json.loads(new_value)
                new_value = json.dumps(new_value, indent=2, ensure_ascii=False)
            except:
                pass
        
        # تبدیل به رشته
        old_value = str(old_value)
        new_value = str(new_value)
        
        # هایلایت تفاوت‌ها (ساده)
        if old_value == new_value:
            return mark_safe(f'<code>{old_value}</code>')
        else:
            return mark_safe(
                f'<code class="text-danger">{old_value}</code> &rarr; <code class="text-success">{new_value}</code>'
            )
    except Exception as e:
        return mark_safe(f'<span class="text-danger">خطا در نمایش: {str(e)}</span>') 