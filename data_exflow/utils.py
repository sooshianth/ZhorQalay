import os
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, date
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import transaction, models, connections
from django.db.models import Q
from django.core.cache import cache
from django.conf import settings
from .models import ImportExportSession, ImportExportLog, ImportRecord
from django.core.exceptions import ValidationError, FieldDoesNotExist
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger("data_exflow_utils")

def test_database_connection():
    """Test that the database connection is working properly."""
    try:
        # Try to execute a simple query to check if the database is responsive
        connections['default'].cursor().execute('SELECT 1')
        return True
    except Exception as e:
        raise ConnectionError(f"Database connection error: {str(e)}")


def acquire_lock(session):
    """
    Acquire a lock for the session to prevent concurrent processing.
    Returns True if the lock was acquired, False otherwise.
    """
    lock_key = f"data_exflow_session_lock_{session.id}"
    
    # Try to acquire the lock using cache
    if cache.add(lock_key, True, timeout=3600):  # Lock expires after 1 hour
        return True
    
    return False


def release_lock(session):
    """Release the lock for the session."""
    lock_key = f"data_exflow_session_lock_{session.id}"
    cache.delete(lock_key)
    return True


def get_file_extension(filename):
    """Get the extension of a file."""
    return os.path.splitext(filename)[1].lower()


def is_valid_file_type(file_extension):
    """Check if the file type is supported."""
    supported_extensions = ['.xlsx', '.xls', '.csv']
    return file_extension in supported_extensions


def check_file_size(file):
    """Check if the file size is within acceptable limits."""
    # Set maximum file size to 10MB (adjust as needed)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
    
    if file.size > MAX_FILE_SIZE:
        raise ValueError(f"File size ({file.size} bytes) exceeds the maximum allowed size of {MAX_FILE_SIZE} bytes (10MB)")
    
    return True


def read_file_to_dataframe(file_path, file_extension):
    """Read a file into a pandas DataFrame."""
    if file_extension in ['.xlsx', '.xls']:
        return pd.read_excel(file_path)
    elif file_extension == '.csv':
        return pd.read_csv(file_path)
    raise ValueError(f"Unsupported file type: {file_extension}")


def get_all_registered_models():
    """Get all registered models in the project."""
    result = {}
    
    # رویکرد بهتر: استفاده از apps برای دریافت مستقیم تمام مدل‌ها
    from django.apps import apps
    
    # دریافت تمام مدل‌های ثبت شده در پروژه
    for app_config in apps.get_app_configs():
        app_label = app_config.label
        
        # حذف فیلتر برنامه‌های داخلی جنگو - اگر می‌خواهید آنها را هم ببینید، این شرط را بردارید
        if app_label in ['admin', 'auth', 'contenttypes', 'sessions', 'django_celery_beat']:
            continue
        
        if app_label not in result:
            result[app_label] = []
        
        for model in app_config.get_models():
            model_name = model.__name__
            
            # دریافت یا ایجاد ContentType برای این مدل
            try:
                from django.contrib.contenttypes.models import ContentType
                content_type = ContentType.objects.get_for_model(model)
                
                result[app_label].append({
                    'name': model_name,
                    'verbose_name': model._meta.verbose_name,
                    'content_type_id': content_type.id,
                })
            except Exception as e:
                logger.error(f"خطا در دریافت ContentType برای مدل {app_label}.{model_name}: {str(e)}")
                # حتی اگر نتوانیم ContentType را دریافت کنیم، مدل را اضافه می‌کنیم
                result[app_label].append({
                    'name': model_name,
                    'verbose_name': model._meta.verbose_name,
                    'content_type_id': None,  # ContentType موجود نیست
                })
    
    # مرتب‌سازی بر اساس نام برنامه
    return dict(sorted(result.items()))


def get_model_fields(app_label, model_name):
    """Get fields for a model."""
    try:
        # Get model class
        model = apps.get_model(app_label, model_name)
        
        fields = []
        # Get model fields
        for field in model._meta.fields:
            # Skip hidden fields
            if field.name.startswith('_'):
                continue
                
            # Get basic field info
            field_info = {
                'name': field.name,
                'verbose_name': field.verbose_name,
                'type': field.get_internal_type(),
                'required': not field.null and not field.blank and not field.primary_key and not field.has_default(),
                'primary_key': field.primary_key,
                'unique': field.unique,
                'has_choices': bool(field.choices),
                'choices': [],
                'has_default': field.has_default(),
                'default_value': None,
            }
            
            # Handle default values
            if field.has_default():
                try:
                    default_value = field.get_default()
                    # Handle callables (like functions, etc)
                    if callable(default_value):
                        try:
                            default_value = default_value()
                        except:
                            default_value = str(default_value)
                    # Convert the default value to string representation
                    field_info['default_value'] = str(default_value)
                except Exception as e:
                    field_info['default_value'] = f"(error getting default: {str(e)})"
            
            # Handle choices fields
            if field.choices:
                for key, display in field.choices:
                    # Check if the choice is a tuple of tuples (for grouped choices)
                    if isinstance(display, (list, tuple)):
                        for subkey, subdisplay in display:
                            field_info['choices'].append({
                                'key': str(subkey),
                                'display': str(subdisplay)
                            })
                    else:
                        field_info['choices'].append({
                            'key': str(key),
                            'display': str(display)
                        })
            
            # Handle ForeignKey fields
            if field.get_internal_type() == 'ForeignKey' and field.related_model:
                related_model_meta = field.related_model._meta
                field_info['related_model'] = {
                    'app_label': related_model_meta.app_label,
                    'model_name': related_model_meta.model_name,
                    'verbose_name': str(related_model_meta.verbose_name),
                }
                
                # If the related model has a __str__ method, get some sample values
                try:
                    sample_instances = field.related_model.objects.all()[:5]
                    field_info['related_model']['sample_values'] = []
                    for instance in sample_instances:
                        field_info['related_model']['sample_values'].append({
                            'id': instance.pk,
                            'display': str(instance)
                        })
                except Exception as e:
                    logger.warning(f"Error getting sample values for {field.name}: {e}")
                
                # If the related model has a choices attribute, add them
                if hasattr(field.related_model, 'CHOICES') or hasattr(field.related_model, 'choices'):
                    choices_attr = getattr(field.related_model, 'CHOICES', None) or getattr(field.related_model, 'choices', None)
                    if choices_attr:
                        field_info['choices'] = [{'key': str(key), 'display': str(display)} 
                                               for key, display in choices_attr]
            
            # Special handling for specific model types like CargoProduct
            if field.related_model and field.related_model.__name__ == 'CargoProduct':
                try:
                    # Check if model has PRODUCT_TYPES attribute
                    if hasattr(field.related_model, 'PRODUCT_TYPES'):
                        # Add product types
                        product_types = field.related_model.PRODUCT_TYPES
                        field_info['product_types'] = [{'key': str(key), 'display': str(display)} 
                                                   for key, display in product_types]
                    
                    # Check if model has COUNTRIES attribute
                    if hasattr(field.related_model, 'COUNTRIES'):
                        # Add countries
                        countries = field.related_model.COUNTRIES
                        field_info['countries'] = [{'key': str(key), 'display': str(display)} 
                                               for key, display in countries]
                except Exception as e:
                    logger.warning(f"Error getting CargoProduct info: {e}")
            
            fields.append(field_info)
        
        # Get many-to-many fields
        for field in model._meta.many_to_many:
            field_info = {
                'name': field.name,
                'verbose_name': field.verbose_name,
                'type': 'ManyToManyField',
                'required': False,  # M2M fields are never required
                'primary_key': False,
                'unique': False,
                'has_choices': False,
                'choices': [],
                'related_model': {
                    'app_label': field.related_model._meta.app_label,
                    'model_name': field.related_model._meta.model_name,
                    'verbose_name': str(field.related_model._meta.verbose_name),
                }
            }
            
            # If the related model has a __str__ method, get some sample values
            try:
                sample_instances = field.related_model.objects.all()[:5]
                field_info['related_model']['sample_values'] = []
                for instance in sample_instances:
                    field_info['related_model']['sample_values'].append({
                        'id': instance.pk,
                        'display': str(instance)
                    })
            except Exception as e:
                logger.warning(f"Error getting sample values for {field.name}: {e}")
            
            fields.append(field_info)
        
        return fields
    except Exception as e:
        logger.warning(f"Error in get_model_fields: {e}")
        return []


