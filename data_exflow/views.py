from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied
import pandas as pd
import numpy as np
import json
import os
import uuid
import tempfile

from .models import ImportExportSession, ImportExportLog, ImportRecord
from .utils import (
    get_file_extension, is_valid_file_type, read_file_to_dataframe,
    get_all_registered_models, get_model_fields, validate_import_data,
    process_import, revert_import, process_export
)

# Create your views here.

# ---------------------------
# Import Views
# ---------------------------

@login_required
def import_view(request):
    """Main import view showing available models to import."""
    models = get_all_registered_models()
    
    context = {
        'title': 'Import Data',
        'models': models,
    }
    
    return render(request, 'data_exflow/import.html', context)


@login_required
def import_upload(request):
    """Handle file upload for import."""
    if request.method != 'POST':
        return redirect('data_exflow:import')
    
    # Get form data
    content_type_id = request.POST.get('content_type_id')
    file = request.FILES.get('file')
    
    if not content_type_id or not file:
        messages.error(request, 'Missing required fields')
        return redirect('data_exflow:import')
    
    # Check if content type exists
    try:
        content_type = ContentType.objects.get(id=content_type_id)
    except ContentType.DoesNotExist:
        messages.error(request, 'Invalid model selected')
        return redirect('data_exflow:import')
    
    # Check file extension
    file_extension = get_file_extension(file.name)
    if not is_valid_file_type(file_extension):
        messages.error(request, f'Invalid file type: {file_extension}. Supported types: .xlsx, .xls, .csv')
        return redirect('data_exflow:import')
    
    # Create import session
    session = ImportExportSession.objects.create(
        session_type=ImportExportSession.IMPORT,
        user=request.user,
        content_type=content_type,
        file=file,
        file_name=file.name,
        file_type=file_extension.replace('.', ''),
        status=ImportExportSession.PENDING
    )
    
    # Log file upload
    ImportExportLog.objects.create(
        session=session,
        log_level=ImportExportLog.INFO,
        message=f"File '{file.name}' uploaded for {content_type.model} import"
    )
    
    return redirect('data_exflow:import_preview', session_id=session.id)


@login_required
def import_preview(request, session_id):
    """Preview the uploaded file contents."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    # Read the file
    file_path = session.file.path
    file_extension = get_file_extension(session.file_name)
    
    try:
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Convert dataframe to JSON for template
        preview_data = {
            'columns': df.columns.tolist(),
            'rows': df.head(10).replace({np.nan: None}).to_dict('records'),
            'total_rows': len(df)
        }
        
        # Get model fields for mapping
        model_class = session.get_model_class()
        fields = get_model_fields(model_class._meta.app_label, model_class.__name__)
        
        context = {
            'title': 'Preview Import Data',
            'session': session,
            'preview': preview_data,
            'model_fields': fields,
        }
        
        return render(request, 'data_exflow/import_preview.html', context)
    except Exception as e:
        messages.error(request, f'Error reading file: {str(e)}')
        return redirect('data_exflow:import')


@login_required
def import_map_fields(request, session_id):
    """Map file columns to model fields."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    if request.method != 'POST':
        return redirect('data_exflow:import_preview', session_id=session.id)
    
    # Get mapping data from form
    mapping = {}
    identifier_field = request.POST.get('identifier_field')
    
    # Read the file to get columns
    file_path = session.file.path
    file_extension = get_file_extension(session.file_name)
    df = read_file_to_dataframe(file_path, file_extension)
    columns = df.columns.tolist()
    
    # Process field mapping
    for column in columns:
        model_field = request.POST.get(f'map_{column}')
        if model_field and model_field != 'ignore':
            mapping[column] = {
                'model_field': model_field,
                'is_identifier': column == identifier_field
            }
    
    # Save mapping to session
    session.mapping = mapping
    session.save()
    
    # Log mapping
    ImportExportLog.objects.create(
        session=session,
        log_level=ImportExportLog.INFO,
        message=f"Field mapping created with {len(mapping)} fields"
    )
    
    return redirect('data_exflow:import_validate', session_id=session.id)


