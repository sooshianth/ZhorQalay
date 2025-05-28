import os
import pandas as pd
import numpy as np
import json
import time
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import transaction, models, connections
from django.db.models import Q
from django.core.cache import cache
from .models import ImportExportSession, ImportExportLog, ImportRecord
from django.core.exceptions import ValidationError, FieldDoesNotExist
from django.utils.translation import gettext_lazy as _


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
    content_types = ContentType.objects.all().order_by('app_label', 'model')
    result = {}
    
    for ct in content_types:
        model_class = ct.model_class()
        if model_class is None:
            continue  # Skip if model class couldn't be loaded
        
        # Skip certain built-in models
        if ct.app_label in ['admin', 'auth', 'contenttypes', 'sessions', 'django_celery_beat']:
            continue
            
        if ct.app_label not in result:
            result[ct.app_label] = []
            
        result[ct.app_label].append({
            'name': model_class.__name__,
            'verbose_name': model_class._meta.verbose_name,
            'content_type_id': ct.id,
        })
    
    return result


def get_model_fields(app_label, model_name):
    """Get fields for a specific model."""
    try:
        # Normalize app_label and model_name
        app_label = app_label.lower().strip()
        model_name = model_name.strip()
        
        print(f"DEBUG: Looking up model: {app_label}.{model_name}")
        print(f"DEBUG: Type of app_label: {type(app_label)}, Type of model_name: {type(model_name)}")
        
        # First try: Directly use ContentType to look up the model
        try:
            from django.contrib.contenttypes.models import ContentType
            
            print(f"DEBUG: All ContentTypes for this app_label:")
            all_models = ContentType.objects.filter(app_label__iexact=app_label)
            for ct in all_models:
                print(f"  - {ct.app_label}.{ct.model} (ID: {ct.id})")
            
            # Try exact match first
            content_type = ContentType.objects.filter(
                app_label__iexact=app_label,
                model__iexact=model_name
            ).first()
            
            print(f"DEBUG: ContentType exact match result: {content_type}")
            
            # If not found, try case-insensitive match with model name only
            if not content_type:
                print(f"DEBUG: Exact match not found, trying case-insensitive with model name only")
                content_type = ContentType.objects.filter(
                    app_label__iexact=app_label,
                    model__icontains=model_name.lower()
                ).first()
                print(f"DEBUG: ContentType case-insensitive result: {content_type}")
            
            # If still not found, try with any model containing the name
            if not content_type:
                print(f"DEBUG: Case-insensitive match not found, trying content type lookup with partial match")
                content_type = ContentType.objects.filter(
                    app_label__iexact=app_label
                ).first()
                print(f"DEBUG: ContentType partial match result: {content_type}")
            
            if content_type:
                print(f"DEBUG: ContentType found: {content_type.app_label}.{content_type.model} (ID: {content_type.id})")
                model = content_type.model_class()
                print(f"DEBUG: Model class: {model.__name__}")
            else:
                print(f"DEBUG: No ContentType found for {app_label}.{model_name}")
                # Fall back to standard lookup
                print(f"DEBUG: Trying to get_model with: app_label='{app_label}', model_name='{model_name}'")
                model = apps.get_model(app_label, model_name)
                print(f"DEBUG: Model found via standard lookup: {model.__name__}")
        except Exception as e:
            print(f"DEBUG: ContentType lookup failed: {str(e)}")
            # Fall back to the original approach
            try:
                print(f"DEBUG: Trying apps.get_model({app_label}, {model_name})")
                model = apps.get_model(app_label, model_name)
                print(f"DEBUG: Model found via standard lookup: {model.__name__}")
            except Exception as inner_e:
                print(f"DEBUG: apps.get_model failed: {str(inner_e)}")
                print(f"DEBUG: Available apps and models:")
                for app_config in apps.get_app_configs():
                    print(f"  App: {app_config.label}")
                    for model in app_config.get_models():
                        print(f"    - {model.__name__}")
                raise inner_e
        
        print(f"DEBUG: Getting fields for model: {model.__name__}")
        fields = []
        
        for field in model._meta.get_fields():
            # Skip many-to-many fields and reverse relations
            if field.is_relation and (field.many_to_many or field.one_to_many):
                continue
                
            field_info = {
                'name': field.name,
                'verbose_name': field.verbose_name if hasattr(field, 'verbose_name') else field.name,
                'type': field.__class__.__name__,
                'required': not field.blank if hasattr(field, 'blank') else False,
                'primary_key': field.primary_key if hasattr(field, 'primary_key') else False,
            }
            
            # Add choices if available
            if hasattr(field, 'choices') and field.choices:
                field_info['choices'] = [{'value': value, 'display': display} for value, display in field.choices]
                
            # Add foreign key information
            if field.is_relation and hasattr(field, 'remote_field') and field.remote_field:
                related_model = field.remote_field.model
                field_info['related_model'] = {
                    'app_label': related_model._meta.app_label,
                    'model_name': related_model.__name__,
                    'verbose_name': related_model._meta.verbose_name,
                }
                
            fields.append(field_info)
        
        print(f"DEBUG: Found {len(fields)} fields for {model.__name__}")
        print(f"DEBUG: First 3 fields: {fields[:3]}")
        return fields
    except Exception as e:
        print(f"DEBUG: Error getting fields for {app_label}.{model_name}: {str(e)}")
        import traceback
        traceback.print_exc()
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
    
    # Strategy 1: Exact match (always include this)
    strategies.append({
        'lookup': {identifier_field: identifier_value},
        'description': 'Exact match'
    })
    
    # For string fields, add case-insensitive lookup
    if isinstance(field, (models.CharField, models.TextField)):
        strategies.append({
            'lookup': {f"{identifier_field}__iexact": identifier_value},
            'description': 'Case-insensitive match'
        })
        
        # For numbers stored as strings, try to convert and match
        if isinstance(identifier_value, str) and identifier_value.strip().isdigit():
            cleaned_value = identifier_value.strip()
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
            'lookup': {f"{identifier_field}__contains": identifier_value},
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
            break
    
    # If we have a unique identifier field, check for existing records
    existing_records = {}
    if unique_identifier_field:
        # Get all values of the identifier field
        identifier_values = dataframe[unique_identifier_field].dropna().unique().tolist()
        if identifier_values:
            # For each identifier value, try to find an existing record
            for value in identifier_values:
                if pd.notna(value):
                    model_field = mapping[unique_identifier_field]['model_field']
                    instance, strategy = find_existing_instance(model_class, model_field, value)
                    if instance:
                        existing_records[str(value)] = {
                            'instance': instance,
                            'strategy': strategy
                        }
    
    # Validate each row
    for index, row in dataframe.iterrows():
        row_number = index + 2  # +2 because pandas is 0-indexed and we have a header row
        row_errors = []
        
        # Check for existing record
        is_update = False
        if unique_identifier_field:
            identifier_value = row.get(unique_identifier_field)
            if pd.notna(identifier_value) and str(identifier_value) in existing_records:
                is_update = True
                match_info = existing_records[str(identifier_value)]
                warnings.append({
                    'row': row_number,
                    'field': unique_identifier_field,
                    'message': f"Found existing record using {match_info['strategy']}"
                })
        
        # Check required fields
        for field_name, field_mapping in mapping.items():
            if not field_mapping.get('model_field'):
                continue  # Skip fields not mapped
                
            model_field = field_mapping['model_field']
            model_field_obj = next((f for f in model_class._meta.fields if f.name == model_field), None)
            
            if model_field_obj and not model_field_obj.blank and not model_field_obj.null:
                if field_name not in row or pd.isna(row[field_name]):
                    if is_update:
                        warnings.append({
                            'row': row_number,
                            'field': field_name,
                            'message': f"Field '{field_name}' is required but has no value. Will keep existing value for update."
                        })
                    else:
                        row_errors.append({
                            'field': field_name,
                            'message': f"Field '{field_name}' is required but has no value."
                        })
        
        if row_errors:
            errors.append({
                'row': row_number,
                'errors': row_errors
            })
    
    return {
        'valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'updates': len(existing_records),
        'creates': len(dataframe) - len(existing_records),
    }