def get_model_unique_fields(model_class):
    """Get fields that are unique or part of unique_together in a model."""
    unique_fields = []
    
    # Add fields with unique=True
    for field in model_class._meta.fields:
        if getattr(field, 'unique', False):
            unique_fields.append(field.name)
    
    # Add fields from unique_together
    if hasattr(model_class._meta, 'unique_together'):
        for field_set in model_class._meta.unique_together:
            unique_fields.extend(field_set)
    
    return list(set(unique_fields))  # Remove duplicates


def suggest_identifier_fields(model_class):
    """Suggest fields that could be used as identifier for a model."""
    suggested_fields = []
    
    # Primary key is always a good identifier
    pk_field = model_class._meta.pk.name
    suggested_fields.append({
        'name': pk_field,
        'reason': 'Primary Key',
        'priority': 1,
    })
    
    # Unique fields are also good identifiers
    unique_fields = get_model_unique_fields(model_class)
    for field_name in unique_fields:
        if field_name != pk_field:  # Don't duplicate the primary key
            suggested_fields.append({
                'name': field_name,
                'reason': 'Unique Field',
                'priority': 2,
            })
    
    # Common naming patterns for identifiers
    common_identifier_patterns = [
        'number', 'code', 'id', 'identifier', 'serial', 'name', 'slug', 'uuid', 'email', 'username', 'phone'
    ]
    
    for field in model_class._meta.fields:
        field_name = field.name.lower()
        
        # Check if field name contains any common identifier patterns
        for pattern in common_identifier_patterns:
            if pattern in field_name and field.name not in [f['name'] for f in suggested_fields]:
                suggested_fields.append({
                    'name': field.name,
                    'reason': f'Common Identifier Pattern ({pattern})',
                    'priority': 3,
                })
                break
    
    # Sort by priority
    suggested_fields.sort(key=lambda x: x['priority'])
    
    return suggested_fields


def get_lookup_strategies(model_class, identifier_field, identifier_value):
    """
    Generate different lookup strategies based on the model and field type.
    This helps find records even when the identifier data might not be an exact match.
    """
    strategies = []
    
    # Get the field object
    try:
        field = model_class._meta.get_field(identifier_field)
    except FieldDoesNotExist:
        return strategies
    
    # حل مشکل pandas: اگر مقدار float هست و فیلد CharField هست، آن را به string تبدیل کن
    cleaned_identifier_value = identifier_value
    if isinstance(field, (models.CharField, models.TextField)) and isinstance(identifier_value, float):
        if identifier_value.is_integer():
            cleaned_identifier_value = str(int(identifier_value))
        else:
            cleaned_identifier_value = str(identifier_value)
    
    # Strategy 1: Exact match (always include this)
    strategies.append({
        'lookup': {identifier_field: cleaned_identifier_value},
        'description': 'Exact match'
    })
    
    # Strategy 2: Original value match (in case the original value is still needed)
    if cleaned_identifier_value != identifier_value:
        strategies.append({
            'lookup': {identifier_field: identifier_value},
            'description': 'Original value match'
        })
    
    # For string fields, add case-insensitive lookup
    if isinstance(field, (models.CharField, models.TextField)):
        strategies.append({
            'lookup': {f"{identifier_field}__iexact": cleaned_identifier_value},
            'description': 'Case-insensitive match'
        })
        
        # For numbers stored as strings, try to convert and match
        if isinstance(cleaned_identifier_value, str) and cleaned_identifier_value.strip().isdigit():
            cleaned_value = cleaned_identifier_value.strip()
            strategies.append({
                'lookup': {identifier_field: cleaned_value},
                'description': 'Cleaned numeric string'
            })
            
            # Try with leading zeros stripped
            if cleaned_value.startswith('0'):
                strategies.append({
                    'lookup': {identifier_field: cleaned_value.lstrip('0')},
                    'description': 'Without leading zeros'
                })
        
        # Try partial matching
        strategies.append({
            'lookup': {f"{identifier_field}__contains": cleaned_identifier_value},
            'description': 'Contains match'
        })
    
    # For numeric fields
    elif isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField)):
        # If a string is provided for a numeric field, try to convert it
        if isinstance(identifier_value, str):
            try:
                # Remove any non-numeric characters except decimal point
                cleaned_value = ''.join(c for c in identifier_value if c.isdigit() or c == '.')
                if isinstance(field, models.IntegerField):
                    numeric_value = int(float(cleaned_value))
                else:
                    numeric_value = float(cleaned_value)
                    
                strategies.append({
                    'lookup': {identifier_field: numeric_value},
                    'description': 'Converted string to number'
                })
            except (ValueError, TypeError):
                pass
    
    # For foreign key fields
    elif isinstance(field, models.ForeignKey):
        related_model = field.remote_field.model
        
        # Try to find by related model's primary key
        if isinstance(identifier_value, str) and identifier_value.isdigit():
            strategies.append({
                'lookup': {f"{identifier_field}_id": int(identifier_value)},
                'description': 'Foreign key by ID'
            })
        
        # If related model has a name field, try matching by name
        if hasattr(related_model, 'name'):
            strategies.append({
                'lookup': {f"{identifier_field}__name": identifier_value},
                'description': 'Foreign key by name'
            })
            strategies.append({
                'lookup': {f"{identifier_field}__name__icontains": identifier_value},
                'description': 'Foreign key by name contains'
            })
    
    return strategies


