"""Production settings additions; no secrets or resource creation happens here."""
import os
from urllib.parse import urlparse


def validate_environment(env):
    required=['DJANGO_SECRET_KEY','DJANGO_ALLOWED_HOSTS','PUBLIC_APP_URL','POSTGRES_DB','POSTGRES_HOST','POSTGRES_USER','POSTGRES_PASSWORD','REDIS_URL','ENTRA_TENANT_ID','ENTRA_CLIENT_ID','ENTRA_CLIENT_SECRET','ENTRA_API_AUDIENCE','INSTITUTION_ID','AZURE_STORAGE_ACCOUNT_NAME','AZURE_STORAGE_CONTAINER','EXECUTION_SERVICE_URL','EXECUTION_SERVICE_TOKEN','AI_API_KEY','AI_MODEL','JITSI_BASE_URL','CLAMAV_HOST']
    errors=[f'{key} is required' for key in required if not env.get(key)]
    for key in ('AI_PROVIDER','JITSI_JWT_APP_ID','JITSI_JWT_SECRET'):
        if not env.get(key):errors.append(f'{key} is required')
    if env.get('AI_PROVIDER') and env['AI_PROVIDER']!='gemini':errors.append('This release uses the Gemini AI adapter')
    secret=env.get('DJANGO_SECRET_KEY','')
    if len(secret)<50 or secret.startswith('local-'):errors.append('DJANGO_SECRET_KEY must be a unique random secret of at least 50 characters')
    for key in ['PUBLIC_APP_URL','EXECUTION_SERVICE_URL','JITSI_BASE_URL']:
        value=env.get(key,'')
        if value and (urlparse(value).scheme!='https' or not urlparse(value).hostname):errors.append(f'{key} must be an absolute HTTPS URL')
    if env.get('JITSI_BASE_URL','').rstrip('/')=='https://meet.jit.si':errors.append('Configure your production Jitsi service; the public test deployment is not accepted')
    hosts=[h.strip() for h in env.get('DJANGO_ALLOWED_HOSTS','').split(',')]
    if '*' in hosts:errors.append('DJANGO_ALLOWED_HOSTS cannot contain a wildcard')
    if env.get('DJANGO_DEBUG','0')!='0':errors.append('DJANGO_DEBUG must be 0')
    if env.get('POSTGRES_SSLMODE','require') not in ('require','verify-ca','verify-full'):errors.append('PostgreSQL TLS must be enabled')
    return errors


def apply(namespace):
    errors=validate_environment(os.environ)
    if errors:raise RuntimeError('Production configuration is incomplete: '+'; '.join(errors))
    from datetime import timedelta
    from azure.identity import DefaultAzureCredential
    namespace.update(
        DEBUG=False,
        SESSION_COOKIE_SECURE=True,CSRF_COOKIE_SECURE=True,
        SESSION_COOKIE_AGE=3600,SESSION_COOKIE_NAME='__Host-lms_session',CSRF_COOKIE_NAME='__Host-lms_csrf',CSRF_COOKIE_HTTPONLY=True,
        SECURE_SSL_REDIRECT=True,SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,SECURE_HSTS_PRELOAD=True,
        SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https'),
        SECURE_CONTENT_TYPE_NOSNIFF=True,X_FRAME_OPTIONS='DENY',
        CSRF_TRUSTED_ORIGINS=[os.environ['PUBLIC_APP_URL'].rstrip('/')],
        SESSION_ENGINE='django.contrib.sessions.backends.cache',
        CACHES={'default':{'BACKEND':'django_redis.cache.RedisCache','LOCATION':os.environ['REDIS_URL'],'OPTIONS':{'CLIENT_CLASS':'django_redis.client.DefaultClient','SOCKET_CONNECT_TIMEOUT':5,'SOCKET_TIMEOUT':5,'IGNORE_EXCEPTIONS':False},'KEY_PREFIX':os.environ['INSTITUTION_ID']+':'+os.environ.get('DEFAULT_CAMPUS','main')}},
        STORAGES={'default':{'BACKEND':'storages.backends.azure_storage.AzureStorage','OPTIONS':{'account_name':os.environ['AZURE_STORAGE_ACCOUNT_NAME'],'azure_container':os.environ['AZURE_STORAGE_CONTAINER'],'token_credential':DefaultAzureCredential(),'expiration_secs':300,'overwrite_files':False,'timeout':30}},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    )
    namespace['DATABASES']['default']['CONN_MAX_AGE']=60
    namespace['DATABASES']['default']['CONN_HEALTH_CHECKS']=True
    namespace['DATABASES']['default']['OPTIONS']={'sslmode':os.environ.get('POSTGRES_SSLMODE','require'),'connect_timeout':10}
    namespace['AUTH_PASSWORD_VALIDATORS']=[{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator'},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},{'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'}]
