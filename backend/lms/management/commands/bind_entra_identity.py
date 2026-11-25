import uuid
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from lms.models import Profile,FederatedIdentity
from lms.services import audit
from lms.identity import ROLES


class Command(BaseCommand):
    help='Explicitly bind an existing migrated user to a directory object, preserving all learner work.'
    def add_arguments(self,p):
        p.add_argument('--user-id',type=int,required=True);p.add_argument('--object-id',required=True)
        p.add_argument('--role',choices=ROLES,required=True);p.add_argument('--confirm',action='store_true')
    @transaction.atomic
    def handle(self,*args,**o):
        if not o['confirm']:raise CommandError('Review user ID, directory object and role, then pass --confirm. This disables password login for this user.')
        if not settings.ENTRA_TENANT_ID:raise CommandError('Set the institution Entra tenant first')
        try:oid=str(uuid.UUID(o['object_id']))
        except ValueError:raise CommandError('Directory object ID must be a UUID')
        user=User.objects.select_for_update().get(pk=o['user_id'])
        existing=FederatedIdentity.objects.filter(directory_tenant=settings.ENTRA_TENANT_ID,subject=oid).first()
        if existing and existing.user_id!=user.id:raise CommandError('Directory object is already bound to another user')
        binding=FederatedIdentity.objects.filter(user=user).first()
        if binding and (binding.subject!=oid or binding.directory_tenant!=settings.ENTRA_TENANT_ID):raise CommandError('User is bound to a different directory object')
        FederatedIdentity.objects.get_or_create(user=user,defaults={'directory_tenant':settings.ENTRA_TENANT_ID,'subject':oid})
        p,_=Profile.objects.get_or_create(user=user);p.role=o['role'];p.roles=[o['role']];p.tenant=settings.INSTITUTION_ID;p.campus=settings.DEFAULT_CAMPUS;p.save()
        user.set_unusable_password();user.save()
        audit(user,'identity.migrated',user,{'role':o['role']})
        self.stdout.write(f'Bound user {user.id}; existing course and submission references retained')