def find_existing_instance(model_class, identifier_field, identifier_value):
    """
    Try multiple strategies to find an existing instance.
    Returns the instance and the strategy that found it.
    """
    strategies = get_lookup_strategies(model_class, identifier_field, identifier_value)
    
    for strategy in strategies:
        try:
            instance = model_class.objects.get(**strategy['lookup'])
            return instance, strategy['description']
        except (model_class.DoesNotExist, ValueError, TypeError):
            continue
        except model_class.MultipleObjectsReturned:
            # If multiple records are found, try to get the most recent one
            if hasattr(model_class, 'created_at'):
                try:
                    instance = model_class.objects.filter(**strategy['lookup']).order_by('-created_at').first()
                    if instance:
                        return instance, f"{strategy['description']} (most recent)"
                except Exception:
                    pass
            # If created_at doesn't exist or query failed, just get the first one
            try:
                instance = model_class.objects.filter(**strategy['lookup']).first()
                if instance:
                    return instance, f"{strategy['description']} (first match)"
            except Exception:
                pass
    
    return None, "No match found"


def find_related_object(related_model, value):
    """
    Find a related object based on value.
    This is used to find ForeignKey related objects during import.
    """
    # Try first by primary key if the value looks like a number
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        try:
            return related_model.objects.get(pk=int(value))
        except (related_model.DoesNotExist, ValueError):
            pass
    
    # Try by name field if it exists
    if hasattr(related_model, 'name'):
        try:
            return related_model.objects.get(name=value)
        except (related_model.DoesNotExist, related_model.MultipleObjectsReturned):
            # Try a case-insensitive search
            try:
                return related_model.objects.get(name__iexact=value)
            except (related_model.DoesNotExist, related_model.MultipleObjectsReturned):
                pass
    
    # Try by title field if it exists
    if hasattr(related_model, 'title'):
        try:
            return related_model.objects.get(title=value)
        except (related_model.DoesNotExist, related_model.MultipleObjectsReturned):
            # Try a case-insensitive search
            try:
                return related_model.objects.get(title__iexact=value)
            except (related_model.DoesNotExist, related_model.MultipleObjectsReturned):
                pass
    
    # Try by code or number fields if they exist
    for field_name in ['code', 'number', 'identifier']:
        if hasattr(related_model, field_name):
            try:
                return related_model.objects.get(**{field_name: value})
            except (related_model.DoesNotExist, related_model.MultipleObjectsReturned):
                pass
    
    # If all else fails, try a contains search on common fields
    for field_name in ['name', 'title', 'description']:
        if hasattr(related_model, field_name):
            try:
                return related_model.objects.filter(**{f"{field_name}__icontains": value}).first()
            except Exception:
                pass
    
    return None


