from django.core.management.base import BaseCommand
from django.db import transaction
from lms.models import Attempt
from lms.signals import question_evidence


class Command(BaseCommand):
    help='Idempotently reconcile derived question evidence after migration or an older-writer rollback; never changes answers or scores.'
    def handle(self,*args,**options):
        count=0
        for attempt in Attempt.objects.filter(submitted_at__isnull=False).iterator(chunk_size=100):
            with transaction.atomic():question_evidence(Attempt,attempt)
            count+=1
        self.stdout.write(f'Reconciled question evidence for {count} submitted attempts; original answers and scores preserved.')
