"""HTTPS shared demo profile, separate from institutional production requirements."""
import os
from pathlib import Path,PurePosixPath
from urllib.parse import urlparse


def validate_environment(env):
    required=('DJANGO_SECRET_KEY','DJANGO_ALLOWED_HOSTS','PUBLIC_APP_URL','POSTGRES_DB','POSTGRES_HOST','POSTGRES_USER','POSTGRES_PASSWORD','LMS_MEDIA_ROOT')
    errors=[f'{key} is required for the shared demo' for key in required if not env.get(key)]
    secret=env.get('DJANGO_SECRET_KEY','')
    if len(secret)<50 or secret.startswith('local-'):errors.append('Use a unique DJANGO_SECRET_KEY of at least 50 characters')
    if env.get('DJANGO_DEBUG','0')!='0':errors.append('DJANGO_DEBUG must be 0 for the shared demo')
    hosts=[host.strip() for host in env.get('DJANGO_ALLOWED_HOSTS','').split(',')]
    if '*' in hosts:errors.append('Wildcard hosts are not permitted')
    origin=urlparse(env.get('PUBLIC_APP_URL',''))
    local=origin.hostname in ('localhost','127.0.0.1')
    if not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('','/') or origin.scheme not in (('http','https') if local else ('https',)):
        errors.append('PUBLIC_APP_URL must be a frontend origin using HTTPS, or localhost for local frontend testing')
    if env.get('POSTGRES_SSLMODE','require') not in ('require','verify-ca','verify-full'):errors.append('PostgreSQL TLS must remain enabled')
    root=env.get('LMS_MEDIA_ROOT','')
    if root and not (Path(root).is_absolute() or PurePosixPath(root).is_absolute()):errors.append('LMS_MEDIA_ROOT must be an absolute persistent storage path')
    return errors


def apply(namespace):
    errors=validate_environment(os.environ)
    if errors:raise RuntimeError('Shared demo configuration is incomplete: '+'; '.join(errors))
    namespace.update(DEBUG=False,SESSION_COOKIE_SECURE=True,CSRF_COOKIE_SECURE=True,
        SECURE_SSL_REDIRECT=True,SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https'),
        SECURE_CONTENT_TYPE_NOSNIFF=True,X_FRAME_OPTIONS='DENY',
        CSRF_TRUSTED_ORIGINS=[os.environ['PUBLIC_APP_URL'].rstrip('/')],
        MEDIA_ROOT=Path(os.environ['LMS_MEDIA_ROOT']))
    namespace['DATABASES']['default']['CONN_MAX_AGE']=60
    namespace['DATABASES']['default']['CONN_HEALTH_CHECKS']=True
    namespace['DATABASES']['default']['OPTIONS']={'sslmode':os.environ.get('POSTGRES_SSLMODE','require'),'connect_timeout':10}