def process_import(session):
    """Process the import operation."""
    # Check database connection first
    test_database_connection()
    
    # Try to acquire a lock
    if not acquire_lock(session):
        raise ValueError("This session is already being processed by another request. Please try again later.")
    
    # Collect errors outside of transaction
    processing_errors = []
    
    try:
        # Get the session info
        model_class = session.get_model_class()
        mapping = session.mapping
        
        # Read the file
        file_path = session.file.path
        file_extension = get_file_extension(session.file_name)
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Update session status outside of atomic block first
        session.status = ImportExportSession.PROCESSING
        session.row_count = len(df)
        session.save()
        
        # Log start of processing
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.INFO,
            message=f"Started processing {session.row_count} rows."
        )
        
        # Find identifier field (for updates)
        identifier_field = None
        identifier_model_field = None
        for field_name, field_config in mapping.items():
            if field_config.get('is_identifier', False):
                identifier_field = field_name
                identifier_model_field = field_config['model_field']
                break
        
        # Process each row in separate atomic blocks
        for index, row in df.iterrows():
            row_number = index + 2  # +2 because pandas is 0-indexed and we have a header row
            
            try:
                with transaction.atomic():
                    # Check if this is an update
                    existing_instance = None
                    match_strategy = None
                    
                    if identifier_field and pd.notna(row.get(identifier_field)):
                        lookup_value = row[identifier_field]
                        existing_instance, match_strategy = find_existing_instance(
                            model_class, identifier_model_field, lookup_value
                        )
                    
                    # Create or update instance
                    if existing_instance:
                        # Update existing record
                        previous_state = {
                            field.name: getattr(existing_instance, field.name)
                            for field in existing_instance._meta.fields
                            if not field.primary_key
                        }
                        
                        # Apply mapped fields
                        for field_name, field_config in mapping.items():
                            if not field_config.get('model_field'):
                                continue
                            
                            model_field = field_config['model_field']
                            if field_name in row and pd.notna(row[field_name]):
                                value = row[field_name]
                                
                                # Sanitize the value based on field type
                                field_obj = model_class._meta.get_field(model_field)
                                value = sanitize_value(value, field_obj)
                                
                                # Handle ForeignKey fields
                                if isinstance(field_obj, models.ForeignKey):
                                    # Try to get or create the related object
                                    related_model = field_obj.remote_field.model
                                    related_obj = find_related_object(related_model, value)
                                    
                                    if related_obj:
                                        setattr(existing_instance, model_field, related_obj)
                                    else:
                                        # Collect warning for later logging
                                        processing_errors.append({
                                            'level': ImportExportLog.WARNING,
                                            'message': f"Could not find related object for field {model_field} with value {value}",
                                            'row_number': row_number
                                        })
                                else:
                                    # For non-foreign key fields, set the value directly
                                    setattr(existing_instance, model_field, value)
                        
                        # Save the instance
                        existing_instance.save()
                        
                        # Record the update
                        current_state = {
                            field.name: getattr(existing_instance, field.name)
                            for field in existing_instance._meta.fields
                            if not field.primary_key
                        }
                        
                        ImportRecord.objects.create(
                            session=session,
                            content_type=session.content_type,
                            object_id=existing_instance.pk,
                            row_number=row_number,
                            action='update',
                            previous_state=previous_state,
                            current_state=current_state
                        )
                        
                        # Log success outside of atomic block
                        processing_errors.append({
                            'level': ImportExportLog.SUCCESS,
                            'message': f"Updated record with ID {existing_instance.pk} using {match_strategy}",
                            'row_number': row_number
                        })
                    else:
                        # Create new record
                        instance_data = {}
                        foreign_key_data = {}
                        
                        # First pass - handle regular fields
                        for field_name, field_config in mapping.items():
                            if not field_config.get('model_field'):
                                continue
                            
                            model_field = field_config['model_field']
                            if field_name in row and pd.notna(row[field_name]):
                                value = row[field_name]
                                
                                # Sanitize the value based on field type
                                field_obj = model_class._meta.get_field(model_field)
                                value = sanitize_value(value, field_obj)
                                
                                # Check if this is a foreign key field
                                if isinstance(field_obj, models.ForeignKey):
                                    foreign_key_data[model_field] = value
                                else:
                                    instance_data[model_field] = value
                        
                        # Create the instance first with non-foreign key fields
                        new_instance = model_class.objects.create(**instance_data)
                        
                        # Second pass - handle foreign keys now that we have an instance
                        for model_field, value in foreign_key_data.items():
                            field_obj = model_class._meta.get_field(model_field)
                            related_model = field_obj.remote_field.model
                            related_obj = find_related_object(related_model, value)
                            
                            if related_obj:
                                setattr(new_instance, model_field, related_obj)
                                new_instance.save()
                            else:
                                # Collect warning for later logging
                                processing_errors.append({
                                    'level': ImportExportLog.WARNING,
                                    'message': f"Could not find related object for field {model_field} with value {value}",
                                    'row_number': row_number
                                })
                        
                        # Record the creation
                        current_state = {
                            field.name: getattr(new_instance, field.name)
                            for field in new_instance._meta.fields
                            if not field.primary_key
                        }
                        
                        ImportRecord.objects.create(
                            session=session,
                            content_type=session.content_type,
                            object_id=new_instance.pk,
                            row_number=row_number,
                            action='create',
                            previous_state=None,
                            current_state=current_state
                        )
                        
                        # Log success for later
                        processing_errors.append({
                            'level': ImportExportLog.SUCCESS,
                            'message': f"Created new record with ID {new_instance.pk}",
                            'row_number': row_number
                        })
                    
                    session.processed_count += 1
                    
            except Exception as e:
                # Collect error for later logging
                processing_errors.append({
                    'level': ImportExportLog.ERROR,
                    'message': f"Error processing row {row_number}: {str(e)}",
                    'row_number': row_number
                })
                session.error_count += 1
        
        # Update session status
        session.status = ImportExportSession.COMPLETED
        session.save()
        
        # Log all collected messages
        for error_info in processing_errors:
            ImportExportLog.objects.create(
                session=session,
                log_level=error_info['level'],
                message=error_info['message'],
                row_number=error_info.get('row_number')
            )
        
        # Log completion
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.INFO,
            message=f"Import completed. {session.processed_count} records processed, {session.error_count} errors."
        )
    except Exception as e:
        # Handle any unexpected errors
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"Import failed with error: {str(e)}"
        )
        raise
    finally:
        # Always release the lock
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
        
        # Create the export file
        file_path = f"media/data_exflow/files/export_{session.id}.{format}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save based on format
        if format.lower() == 'xlsx':
            final_df.to_excel(file_path, index=False)
        elif format.lower() == 'csv':
            final_df.to_csv(file_path, index=False)
        else:
            # Default to Excel
            final_df.to_excel(file_path, index=False)
        
        # Update the session with the file
        with open(file_path, 'rb') as f:
            session.file.save(f"export_{session.id}.{format}", f)
        
        session.record_count = len(final_df)
        session.processed_count = len(final_df)
        session.status = ImportExportSession.COMPLETED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.INFO,
            message=f"Export completed. {session.processed_count} records exported."
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
    
    return value 