def validate_import_data(session, dataframe, mapping):
    """Validate that the data can be imported."""
    model_class = session.get_model_class()
    errors = []
    warnings = []
    unique_identifier_field = None
    
    # Find the field used as unique identifier (for updates)
    for field_name, field_mapping in mapping.items():
        if field_mapping.get('is_identifier', False):
            unique_identifier_field = field_name
            model_field_name = field_mapping['model_field']
            break
    
    # اگر فیلد شناسه‌گر تعیین نشده باشد، خطا برگردان
    if not unique_identifier_field:
        return {
            'valid': False,
            'errors': [{
                'row': 0,
                'field': '',
                'errors': [{
                    'message': 'فیلد شناسه‌گر برای تشخیص رکوردهای تکراری انتخاب نشده است.'
                }]
            }]
        }
    
    # بررسی اعتبار فیلد شناسه‌گر
    try:
        field_obj = model_class._meta.get_field(model_field_name)
        
        # نمایش هشدار اگر فیلد شناسه‌گر یونیک نیست
        is_unique = getattr(field_obj, 'unique', False) or getattr(field_obj, 'primary_key', False)
        if not is_unique:
            # بررسی unique_together
            in_unique_together = False
            if hasattr(model_class._meta, 'unique_together'):
                for field_set in model_class._meta.unique_together:
                    if model_field_name in field_set:
                        in_unique_together = True
                        break
            
            if not in_unique_together:
                warnings.append({
                    'row': 0,
                    'message': f'فیلد انتخاب شده ({model_field_name}) به عنوان شناسه‌گر، در مدل یونیک نیست. این ممکن است باعث شناسایی اشتباه رکوردهای تکراری شود.'
                })
                
    except Exception as e:
        return {
            'valid': False, 
            'errors': [{
                'row': 0,
                'field': model_field_name,
                'errors': [{
                    'message': f'خطا در بررسی فیلد شناسه‌گر: {str(e)}'
                }]
            }]
        }
        
    # If we have a unique identifier field, check for existing records
    existing_records = {}
    duplicate_values = {}
    
    if unique_identifier_field:
        # Get all values of the identifier field
        identifier_values = dataframe[unique_identifier_field].dropna().tolist()
        if identifier_values:
            # بررسی مقادیر تکراری در فایل ورودی
            value_counts = {}
            for i, value in enumerate(identifier_values):
                if pd.notna(value):
                    str_value = str(value).strip()
                    if str_value in value_counts:
                        value_counts[str_value].append(i+2)  # +2 برای شروع از ردیف 2 (با در نظر گرفتن هدر)
                    else:
                        value_counts[str_value] = [i+2]
            
            # ثبت مقادیر تکراری در فایل ورودی
            for value, rows in value_counts.items():
                if len(rows) > 1:
                    duplicate_values[value] = rows
                    warnings.append({
                        'row': rows[0],
                        'message': f'مقدار "{value}" برای فیلد شناسه‌گر در ردیف‌های {", ".join(map(str, rows))} تکراری است.'
                    })
            
            # For each unique identifier value, try to find an existing record
            model_field = mapping[unique_identifier_field]['model_field']
            unique_values = set(identifier_values)
            
            for value in unique_values:
                if pd.notna(value):
                    instance, strategy = find_existing_instance(model_class, model_field, value)
                    if instance:
                        existing_records[str(value)] = {
                            'instance': instance,
                            'strategy': strategy
                        }
    
    # Count for creates and updates
    creates = 0
    updates = 0
    
    # جمع‌آوری اطلاعات فیلدهای choices
    fields_with_choices = {}
    for field_name, field_mapping in mapping.items():
        if not field_mapping.get('model_field'):
            continue
            
        model_field_name = field_mapping['model_field']
        try:
            field_obj = model_class._meta.get_field(model_field_name)
            if hasattr(field_obj, 'choices') and field_obj.choices:
                fields_with_choices[field_name] = {
                    'model_field': model_field_name,
                    'choices': field_obj.choices,
                    'valid_values': [str(key) for key, _ in field_obj.choices] + [str(display) for _, display in field_obj.choices]
                }
        except Exception:
            pass
    
    # Validate each row
    for index, row in dataframe.iterrows():
        row_number = index + 2  # +2 because pandas is 0-indexed and we have a header row
        row_errors = []
        
        # Check for existing record
        is_update = False
        if unique_identifier_field:
            identifier_value = row.get(unique_identifier_field)
            if pd.notna(identifier_value):
                if str(identifier_value) in existing_records:
                    is_update = True
                    match_info = existing_records[str(identifier_value)]
                    warnings.append({
                        'row': row_number,
                        'field': unique_identifier_field,
                        'message': f"رکورد موجود با استفاده از {match_info['strategy']} یافت شد"
                    })
        
        # Count updates and creates
        if is_update:
            updates += 1
        else:
            creates += 1
        
        # بررسی فیلدهای choices
        for field_name, choice_info in fields_with_choices.items():
            value = row.get(field_name)
            if pd.notna(value):
                str_value = str(value).strip()
                # تست تطبیق اولیه - با استفاده از روش‌های مختلف تطبیق در تابع match_choice_value
                matched_value = match_choice_value(str_value, choice_info['choices'])
                
                # اگر مقدار برگشتی همان مقدار اولیه باشد، یعنی تطبیقی پیدا نشده
                if str(matched_value) == str_value and str_value not in choice_info['valid_values']:
                    choices_text = ', '.join([f"{key} ({display})" for key, display in choice_info['choices']])
                    row_errors.append({
                        'field': field_name,
                        'message': f'مقدار "{str_value}" برای فیلد {choice_info["model_field"]} مجاز نیست. مقادیر مجاز: {choices_text}'
                    })
                elif str(matched_value) != str_value:
                    # تطبیق انجام شده اما دقیقاً یکسان نیست
                    matched_display = next((display for key, display in choice_info['choices'] if str(key) == str(matched_value)), matched_value)
                    warnings.append({
                        'row': row_number,
                        'field': field_name,
                        'message': f'مقدار "{str_value}" به "{matched_value}" ({matched_display}) تبدیل شد'
                    })
        
        # Check required fields
        for field_name, field_mapping in mapping.items():
            model_field = field_mapping['model_field']
            if model_field:
                try:
                    field_obj = model_class._meta.get_field(model_field)
                    
                    # Check if field is required
                    if not field_obj.blank and not field_obj.null and not field_obj.primary_key:
                        value = row.get(field_name)
                        if pd.isna(value) or value == '':
                            row_errors.append({
                                'field': field_name,
                                'message': f'فیلد {model_field} الزامی است'
                            })
                except Exception as e:
                    row_errors.append({
                        'field': field_name,
                        'message': f'خطا در بررسی فیلد {model_field}: {str(e)}'
                    })
        
        # If there are errors in this row, add to errors list
        if row_errors:
            errors.append({
                'row': row_number,
                'errors': row_errors
            })
    
    # Additional checks for unique constraint violations
    unique_fields = {}
    
    # Get all unique fields in the model
    for field in model_class._meta.fields:
        if getattr(field, 'unique', False) and not getattr(field, 'primary_key', False):
            unique_fields[field.name] = []
    
    # If we have unique fields, check for potential conflicts
    if unique_fields:
        for field_name, mapped_values in unique_fields.items():
            # Find the file column mapped to this model field
            mapped_column = None
            for col, mapping_info in mapping.items():
                if mapping_info.get('model_field') == field_name:
                    mapped_column = col
                    break
            
            if mapped_column:
                # Get all values for this field from the database
                existing_values = set(model_class.objects.values_list(field_name, flat=True))
                
                # Check each row for potential conflicts
                for index, row in dataframe.iterrows():
                    row_number = index + 2
                    value = row.get(mapped_column)
                    
                    if pd.notna(value) and value != '':
                        # بررسی فیلدهای یونیک از نوع عددی
                        if isinstance(value, (int, float)):
                            if value in existing_values:
                                # بررسی کنیم که آیا این مقدار با فیلد شناسه‌گر مطابقت دارد
                                identifier_value = row.get(unique_identifier_field)
                                # اگر رکورد با این مقدار شناسه‌گر وجود نداشته باشد، یک خطا اضافه کنیم
                                if not pd.notna(identifier_value) or str(identifier_value) not in existing_records:
                                    errors.append({
                                        'row': row_number,
                                        'errors': [{
                                            'field': mapped_column,
                                            'message': f'مقدار {value} برای فیلد {field_name} در پایگاه داده وجود دارد و یک خطای یونیک رخ خواهد داد.'
                                        }]
                                    })
                        # بررسی فیلدهای یونیک از نوع رشته
                        elif isinstance(value, str) and value.strip() in existing_values:
                            # بررسی کنیم که آیا این مقدار با فیلد شناسه‌گر مطابقت دارد
                            identifier_value = row.get(unique_identifier_field)
                            # اگر رکورد با این مقدار شناسه‌گر وجود نداشته باشد، یک خطا اضافه کنیم
                            if not pd.notna(identifier_value) or str(identifier_value) not in existing_records:
                                errors.append({
                                    'row': row_number,
                                    'errors': [{
                                        'field': mapped_column,
                                        'message': f'مقدار "{value}" برای فیلد {field_name} در پایگاه داده وجود دارد و یک خطای یونیک رخ خواهد داد.'
                                    }]
                                })
    
    # Check for duplicates in the imported data for unique fields
    for field_name in unique_fields.keys():
        # Find the file column mapped to this model field
        mapped_column = None
        for col, mapping_info in mapping.items():
            if mapping_info.get('model_field') == field_name:
                mapped_column = col
                break
        
        if mapped_column and mapped_column in dataframe.columns:
            # Count occurrences of each value
            value_counts = dataframe[mapped_column].value_counts()
            
            # Check for duplicates
            for value, count in value_counts.items():
                if count > 1 and pd.notna(value) and value != '':
                    # Find rows with this value
                    rows = dataframe.index[dataframe[mapped_column] == value].tolist()
                    rows = [r+2 for r in rows]  # +2 for header and 0-indexing
                    
                    # Add error for each row with this value
                    for row in rows:
                        errors.append({
                            'row': row,
                            'errors': [{
                                'field': mapped_column,
                                'message': f'مقدار "{value}" برای فیلد {field_name} در ردیف‌های {", ".join(map(str, rows))} تکراری است و نقض محدودیت یکتایی خواهد شد.'
                            }]
                        })
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'creates': creates,
        'updates': updates,
        'existing_records': len(existing_records),
        'duplicate_values': duplicate_values,
        'fields_with_choices': {k: {'model_field': v['model_field'], 'choices': [(str(key), str(display)) for key, display in v['choices']]} 
                               for k, v in fields_with_choices.items()}
    }


