import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PRODUCTION = os.environ.get('LMS_ENV','development') == 'production'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'local-development-only-change-before-deployment')
DEBUG = os.environ.get('DJANGO_DEBUG', '0' if PRODUCTION else '1') == '1'
if not DEBUG and SECRET_KEY.startswith('local-'):
    raise RuntimeError('Set DJANGO_SECRET_KEY before disabling development mode')
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if h.strip()]
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'lms']
MIDDLEWARE = ['lms.middleware.LmsPrivateResponses','django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
if os.environ.get('POSTGRES_DB'):
    DATABASES['default'] = {'ENGINE': 'django.db.backends.postgresql', 'NAME': os.environ['POSTGRES_DB'], 'USER': os.environ.get('POSTGRES_USER', 'postgres'), 'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''), 'HOST': os.environ.get('POSTGRES_HOST', 'localhost'), 'PORT': os.environ.get('POSTGRES_PORT', '5432')}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = os.environ.get('LMS_TIME_ZONE','Asia/Kolkata')
LIBRARY_LOAN_DAYS = int(os.environ.get('LIBRARY_LOAN_DAYS', '14'))
if LIBRARY_LOAN_DAYS <= 0:
    raise RuntimeError('LIBRARY_LOAN_DAYS must be a positive number of days')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_TRUSTED_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
AUTH_PASSWORD_VALIDATORS = []
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 30 * 1024 * 1024
MAX_UPLOAD_BYTES = int(os.environ.get('MAX_UPLOAD_BYTES',str(512*1024*1024 if PRODUCTION else 25*1024*1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = 2*1024*1024
PUBLIC_APP_URL = os.environ.get('PUBLIC_APP_URL','http://127.0.0.1:3000').rstrip('/')
ENTRA_TENANT_ID = os.environ.get('ENTRA_TENANT_ID','')
ENTRA_CLIENT_ID = os.environ.get('ENTRA_CLIENT_ID','')
ENTRA_CLIENT_SECRET = os.environ.get('ENTRA_CLIENT_SECRET','')
ENTRA_API_AUDIENCE = os.environ.get('ENTRA_API_AUDIENCE',ENTRA_CLIENT_ID)
ENTRA_AUTHORITY = os.environ.get('ENTRA_AUTHORITY',f'https://login.microsoftonline.com/{ENTRA_TENANT_ID}')
ENTRA_ISSUER = os.environ.get('ENTRA_ISSUER',f'https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0')
ENTRA_JWKS_URL = os.environ.get('ENTRA_JWKS_URL',f'https://login.microsoftonline.com/{ENTRA_TENANT_ID}/discovery/v2.0/keys')
INSTITUTION_ID = os.environ.get('INSTITUTION_ID','demo')
DEFAULT_CAMPUS = os.environ.get('DEFAULT_CAMPUS','main')
if PRODUCTION:
    from .production import apply
    apply(globals())
elif os.environ.get('LMS_ENV') == 'demo':
    from .demo import apply
    apply(globals())

LIVE_ROOM_POLL_SECONDS = int(os.environ.get('LIVE_ROOM_POLL_SECONDS', '5'))
LECTURE_PROGRESS_SAVE_SECONDS = int(os.environ.get('LECTURE_PROGRESS_SAVE_SECONDS', '15'))
PERSONALISATION_REVIEW_BELOW_PERCENT = int(os.environ.get('PERSONALISATION_REVIEW_BELOW_PERCENT', '70'))
PERSONALISATION_PACE_LIMITS = {
    'Gentle':int(os.environ.get('PERSONALISATION_GENTLE_LIMIT','3')),
    'Steady':int(os.environ.get('PERSONALISATION_STEADY_LIMIT','6')),
    'Intensive':int(os.environ.get('PERSONALISATION_INTENSIVE_LIMIT','10')),
}
if not 0 <= PERSONALISATION_REVIEW_BELOW_PERCENT <= 100 or any(value <= 0 for value in PERSONALISATION_PACE_LIMITS.values()):
    raise RuntimeError('Personalisation needs a percentage from 0 to 100 and positive pace limits')
if LECTURE_PROGRESS_SAVE_SECONDS <= 0:
    raise RuntimeError('LECTURE_PROGRESS_SAVE_SECONDS must be positive')
LIVE_LATE_AFTER_MINUTES = int(os.environ.get('LIVE_LATE_AFTER_MINUTES', '10'))
if LIVE_ROOM_POLL_SECONDS <= 0 or LIVE_LATE_AFTER_MINUTES < 0:
    raise RuntimeError('Live polling must be positive and late threshold must not be negative')
