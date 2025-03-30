from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'داده‌های اصلی'
    def ready(self):
        # اتصال سیگنال‌ها
        import core.zignals