def process_import(session):
    """Process the import data and save to database."""
    if not acquire_lock(session):
        raise Exception("این جلسه ایمپورت در حال پردازش توسط کاربر دیگری است")
    
    try:
        # Get the model and mapping
        model_class = session.get_model_class()
        mapping = session.mapping
        
        # Read the file
        file_path = session.file.path
        file_extension = get_file_extension(session.file_name)
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Find the identifier field
        unique_identifier_field = None
        for field_name, field_mapping in mapping.items():
            if field_mapping.get('is_identifier', False):
                unique_identifier_field = field_name
                model_field = field_mapping['model_field']
                break
        
        if not unique_identifier_field:
            raise ValidationError("فیلد شناسه برای تشخیص رکوردهای موجود انتخاب نشده است")
        
        # Update session status
        session.status = 'processing'
        session.row_count = len(df)
        session.processed_count = 0
        session.save()
        
        # Process rows
        create_count = 0
        update_count = 0
        error_count = 0
        skipped_count = 0
        
        # تهیه لیست فیلدهای یونیک مدل
        unique_fields = []
        for field in model_class._meta.fields:
            if getattr(field, 'unique', False) and not getattr(field, 'primary_key', False):
                unique_fields.append(field.name)
        
        # لیست برای نگهداری تمام خطاها
        all_errors = []
        
        for index, row in df.iterrows():
            row_number = index + 2  # +2 because pandas is 0-indexed and we have a header row
            instance = None
            previous_state = None
            field_values = {}
            
            try:
                # Get the unique identifier value
                identifier_value = row.get(unique_identifier_field)
                
                # Skip rows without an identifier
                if pd.isna(identifier_value):
                    ImportExportLog.objects.create(
                        session=session,
                        log_level='warning',
                        message=f"ردیف {row_number} بدون مقدار شناسه رد شد",
                        row_number=row_number
                    )
                    skipped_count += 1
                    continue
                
                # هر ردیف در یک atomic block جداگانه پردازش می‌شود
                with transaction.atomic():
                    # Try to find an existing instance
                    instance, strategy = find_existing_instance(model_class, model_field, identifier_value)
                    
                    # Prepare field values
                    field_values = {}
                    for field_name, field_mapping in mapping.items():
                        if not field_mapping.get('model_field'):
                            continue  # Skip unmapped fields
                        
                        model_field_name = field_mapping['model_field']
                        value = row.get(field_name)
                        
                        # Skip null values for updates if field is not nullable
                        if instance and pd.isna(value):
                            field_obj = model_class._meta.get_field(model_field_name)
                            if not field_obj.null and not field_obj.blank:
                                continue
                        
                        # Skip empty foreign keys
                        if pd.isna(value) or value == '':
                            field_obj = model_class._meta.get_field(model_field_name)
                            if field_obj.is_relation:
                                continue
                        
                        # Process the value if it's not null
                        if pd.notna(value):
                            # Get the field object
                            field_obj = model_class._meta.get_field(model_field_name)
                            
                            # Handle foreign key relations
                            if field_obj.is_relation:
                                if hasattr(field_obj, 'remote_field') and field_obj.remote_field:
                                    related_model = field_obj.remote_field.model
                                    related_obj = find_related_object(related_model, value)
                                    
                                    if related_obj:
                                        field_values[model_field_name] = related_obj
                                    else:
                                        # Log error and skip this field
                                        error_msg = f"ردیف {row_number}: مقدار {value} برای فیلد {model_field_name} پیدا نشد"
                                        ImportExportLog.objects.create(
                                            session=session,
                                            log_level='error',
                                            message=error_msg,
                                            row_number=row_number
                                        )
                                        logger.warning(error_msg)
                                        all_errors.append(error_msg)
                                        continue
                            # Handle normal fields
                            else:
                                # Sanitize and convert the value
                                sanitized_value = sanitize_value(value, field_obj)
                                field_values[model_field_name] = sanitized_value
                    
                    # Handle create or update
                    if instance:
                        # Store the previous state for reversion
                        previous_state = {}
                        for field_name in field_values.keys():
                            if hasattr(instance, field_name):
                                previous_state[field_name] = getattr(instance, field_name)
                        
                        # بررسی تداخل با سایر رکوردها در فیلدهای یونیک
                        for field_name in unique_fields:
                            if field_name in field_values:
                                value = field_values[field_name]
                                # بررسی وجود رکورد دیگر با همین مقدار
                                try:
                                    existing = model_class.objects.exclude(pk=instance.pk).get(**{field_name: value})
                                    if existing:
                                        # خطا برای فیلد یونیک
                                        raise ValidationError(f"مقدار {value} برای فیلد {field_name} قبلاً در دیتابیس ثبت شده و منحصر به فرد باید باشد")
                                except model_class.DoesNotExist:
                                    # مشکلی وجود ندارد
                                    pass
                        
                        # Update the instance
                        for field_name, value in field_values.items():
                            setattr(instance, field_name, value)
                        
                        # Try to save the instance with validation
                        instance.full_clean()
                        instance.save()
                        
                        # Log update
                        ImportExportLog.objects.create(
                            session=session,
                            log_level='success',
                            message=f"ردیف {row_number}: رکورد با شناسه {identifier_value} بروزرسانی شد",
                            row_number=row_number
                        )
                        
                        update_count += 1
                            
                    else:  # Create new instance
                        # بررسی تداخل با سایر رکوردها در فیلدهای یونیک
                        for field_name in unique_fields:
                            if field_name in field_values:
                                value = field_values[field_name]
                                # بررسی وجود رکورد با همین مقدار
                                try:
                                    existing = model_class.objects.get(**{field_name: value})
                                    if existing:
                                        # خطا برای فیلد یونیک
                                        raise ValidationError(f"مقدار {value} برای فیلد {field_name} قبلاً در دیتابیس ثبت شده و منحصر به فرد باید باشد")
                                except model_class.DoesNotExist:
                                    # مشکلی وجود ندارد
                                    pass
                        
                        # Create a new instance
                        instance = model_class(**field_values)
                        
                        # Validate and save the instance
                        instance.full_clean()
                        instance.save()
                        
                        # Log creation
                        ImportExportLog.objects.create(
                            session=session,
                            log_level='success',
                            message=f"ردیف {row_number}: رکورد جدید با شناسه {instance.pk} ایجاد شد",
                            row_number=row_number
                        )
                        
                        create_count += 1
                    
                    # Update processed count
                    session.processed_count += 1
                    
            except Exception as e:
                # Check for unique constraint violation
                error_msg = str(e)
                if 'UNIQUE constraint failed' in error_msg or 'unique constraint' in error_msg.lower() or 'duplicate key' in error_msg.lower():
                    field_name = error_msg.split(':')[-1].strip() if ':' in error_msg else 'unknown field'
                    error_message = f"ردیف {row_number}: خطای تکراری بودن داده در فیلد {field_name}. مقدار باید منحصر به فرد باشد."
                else:
                    error_message = f"ردیف {row_number}: خطا در پردازش - {str(e)}"
                
                # Log error
                ImportExportLog.objects.create(
                    session=session,
                    log_level='error',
                    message=error_message,
                    row_number=row_number
                )
                logger.warning(error_message)
                all_errors.append(error_message)
                error_count += 1
                
                # به جای raise کردن، فقط ادامه می‌دهیم
                continue
                
            # ایجاد ImportRecord خارج از atomic block
            try:
                if instance:
                    if previous_state:
                        # Update case
                        ImportRecord.objects.create(
                            session=session,
                            content_type=session.content_type,
                            object_id=instance.pk,
                            row_number=row_number,
                            action='update',
                            previous_state=previous_state,
                            current_state=field_values
                        )
                    else:
                        # Create case
                        ImportRecord.objects.create(
                            session=session,
                            content_type=session.content_type,
                            object_id=instance.pk,
                            row_number=row_number,
                            action='create',
                            previous_state=None,
                            current_state=field_values
                        )
            except Exception as import_record_error:
                # اگر ایجاد ImportRecord خطا داشت، فقط لاگ کن و ادامه بده
                logger.warning(f"ردیف {row_number}: خطا در ایجاد ImportRecord: {str(import_record_error)}")
                ImportExportLog.objects.create(
                    session=session,
                    log_level='warning',
                    message=f"ردیف {row_number}: خطا در ایجاد رکورد بازگشت: {str(import_record_error)}",
                    row_number=row_number
                )
    
        # Update session status
        session.status = 'completed'
        session.processed_count = create_count + update_count
        session.error_count = error_count
        session.save()
        
        # Log success with summary
        summary_message = f"ایمپورت با موفقیت انجام شد. {create_count} رکورد ایجاد شده، {update_count} رکورد بروزرسانی شده، {error_count} خطا، {skipped_count} رد شده."
        ImportExportLog.objects.create(
            session=session,
            log_level='info',
            message=summary_message
        )
        
        # اگر خطایی وجود داشت، خلاصه تمام خطاها را هم لاگ کن
        if all_errors:
            errors_summary = "خلاصه خطاهای رخ داده:\n" + "\n".join(all_errors[:50])  # فقط 50 خطای اول
            if len(all_errors) > 50:
                errors_summary += f"\n... و {len(all_errors) - 50} خطای دیگر"
            
            ImportExportLog.objects.create(
                session=session,
                log_level='warning',
                message=errors_summary
            )
        
        return {
            'success': True,
            'creates': create_count,
            'updates': update_count,
            'errors': error_count,
            'skipped': skipped_count,
            'error_details': all_errors
        }
        
    except Exception as e:
        # Update session status
        session.status = 'failed'
        session.error_count += 1 if 'error_count' in locals() else 1
        session.save()
        
        # Log failure
        ImportExportLog.objects.create(
            session=session,
            log_level='error',
            message=f"ایمپورت با خطا مواجه شد: {str(e)}"
        )

        
        import traceback
        error_trace = traceback.format_exc()
        ImportExportLog.objects.create(
            session=session,
            log_level='error',
            message=f"جزئیات خطا: {error_trace[:500]}..."
        )
        logger.warning(f"ایمپورت با خطا مواجه شد: {str(e)}, جزئیات خطا: {error_trace[:500]}...")
        
        return {
            'success': False,
            'error': str(e)
        }
        
    finally:
        # Release the lock
        release_lock(session)


