import os
from pathlib import Path
from celery.schedules import crontab
import dotenv
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure-@22ofzh7o7x!4+a$&(#b&--%20i1q*nz0s!_k)!7ky@2@3ugb+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '192.168.100.56']

# Session timeout configuration
SESSION_COOKIE_AGE = 1200  # 20 minutes in seconds
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Application definition

GRAPH_MODELS = {
    'all_applications': True,  # نمایش همه اپلیکیشن‌های نصب‌شده
    'group_models': True,      # گروه‌بندی مدل‌ها بر اساس اپلیکیشن
    'inheritance': True,       # نمایش ارث‌بری بین مدل‌ها
    'fields': True,            # نمایش فیلدها
}

INSTALLED_APPS = [
    'channels',
    'daphne',
    'colorfield',
    'captcha',
    'django_celery_beat',
    'rest_framework',
    'whatsapp_api.apps.WhatsappApiConfig',
    'admin_interface',  
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_extensions',
    'django_jalali',
    'sms_ir',
    'core.apps.CoreConfig',
    'sales.apps.SalesConfig',
    'ERP.apps.ERPConfig',
    'authentication.apps.AuthenticationConfig',
    'sms_api.apps.SmsApiConfig',
    'chat.apps.ChatConfig',
    'HR.apps.HRConfig',
    'todo.apps.TodoConfig',
    'bki_api.apps.BkiApiConfig',
    'bki_barnameh.apps.BkiBarnamehConfig',
    'bki_cargos.apps.BkiCargosConfig',
    'data_exflow.apps.DataExflowConfig',
    'table_filter.apps.TableFilterConfig',
    'bi.apps.BIConfig',
    'fledger.apps.FledgerConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'config.middleware.SessionTimeoutMiddleware',
    'config.middleware.RestrictAdminAccessMiddleware',
    'HR.middleware.DebugMiddleware',  # دیباگ میدلور

]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', BASE_DIR / 'core/templates', BASE_DIR / 'sales/templates', BASE_DIR / 'ERP/templates', BASE_DIR / 'CRM/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# CACHES = {
#     "default": {
#         "BACKEND": "django.core.cache.backends.redis.RedisCache",
#         "LOCATION": "redis://127.0.0.1:6379/1",
#     }
# }

LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True

CRISPY_TEMPLATE_PACK = 'bootstrap4'

STATIC_ROOT = BASE_DIR / 'static'
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "core/static",
    BASE_DIR / "sales/static",
    BASE_DIR / "ERP/static",
    BASE_DIR / "authentication/static",
    BASE_DIR / "table_filter/static",
    # BASE_DIR / "excel_manager/static",
    BASE_DIR / "sms_api/static",
    BASE_DIR / "whatsapp_api/static",
    BASE_DIR / "fledger/static",
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


DEFAULT_LOGIN_URL = 'welcome_profile'
DEFAULT_LOGIN_REDIRECT_URL = 'home_view'
DEFAULT_LOGOUT_URL = 'logout'

# تنظیمات آپلود فایل
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# تنظیمات لاگینگ
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'excel_manager': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# SMS API Settings
SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
SMS_LINE_NUMBER = int(os.environ.get('SMS_LINE_NUMBER', '0'))

# BKI API Settings
BKI_USERNAME = os.environ.get('BKI_USERNAME', '')
BKI_PASSWORD = os.environ.get('BKI_PASSWORD', '')

# Sales Agent SMS Qouta
SALES_AGENT_SMS_QOUTA = int(os.environ.get('SALES_AGENT_SMS_QOUTA', '0'))