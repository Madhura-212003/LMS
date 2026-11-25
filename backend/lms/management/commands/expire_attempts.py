import time
from django.core.management.base import BaseCommand
from lms.models import Attempt
from lms.services import expired, finish_attempt


class Command(BaseCommand):
    help='Finalize expired quiz attempts. Use --watch for a local five-second worker.'
    def add_arguments(self,parser):parser.add_argument('--watch',action='store_true')
    def handle(self,*args,**options):
        while True:
            count=0
            for a in Attempt.objects.filter(submitted_at=None).select_related('user','quiz'):
                if expired(a):finish_attempt(a.user,a.id);count+=1
            if count:self.stdout.write(f'Finalized {count} expired attempts')
            if not options['watch']:break
            time.sleep(5)