def revert_import(session):
    """Revert an import operation."""
    if not session.can_be_reverted:
        raise ValueError("This session cannot be reverted.")
    
    # Try to acquire a lock
    if not acquire_lock(session):
        raise ValueError("This session is already being processed by another request. Please try again later.")
    
    # Collect logs outside of transaction
    revert_logs = []
    
    try:
        # Get all import records for this session
        import_records = ImportRecord.objects.filter(session=session).order_by('-id')
        
        for record in import_records:
            model_class = record.content_type.model_class()
            
            try:
                with transaction.atomic():
                    instance = model_class.objects.get(pk=record.object_id)
                    
                    if record.action == 'create':
                        # Delete created records
                        instance.delete()
                        revert_logs.append({
                            'level': ImportExportLog.INFO,
                            'message': f"Deleted record with ID {record.object_id}",
                            'row_number': record.row_number
                        })
                    elif record.action == 'update':
                        # Restore previous state
                        for field, value in record.previous_state.items():
                            setattr(instance, field, value)
                        instance.save()
                        revert_logs.append({
                            'level': ImportExportLog.INFO,
                            'message': f"Reverted record with ID {record.object_id} to previous state",
                            'row_number': record.row_number
                        })
            except model_class.DoesNotExist:
                revert_logs.append({
                    'level': ImportExportLog.WARNING,
                    'message': f"Record with ID {record.object_id} not found during reversion",
                    'row_number': record.row_number
                })
            except Exception as e:
                revert_logs.append({
                    'level': ImportExportLog.ERROR,
                    'message': f"Error reverting record with ID {record.object_id}: {str(e)}",
                    'row_number': record.row_number
                })
                logger.warning(f"Error reverting record with ID {record.object_id}: {str(e)}")
        
        # Update session status
        session.status = ImportExportSession.REVERTED
        session.save()
        
        # Log all collected messages
        for log_info in revert_logs:
            ImportExportLog.objects.create(
                session=session,
                log_level=log_info['level'],
                message=log_info['message'],
                row_number=log_info.get('row_number')
            )
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.INFO,
            message=f"Import session reverted. All changes have been rolled back."
        )
    except Exception as e:
        # Handle any unexpected errors
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"Revert failed with error: {str(e)}"
        )
        logger.warning(f"Revert failed with error: {str(e)}")
        raise
    finally:
        # Always release the lock
        release_lock(session)


