"""Entra authorization-code login for browsers and validated bearer access tokens."""
from functools import lru_cache
from django.conf import settings
from django.contrib.auth import login,logout
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponseRedirect,JsonResponse
from ninja.security import HttpBearer
from ninja.errors import HttpError
import jwt
import msal
from .models import Profile,FederatedIdentity

from .permissions import ROLES


def configured():return bool(settings.ENTRA_TENANT_ID and settings.ENTRA_CLIENT_ID and settings.ENTRA_CLIENT_SECRET)


def application():
    return msal.ConfidentialClientApplication(settings.ENTRA_CLIENT_ID,authority=settings.ENTRA_AUTHORITY,client_credential=settings.ENTRA_CLIENT_SECRET)


@transaction.atomic
def resolve_user(claims):
    if claims.get('tid')!=settings.ENTRA_TENANT_ID or not claims.get('oid'):
        raise HttpError(403,'Identity is not from the configured institution directory')
    assigned=claims.get('roles',[])
    if not isinstance(assigned,list) or any(not isinstance(r,str) for r in assigned):
        raise HttpError(403,'Identity roles must be a directory-issued list of app-role values')
    lms_roles=set(assigned)&set(ROLES)
    if 'Learner' in lms_roles and len(lms_roles)>1:
        raise HttpError(403,'Use separate learner and staff identities; ask IT to remove the conflicting app-role assignment')
    role=next((r for r in ROLES if r in assigned),None)
    if not role:raise HttpError(403,'Your identity has no LMS app role. Ask your institution administrator for access.')
    tid,oid=claims['tid'],claims['oid']
    identity=FederatedIdentity.objects.select_related('user').filter(directory_tenant=tid,subject=oid).first()
    if identity:user=identity.user
    else:
        # Never link by email: email is mutable and must not take over local users.
        user=User.objects.create(username='entra:'+tid+':'+oid)
        user.set_unusable_password()
        FederatedIdentity.objects.create(user=user,directory_tenant=tid,subject=oid)
    if not user.is_active:raise HttpError(403,'This account is inactive')
    user.email=str(claims.get('preferred_username',''))[:254]
    user.first_name=str(claims.get('name',''))[:150]
    user.save()
    profile,_=Profile.objects.get_or_create(user=user)
    profile.role,profile.roles,profile.tenant,profile.campus=role,[r for r in ROLES if r in assigned],settings.INSTITUTION_ID,settings.DEFAULT_CAMPUS
    profile.save()
    return user


def browser_start(request):
    if not configured():return JsonResponse({'detail':'Institution sign-in is not configured. Contact IT.'},status=503)
    flow=application().initiate_auth_code_flow(scopes=[],redirect_uri=settings.PUBLIC_APP_URL+'/api/lms/auth/entra/callback')
    request.session['entra_flow']=flow
    return HttpResponseRedirect(flow['auth_uri'])


def browser_callback(request):
    flow=request.session.pop('entra_flow',None)
    if not flow:return JsonResponse({'detail':'Sign-in state is missing or expired. Start sign-in again.'},status=400)
    try:
        result=application().acquire_token_by_auth_code_flow(flow,dict(request.GET.items()))
        claims=result.get('id_token_claims')
        if not claims:raise ValueError('Identity provider rejected the authorization code')
        user=resolve_user(claims)
    except (ValueError,HttpError):return JsonResponse({'detail':'Institution sign-in failed or no LMS app role was assigned. Start again or contact IT.'},status=403)
    login(request,user,backend='django.contrib.auth.backends.ModelBackend')
    from .services import audit
    audit(user,'auth.entra_login',user)
    return HttpResponseRedirect(settings.PUBLIC_APP_URL+'/lms/home')


@lru_cache(maxsize=8)
def key_client(url):return jwt.PyJWKClient(url,cache_keys=True,lifespan=300,timeout=5)


class EntraBearer(HttpBearer):
    def authenticate(self,request,token):
        if not settings.ENTRA_TENANT_ID:return None
        try:
            key=key_client(settings.ENTRA_JWKS_URL).get_signing_key_from_jwt(token)
            claims=jwt.decode(token,key.key,algorithms=['RS256'],audience=settings.ENTRA_API_AUDIENCE,issuer=settings.ENTRA_ISSUER,options={'require':['exp','iat','iss','aud','tid','oid']})
            user=resolve_user(claims)
        except (jwt.PyJWTError,ValueError,HttpError):return None
        request.user=user
        return user


def session_auth(request):
    if not request.user.is_authenticated:return None
    from .permissions import roles
    if not roles(request.user):return None
    if settings.PRODUCTION and not FederatedIdentity.objects.filter(user=request.user).exists():return None
    # Keep Ninja's session authenticator so unsafe cookie requests require CSRF.
    from ninja.security import django_auth
    return django_auth(request)
