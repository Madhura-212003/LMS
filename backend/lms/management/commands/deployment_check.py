import os
import sys
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.db import connection
from django.core.cache import cache
from config.production import validate_environment


class Command(BaseCommand):
    help='Validate production configuration without printing secret values; optionally exercise services.'
    def add_arguments(self,parser):parser.add_argument('--live-services',action='store_true')
    def handle(self,*args,**options):
        errors=validate_environment(os.environ)
        if sys.version_info[:2]!=(3,13):errors.append('Release runtime must use Python 3.13')
        if errors:raise CommandError('\n'.join(errors))
        self.stdout.write('PASS production environment names, URL policies and runtime')
        if not options['live_services']:return
        if not settings.PRODUCTION:raise CommandError('Set LMS_ENV=production before live checks')
        if connection.vendor!='postgresql':raise CommandError('Production database must be PostgreSQL')
        with connection.cursor() as cursor:
            cursor.execute('SHOW server_version_num');version=int(cursor.fetchone()[0])
            if not 160000<=version<170000:raise CommandError('This release targets PostgreSQL 16')
        cache.set('lms-deployment-check','ok',30)
        if cache.get('lms-deployment-check')!='ok':raise CommandError('Redis cache did not round-trip')
        from lms.execution import execute
        if execute('print(2+3)','',language='Python').strip()!='5':raise CommandError('Execution output did not match')
        from lms.ai_service import generate
        if not generate('Reply with a short greeting.'):raise CommandError('General AI smoke test returned no text')
        if not generate('Summarise this lesson.','Water freezes at zero degrees Celsius under standard pressure.'):raise CommandError('Lesson AI smoke test returned no text')
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile
        import uuid
        key=default_storage.save('_health/'+uuid.uuid4().hex+'.txt',ContentFile(b'lms-storage-check'))
        try:
            with default_storage.open(key,'rb') as stream:
                if stream.read()!=b'lms-storage-check':raise CommandError('Blob storage round-trip failed')
        finally:default_storage.delete(key)
        self.stdout.write('PASS PostgreSQL 16, Redis, execution, General/Lesson AI and private blob storage')