def process_export(content_types, field_mapping, user, format='xlsx'):
    """Process the export operation."""
    # Check database connection first
    test_database_connection()
    
    # Create a new export session
    session = ImportExportSession.objects.create(
        session_type=ImportExportSession.EXPORT,
        user=user,
        content_type=content_types[0],  # Use the first content type for reference
        file_name=f"export_{content_types[0].model}.{format}",
        file_type=format,
        status=ImportExportSession.PROCESSING,
        mapping=field_mapping
    )
    
    # Try to acquire a lock
    if not acquire_lock(session):
        raise ValueError("This session is already being processed by another request. Please try again later.")
    
    try:
        # Prepare the dataframes for each model
        dataframes = []
        
        for content_type in content_types:
            model_class = content_type.model_class()
            queryset = model_class.objects.all()
            
            # Extract field mapping for this model
            model_fields = field_mapping.get(f"{content_type.app_label}.{content_type.model}", {})
            
            if not model_fields:
                continue
                
            # Extract data
            data = []
            for instance in queryset:
                row = {}
                for field_name, export_name in model_fields.items():
                    try:
                        value = getattr(instance, field_name)
                        
                        # Convert DateTime and timezone fields to string for Excel compatibility
                        if value is not None:
                            # Get the field object to check its type
                            try:
                                field_obj = model_class._meta.get_field(field_name)
                                
                                # Check if it's a DateTime field
                                if isinstance(field_obj, (models.DateTimeField, models.DateField, models.TimeField)):
                                    # Convert to string in a readable format
                                    if isinstance(field_obj, models.DateTimeField):
                                        # Format: YYYY-MM-DD HH:MM:SS
                                        value = value.strftime('%Y-%m-%d %H:%M:%S') if value else None
                                    elif isinstance(field_obj, models.DateField):
                                        # Format: YYYY-MM-DD
                                        value = value.strftime('%Y-%m-%d') if value else None
                                    elif isinstance(field_obj, models.TimeField):
                                        # Format: HH:MM:SS
                                        value = value.strftime('%H:%M:%S') if value else None
                                
                                # Handle timezone-aware datetime fields
                                elif hasattr(value, 'tzinfo') and value.tzinfo is not None:
                                    # Convert timezone-aware datetime to string
                                    value = value.strftime('%Y-%m-%d %H:%M:%S %Z') if value else None
                                    
                            except FieldDoesNotExist:
                                # If field doesn't exist in model, check if value is datetime-like
                                if hasattr(value, 'strftime'):
                                    if hasattr(value, 'hour'):  # DateTime or Time
                                        if hasattr(value, 'date'):  # DateTime
                                            value = value.strftime('%Y-%m-%d %H:%M:%S')
                                        else:  # Time only
                                            value = value.strftime('%H:%M:%S')
                                    else:  # Date only
                                        value = value.strftime('%Y-%m-%d')
                        
                        row[export_name] = value
                    except AttributeError:
                        row[export_name] = None
                data.append(row)
            
            # Create dataframe
            if data:
                df = pd.DataFrame(data)
                dataframes.append(df)
        
        # Combine all dataframes if multiple models
        if len(dataframes) > 1:
            final_df = pd.concat(dataframes, ignore_index=True)
        elif len(dataframes) == 1:
            final_df = dataframes[0]
        else:
            final_df = pd.DataFrame()
        
        # Create the export file using Django settings
        try:
            export_dir = os.path.join(settings.MEDIA_ROOT, 'data_exflow', 'files')
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, f"export_{session.id}.{format}")
            
            # Save based on format
            if format.lower() == 'xlsx':
                final_df.to_excel(file_path, index=False)
            elif format.lower() == 'csv':
                final_df.to_csv(file_path, index=False)
            else:
                # Default to Excel
                final_df.to_excel(file_path, index=False)
                
        except PermissionError as e:
            error_msg = f"Permission denied creating export file. Please check IIS AppPool permissions for MEDIA_ROOT: {settings.MEDIA_ROOT}"
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.ERROR,
                message=error_msg
            )
            raise PermissionError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error creating export file in {export_dir}: {str(e)}"
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.ERROR,
                message=error_msg
            )
            raise OSError(error_msg) from e
        
        # Update the session with the file
        try:
            with open(file_path, 'rb') as f:
                session.file.save(f"export_{session.id}.{format}", f)
        except PermissionError as e:
            error_msg = f"Permission denied saving export file to Django FileField. Please check IIS AppPool permissions for MEDIA_ROOT: {settings.MEDIA_ROOT}"
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.ERROR,
                message=error_msg
            )
            raise PermissionError(error_msg) from e
        except OSError as e:
            error_msg = f"OS error saving export file to Django FileField: {str(e)}"
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.ERROR,
                message=error_msg
            )
            raise OSError(error_msg) from e
        finally:
            # Clean up temporary file if it exists
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass  # Ignore cleanup errors
        
        session.record_count = len(final_df)
        session.processed_count = len(final_df)
        session.status = ImportExportSession.COMPLETED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.INFO,
            message=f"Export completed. {session.processed_count} records exported. DateTime and timezone fields converted to string format for Excel compatibility."
        )
        
        return session
    except Exception as e:
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"Export failed: {str(e)}"
        )

        logger.warning(f"Export failed: {str(e)}")
        
        # Re-raise the exception with additional context
        raise ValueError(f"Export operation failed: {str(e)}")
    finally:
        # Always release the lock
        release_lock(session)


def sanitize_value(value, field_obj):
    """Sanitize input values to prevent injection attacks."""
    if value is None:
        return None
        
    # Convert to string for sanitization if needed
    if not isinstance(value, str) and not isinstance(value, (int, float, bool, dict, list)):
        value = str(value)
    
    # Handle different field types differently
    if isinstance(field_obj, models.CharField) or isinstance(field_obj, models.TextField):
        # For text fields, ensure we don't exceed max_length
        if isinstance(value, str) and hasattr(field_obj, 'max_length') and field_obj.max_length:
            value = value[:field_obj.max_length]
        
        # حل مشکل pandas: اگر مقدار float هست و فیلد CharField هست، آن را به string تبدیل کن
        if isinstance(value, float):
            # اگر مقدار float هست و قسمت اعشاری صفر است، آن را به int و سپس string تبدیل کن
            if value.is_integer():
                value = str(int(value))
            else:
                value = str(value)
            
        # Handle choices fields
        if hasattr(field_obj, 'choices') and field_obj.choices:
            value = match_choice_value(value, field_obj.choices)
    
    elif isinstance(field_obj, models.IntegerField):
        # For integer fields, ensure we have a valid integer
        try:
            if isinstance(value, str):
                value = int(value)
        except (ValueError, TypeError):
            # If conversion fails, return None
            return None
    
    elif isinstance(field_obj, models.FloatField) or isinstance(field_obj, models.DecimalField):
        # For float/decimal fields, ensure we have a valid number
        try:
            if isinstance(value, str):
                value = float(value)
        except (ValueError, TypeError):
            return None
    
    elif isinstance(field_obj, models.BooleanField):
        # For boolean fields, convert common string representations
        if isinstance(value, str):
            value = value.lower()
            if value in ('true', 'yes', '1', 'y'):
                value = True
            elif value in ('false', 'no', '0', 'n'):
                value = False
            else:
                # Invalid boolean representation
                return None
    
    # Handle jDateField (Jalali Date Field) - اضافه شده برای پشتیبانی از تاریخ‌های جلالی
    elif hasattr(field_obj, '__class__') and 'jDateField' in str(field_obj.__class__):
        if isinstance(value, str):
            # پشتیبانی از فرمت‌های مختلف تاریخ جلالی
            value = parse_jalali_date(value)
    
    # Handle regular DateField
    elif isinstance(field_obj, models.DateField):
        if isinstance(value, str):
            value = parse_date_string(value)
    
    # Handle DateTimeField
    elif isinstance(field_obj, models.DateTimeField):
        if isinstance(value, str):
            value = parse_datetime_string(value)
    
    return value 


