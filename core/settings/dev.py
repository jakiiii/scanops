from .base import *

INSTALLED_APPS = INSTALLED_APPS + [
    'django_extensions',
    'drf_yasg',
]

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

if os.environ.get('JTRO_DEV_DATABASE') == "postgres":
    DATABASES = {
        'default': {
            'ENGINE': os.environ.get('JTRO_DEV_DATABASE_ENGINE'),
            'NAME': os.environ.get('JTRO_DEV_DATABASE_NAME'),
            'USER': os.environ.get('JTRO_DEV_DATABASE_USER'),
            'PASSWORD': os.environ.get('JTRO_DEV_DATABASE_PASSWORD'),
            'HOST': os.environ.get('JTRO_DEV_DATABASE_HOST'),
            'PORT': os.environ.get('JTRO_DEV_DATABASE_PORT'),
        }
    }
else:
    sqlite_name = os.environ.get("JTRO_SQLITE_PATH")
    if not sqlite_name:
        sqlite_name = os.path.join(BASE_DIR, "db.sqlite3")

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_name,
        }
    }

SWAGGER_SETTINGS = {
    'DEFAULT_FIELD_INSPECTORS': [
        'drf_yasg.inspectors.CamelCaseJSONFilter',
        'drf_yasg.inspectors.InlineSerializerInspector',
        'drf_yasg.inspectors.RelatedFieldInspector',
        'drf_yasg.inspectors.ChoiceFieldInspector',
        'drf_yasg.inspectors.FileFieldInspector',
        'drf_yasg.inspectors.DictFieldInspector',
        'drf_yasg.inspectors.SimpleFieldInspector',
        'drf_yasg.inspectors.StringDefaultFieldInspector',
    ],
}

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