@login_required
def import_validate(request, session_id):
    """Validate the import data against the model."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    if not session.mapping:
        messages.error(request, 'No field mapping found')
        return redirect('data_exflow:import_preview', session_id=session.id)
    
    # Update session status
    session.status = ImportExportSession.VALIDATING
    session.save()
    
    # Read the file
    file_path = session.file.path
    file_extension = get_file_extension(session.file_name)
    
    try:
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Validate data
        validation_result = validate_import_data(session, df, session.mapping)
        
        # Update session status
        session.status = ImportExportSession.VALIDATED if validation_result['valid'] else ImportExportSession.FAILED
        session.save()
        
        # Log validation results
        if validation_result['valid']:
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.SUCCESS,
                message=f"Validation successful. {validation_result['creates']} records to create, {validation_result['updates']} records to update."
            )
        else:
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.ERROR,
                message=f"Validation failed with {len(validation_result['errors'])} errors."
            )
            
            # Log each error
            for error in validation_result['errors']:
                ImportExportLog.objects.create(
                    session=session,
                    log_level=ImportExportLog.ERROR,
                    message=f"Row {error['row']}: " + ", ".join([e['message'] for e in error['errors']]),
                    row_number=error['row']
                )
        
        # Prepare warning logs
        for warning in validation_result.get('warnings', []):
            ImportExportLog.objects.create(
                session=session,
                log_level=ImportExportLog.WARNING,
                message=warning['message'],
                row_number=warning['row']
            )
        
        context = {
            'title': 'Validate Import Data',
            'session': session,
            'validation': validation_result,
            'logs': ImportExportLog.objects.filter(session=session).order_by('-created_at')[:20]
        }
        
        return render(request, 'data_exflow/import_validate.html', context)
        
    except Exception as e:
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"Validation error: {str(e)}"
        )
        
        messages.error(request, f'Validation error: {str(e)}')
        return redirect('data_exflow:import')


@login_required
def import_process(request, session_id):
    """Process the import operation."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    if session.status != ImportExportSession.VALIDATED:
        messages.error(request, 'Session not validated')
        return redirect('data_exflow:import_validate', session_id=session.id)
    
    if request.method != 'POST':
        return redirect('data_exflow:import_validate', session_id=session.id)
    
    try:
        # Process the import
        process_import(session)
        
        messages.success(request, 'Import process completed successfully')
        return redirect('data_exflow:import_results', session_id=session.id)
        
    except Exception as e:
        session.status = ImportExportSession.FAILED
        session.save()
        
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"Import process error: {str(e)}"
        )
        
        messages.error(request, f'Import process error: {str(e)}')
        return redirect('data_exflow:import_validate', session_id=session.id)


