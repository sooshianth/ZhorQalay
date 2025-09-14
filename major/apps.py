from django.apps import AppConfig

class MajorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'major'
    
    def ready(self):
        # بارگذاری سیگنال‌ها
        import major.signals