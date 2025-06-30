from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class FledgerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fledger'
    verbose_name = _('مدیریت کیف پول')
    
    def ready(self):
        import fledger.models  # Import models to register signals