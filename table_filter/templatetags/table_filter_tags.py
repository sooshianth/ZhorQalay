from django import template
from django.utils.safestring import mark_safe
from django.templatetags.static import static

register = template.Library()


@register.inclusion_tag('table_filter/table_filter_scripts.html')
def table_filter_scripts():
    """
    Load table filter CSS and JavaScript files
    """
    return {}


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
    """
    این تگ را در انتهای صفحه قرار دهید تا فیلترهای جدول فعال شوند.
    """
    script = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Initializing table filters...');
            setTimeout(function() {
                try {
                    // ابتدا هر دکمه فیلتر موجود را حذف می‌کنیم تا از تکرار جلوگیری شود
                    document.querySelectorAll('.filter-btn, .filter-dropdown-btn').forEach(function(btn) {
                        btn.remove();
                    });
                    
                    // تلاش برای حذف سورت‌های مثلثی موجود قبل از راه‌اندازی فیلترها
                    document.querySelectorAll('.enable-filter th').forEach(function(th) {
                        // حذف کلاس‌های سورت مثلثی
                        th.classList.remove('sorting', 'sorting_asc', 'sorting_desc');
                        // حذف آیکون سورت
                        th.style.backgroundImage = 'none';
                    });
                    
                    // ایجاد نمونه جدید از TableFilter
                    const tableFilter = new TableFilter({
                        tableSelector: '.enable-filter',
                        filterButtonClass: 'filter-btn'
                    });
                    
                    // ثبت در window برای دسترسی احتمالی
                    window.tableFilter = tableFilter;
                    
                    console.log('Table filters initialized successfully!');
                } catch (e) {
                    console.error('Error initializing table filters:', e);
                }
            }, 100);
        });
    </script>
    """
    return mark_safe(script)


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