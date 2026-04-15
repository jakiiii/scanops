from .base import *
from django.core.exceptions import ImproperlyConfigured

# Production settings must never expose Django debug pages.
if env_flag('JTRO_DEBUG', default=False):
    raise ImproperlyConfigured("JTRO_DEBUG cannot be enabled with core.settings.production.")

DEBUG = False

if not SECRET_KEY:
    raise ImproperlyConfigured("JTRO_SECRET_KEY environment variable is required in production.")

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("JTRO_ALLOWED_HOSTS must be configured in production.")
INSTALLED_APPS = INSTALLED_APPS + [

]

# Database
# https://docs.djangoproject.com/en/4.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('JTRO_DATABASE_ENGINE'),
        'NAME': os.environ.get('JTRO_DATABASE_NAME'),
        'USER': os.environ.get('JTRO_DATABASE_USER'),
        'PASSWORD': os.environ.get('JTRO_DATABASE_PASSWORD'),
        'HOST': os.environ.get('JTRO_DATABASE_HOST'),
        'PORT': os.environ.get('JTRO_DATABASE_PORT'),
    }
}

SSL_ENABLED = env_flag('JTRO_SSL_ENABLED', default=True)

if SSL_ENABLED:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_flag('JTRO_SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = env_flag('JTRO_SESSION_COOKIE_SECURE', default=True)
    CSRF_COOKIE_SECURE = env_flag('JTRO_CSRF_COOKIE_SECURE', default=True)
    SECURE_HSTS_SECONDS = int(os.environ.get('JTRO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag('JTRO_HSTS_INCLUDE_SUBDOMAINS', default=True)
    SECURE_HSTS_PRELOAD = env_flag('JTRO_HSTS_PRELOAD', default=True)
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
