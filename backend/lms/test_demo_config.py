from unittest.mock import patch
from django.test import SimpleTestCase
from config.demo import validate_environment,apply


class DemoConfigurationTests(SimpleTestCase):
    def environment(self):
        return {'DJANGO_SECRET_KEY':'x'*64,'DJANGO_ALLOWED_HOSTS':'demo.onrender.com','PUBLIC_APP_URL':'https://frontend.example.org','DJANGO_DEBUG':'0','POSTGRES_DB':'demo','POSTGRES_HOST':'db.example.org','POSTGRES_USER':'demo','POSTGRES_PASSWORD':'test-only','LMS_MEDIA_ROOT':'/var/data/media'}

    def test_demo_requires_durable_database_hosts_secret_and_safe_origin(self):
        env=self.environment();self.assertEqual(validate_environment(env),[])
        for key,value in [('DJANGO_DEBUG','1'),('DJANGO_SECRET_KEY','short'),('DJANGO_ALLOWED_HOSTS','*'),('PUBLIC_APP_URL','http://public.example.org'),('PUBLIC_APP_URL','https://example.org/path'),('POSTGRES_HOST',''),('POSTGRES_SSLMODE','disable'),('LMS_MEDIA_ROOT','relative/media')]:
            with self.subTest(key=key,value=value):self.assertTrue(validate_environment({**env,key:value}))
        self.assertEqual(validate_environment({**env,'PUBLIC_APP_URL':'http://localhost:3000'}),[])

    def test_demo_keeps_secure_cookies_tls_database_and_password_login_separate_from_production(self):
        namespace={'PRODUCTION':False,'DATABASES':{'default':{'ENGINE':'django.db.backends.postgresql'}}}
        with patch.dict('os.environ',self.environment(),clear=True):apply(namespace)
        self.assertFalse(namespace['PRODUCTION']);self.assertFalse(namespace['DEBUG'])
        self.assertTrue(namespace['SESSION_COOKIE_SECURE']);self.assertTrue(namespace['SECURE_SSL_REDIRECT'])
        self.assertEqual(namespace['CSRF_TRUSTED_ORIGINS'],['https://frontend.example.org'])
        self.assertEqual(namespace['DATABASES']['default']['OPTIONS']['sslmode'],'require')
        self.assertEqual(str(namespace['MEDIA_ROOT']).replace('\\','/'),'/var/data/media')

    def test_incomplete_demo_fails_closed(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'Shared demo configuration is incomplete'):apply({})
