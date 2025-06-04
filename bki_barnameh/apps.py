from django.apps import AppConfig


class BkiBarnamehConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bki_barnameh'

    def ready(self):
        import bki_barnameh.signals
