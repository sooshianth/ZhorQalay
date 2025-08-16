from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'داده‌های اصلی'

    def ready(self):
        # Load app signals (non‑DB)
        import core.zignals
        # Load SQLite PRAGMA signal handler
        import core.db_pragmas
