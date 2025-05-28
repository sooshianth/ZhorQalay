from django.db import models
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.models import ContentType
import uuid
import json

User = get_user_model()

class ImportExportSession(models.Model):
    """Stores information about an import or export session."""
    IMPORT = 'import'
    EXPORT = 'export'
    SESSION_TYPES = (
        (IMPORT, _('Import')),
        (EXPORT, _('Export')),
    )
    
    PENDING = 'pending'
    VALIDATING = 'validating'
    VALIDATED = 'validated'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'
    REVERTED = 'reverted'
    
    STATUS_CHOICES = (
        (PENDING, _('Pending')),
        (VALIDATING, _('Validating')),
        (VALIDATED, _('Validated')),
        (PROCESSING, _('Processing')),
        (COMPLETED, _('Completed')),
        (FAILED, _('Failed')),
        (REVERTED, _('Reverted')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_type = models.CharField(max_length=10, choices=SESSION_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='import_export_sessions')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    file = models.FileField(upload_to='data_exflow/files/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    row_count = models.IntegerField(default=0)
    processed_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    mapping = models.JSONField(null=True, blank=True)
    is_locked = models.BooleanField(default=False, help_text=_("Indicates if this session is currently being processed"))
    
    def __str__(self):
        return f"{self.get_session_type_display()} - {self.content_type} - {self.created_at}"

    def get_model_class(self):
        """Get the model class from the content type."""
        return self.content_type.model_class()
    
    @property
    def is_import(self):
        return self.session_type == self.IMPORT
    
    @property
    def is_export(self):
        return self.session_type == self.EXPORT
    
    @property
    def can_be_reverted(self):
        return self.is_import and self.status == self.COMPLETED


class ImportExportLog(models.Model):
    """Logs for import/export operations."""
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    SUCCESS = 'success'
    
    LOG_LEVEL_CHOICES = (
        (INFO, _('Info')),
        (WARNING, _('Warning')),
        (ERROR, _('Error')),
        (SUCCESS, _('Success')),
    )
    
    session = models.ForeignKey(ImportExportSession, on_delete=models.CASCADE, related_name='logs')
    log_level = models.CharField(max_length=10, choices=LOG_LEVEL_CHOICES, default=INFO)
    message = models.TextField()
    row_number = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_log_level_display()} - {self.created_at}"


class ImportRecord(models.Model):
    """Keeps track of imported records for potential reversion."""
    session = models.ForeignKey(ImportExportSession, on_delete=models.CASCADE, related_name='import_records')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.TextField()
    row_number = models.IntegerField()
    action = models.CharField(max_length=10, choices=(('create', 'Create'), ('update', 'Update')))
    previous_state = models.JSONField(null=True, blank=True)  # Only for updates
    current_state = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} - {self.content_type} - {self.object_id}"