@login_required
def import_results(request, session_id):
    """Show import results."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    # Get logs
    logs = ImportExportLog.objects.filter(session=session).order_by('-created_at')
    
    # Get import records
    import_records = ImportRecord.objects.filter(session=session).order_by('row_number')
    
    context = {
        'title': 'Import Results',
        'session': session,
        'logs': logs,
        'records': import_records,
        'success_count': import_records.filter(action='create').count() + import_records.filter(action='update').count(),
        'create_count': import_records.filter(action='create').count(),
        'update_count': import_records.filter(action='update').count(),
    }
    
    return render(request, 'data_exflow/import_results.html', context)


@login_required
def import_revert(request, session_id):
    """Revert an import operation."""
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        messages.error(request, 'Invalid session type')
        return redirect('data_exflow:import')
    
    if not session.can_be_reverted:
        messages.error(request, 'This session cannot be reverted')
        return redirect('data_exflow:import_results', session_id=session.id)
    
    if request.method != 'POST':
        return redirect('data_exflow:import_results', session_id=session.id)
    
    try:
        # Revert the import
        revert_import(session)
        
        messages.success(request, 'Import reverted successfully')
        return redirect('data_exflow:import_results', session_id=session.id)
        
    except Exception as e:
        ImportExportLog.objects.create(
            session=session,
            log_level=ImportExportLog.ERROR,
            message=f"Revert error: {str(e)}"
        )
        
        messages.error(request, f'Revert error: {str(e)}')
        return redirect('data_exflow:import_results', session_id=session.id)


# ---------------------------
# Export Views
# ---------------------------

@login_required
def export_view(request):
    """Main export view showing available models to export."""
    models = get_all_registered_models()
    
    context = {
        'title': 'Export Data',
        'models': models,
    }
    
    return render(request, 'data_exflow/export.html', context)


@login_required
def export_select_fields(request):
    """Select fields to export."""
    if request.method != 'POST':
        return redirect('data_exflow:export')
    
    # Get selected models
    selected_models = request.POST.getlist('content_type_id')
    
    if not selected_models:
        messages.error(request, 'No models selected')
        return redirect('data_exflow:export')
    
    # Get content types and model fields
    content_types = []
    model_fields = {}
    
    for ct_id in selected_models:
        try:
            ct = ContentType.objects.get(id=ct_id)
            content_types.append(ct)
            
            model_class = ct.model_class()
            fields = get_model_fields(model_class._meta.app_label, model_class.__name__)
            
            model_fields[f"{ct.app_label}.{ct.model}"] = fields
            
        except ContentType.DoesNotExist:
            continue
    
    context = {
        'title': 'Select Export Fields',
        'content_types': content_types,
        'model_fields': model_fields,
    }
    
    return render(request, 'data_exflow/export_select_fields.html', context)


@login_required
def export_process(request):
    """Process the export operation."""
    if request.method != 'POST':
        return redirect('data_exflow:export')
    
    # Get form data
    field_mapping = {}
    content_types = []
    
    # Process all models and their fields
    for key, value in request.POST.items():
        if key.startswith('field_'):
            # Format: field_app-label_model_fieldname
            _, app_label, model, field_name = key.split('_', 3)
            
            model_key = f"{app_label}.{model}"
            if model_key not in field_mapping:
                field_mapping[model_key] = {}
                
                # Add content type
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model)
                    content_types.append(ct)
                except ContentType.DoesNotExist:
                    continue
            
            # Add field mapping with the exported name as value
            field_mapping[model_key][field_name] = value
    
    if not content_types or not field_mapping:
        messages.error(request, 'No fields selected for export')
        return redirect('data_exflow:export')
    
    try:
        # Process the export
        session = process_export(content_types, field_mapping, request.user)
        
        # Serve the file
        response = HttpResponse(
            session.file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{session.file_name}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Export error: {str(e)}')
        return redirect('data_exflow:export')


# ---------------------------
# API Views
# ---------------------------

@login_required
def api_get_models(request):
    """API endpoint to get all available models."""
    models = get_all_registered_models()
    return JsonResponse(models)


@login_required
def api_get_model_fields(request, app_label, model_name):
    """API endpoint to get fields for a specific model."""
    fields = get_model_fields(app_label, model_name)
    return JsonResponse({'fields': fields})


@csrf_exempt
@login_required
def api_edit_cell(request, session_id):
    """API endpoint to edit a cell in the preview."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    session = get_object_or_404(ImportExportSession, id=session_id, user=request.user)
    
    if session.session_type != ImportExportSession.IMPORT:
        return JsonResponse({'error': 'Invalid session type'}, status=400)
    
    try:
        data = json.loads(request.body)
        row = data.get('row')
        column = data.get('column')
        value = data.get('value')
        
        if row is None or column is None or value is None:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        # Read the file
        file_path = session.file.path
        file_extension = get_file_extension(session.file_name)
        
        df = read_file_to_dataframe(file_path, file_extension)
        
        # Update the cell value
        df.iloc[row, df.columns.get_loc(column)] = value
        
        # Create a temporary file to save the updated data
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
            temp_path = tmp.name
            
            # Save the dataframe to the temporary file
            if file_extension in ['.xlsx', '.xls']:
                df.to_excel(temp_path, index=False)
            elif file_extension == '.csv':
                df.to_csv(temp_path, index=False)
        
        # Save the updated file
        with open(temp_path, 'rb') as f:
            session.file.save(session.file_name, f)
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