def match_choice_value(value, choices):
    """
    تطبیق مقدار ورودی با مقادیر مجاز در choices
    این تابع سعی می‌کند با استفاده از روش‌های مختلف، مقدار ورودی را با یکی از مقادیر مجاز تطبیق دهد
    """
    if value is None or value == '':
        return value
        
    # تبدیل به رشته برای مقایسه
    str_value = str(value).strip()
    
    # اگر مقدار دقیقاً با یکی از کلیدها مطابقت داشت
    for choice_key, choice_display in choices:
        if str(choice_key) == str_value:
            return choice_key
    
    # اگر مقدار با متن نمایشی مطابقت داشت
    for choice_key, choice_display in choices:
        if str(choice_display) == str_value:
            return choice_key
    
    # تطبیق با حساسیت کمتر به حروف بزرگ/کوچک برای کلیدها
    for choice_key, choice_display in choices:
        if str(choice_key).lower() == str_value.lower():
            return choice_key
    
    # تطبیق با حساسیت کمتر به حروف بزرگ/کوچک برای متن نمایشی
    for choice_key, choice_display in choices:
        if str(choice_display).lower() == str_value.lower():
            return choice_key
    
    # تطبیق با شباهت زیاد (حاوی بودن)
    for choice_key, choice_display in choices:
        if str_value.lower() in str(choice_key).lower() or str_value.lower() in str(choice_display).lower():
            return choice_key
        if str(choice_key).lower() in str_value.lower() or str(choice_display).lower() in str_value.lower():
            return choice_key
    
    # اگر هیچ تطبیقی پیدا نشد، مقدار اصلی را برگردان
    return value


def get_model_field_choices(model_class, field_name):
    """
    دریافت مقادیر مجاز برای یک فیلد با choices
    """
    try:
        field = model_class._meta.get_field(field_name)
        if hasattr(field, 'choices') and field.choices:
            return [{'key': key, 'value': value} for key, value in field.choices]
        return []
    except Exception:
        return [] 


def get_column_letter(column_number):
    """
    Convert a column number to an Excel column letter (e.g., 1 -> A, 27 -> AA)
    """
    result = ""
    while column_number > 0:
        column_number, remainder = divmod(column_number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def parse_jalali_date(date_string):
    """
    پردازش تاریخ جلالی از فرمت‌های مختلف
    پشتیبانی از فرمت‌های: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    # حذف فضاهای اضافی
    date_string = date_string.strip()
    
    # فرمت‌های مختلف جداکننده
    separators = ['-', '/', '.']
    
    for separator in separators:
        if separator in date_string:
            try:
                parts = date_string.split(separator)
                if len(parts) == 3:
                    year, month, day = parts
                    
                    # تبدیل به عدد
                    year = int(year.strip())
                    month = int(month.strip())
                    day = int(day.strip())
                    
                    # بررسی اعتبار تاریخ جلالی
                    if validate_jalali_date(year, month, day):
                        # ایجاد تاریخ جلالی
                        from django_jalali.db import models as jmodels
                        return jmodels.jdatetime.datetime(year, month, day).date()
                    else:
                        logger.warning(f"تاریخ جلالی نامعتبر: {date_string}")
                        return None
                        
            except (ValueError, TypeError) as e:
                logger.warning(f"خطا در پردازش تاریخ جلالی {date_string}: {str(e)}")
                continue
    
    # اگر هیچ فرمت معتبری پیدا نشد
    logger.warning(f"فرمت تاریخ جلالی نامعتبر: {date_string}")
    return None


def validate_jalali_date(year, month, day):
    """
    بررسی اعتبار تاریخ جلالی
    """
    # بررسی محدوده سال
    if year < 1300 or year > 1500:  # محدوده منطقی برای سال جلالی
        return False
    
    # بررسی محدوده ماه
    if month < 1 or month > 12:
        return False
    
    # بررسی محدوده روز
    if day < 1 or day > 31:
        return False
    
    # بررسی روزهای ماه‌های مختلف
    if month <= 6 and day > 31:
        return False
    elif month <= 11 and day > 30:
        return False
    elif month == 12 and day > 29:  # اسفند
        return False
    
    return True


def parse_date_string(date_string):
    """
    پردازش تاریخ میلادی از فرمت‌های مختلف
    پشتیبانی از فرمت‌های: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    """
    if not date_string or not isinstance(date_string, str):
        return None
    
    # حذف فضاهای اضافی
    date_string = date_string.strip()
    
    # فرمت‌های مختلف جداکننده
    separators = ['-', '/', '.']
    
    for separator in separators:
        if separator in date_string:
            try:
                parts = date_string.split(separator)
                if len(parts) == 3:
                    year, month, day = parts
                    
                    # تبدیل به عدد
                    year = int(year.strip())
                    month = int(month.strip())
                    day = int(day.strip())
                    
                    # ایجاد تاریخ میلادی
                    return date(year, month, day)
                        
            except (ValueError, TypeError) as e:
                logger.warning(f"خطا در پردازش تاریخ میلادی {date_string}: {str(e)}")
                continue
    
    # اگر هیچ فرمت معتبری پیدا نشد
    logger.warning(f"فرمت تاریخ میلادی نامعتبر: {date_string}")
    return None


def parse_datetime_string(datetime_string):
    """
    پردازش تاریخ و زمان از فرمت‌های مختلف
    پشتیبانی از فرمت‌های: YYYY-MM-DD HH:MM:SS, YYYY/MM/DD HH:MM:SS
    """
    if not datetime_string or not isinstance(datetime_string, str):
        return None
    
    # حذف فضاهای اضافی
    datetime_string = datetime_string.strip()
    
    # جدا کردن تاریخ و زمان
    if ' ' in datetime_string:
        date_part, time_part = datetime_string.split(' ', 1)
        
        # پردازش تاریخ
        parsed_date = parse_date_string(date_part)
        if not parsed_date:
            return None
        
        # پردازش زمان
        try:
            time_parts = time_part.split(':')
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                
                return datetime.combine(parsed_date, datetime.min.time().replace(hour=hour, minute=minute, second=second))
        except (ValueError, TypeError) as e:
            logger.warning(f"خطا در پردازش زمان {time_part}: {str(e)}")
            return None
    else:
        # فقط تاریخ بدون زمان
        parsed_date = parse_date_string(datetime_string)
        if parsed_date:
            return datetime.combine(parsed_date, datetime.min.time())
    
    return None 