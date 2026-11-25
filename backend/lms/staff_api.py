from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from ninja import Router,Schema
from ninja.errors import HttpError
from .models import CourseStaffAssignment
from .listing import list_page
from .permissions import require,roles
from .services import course_access,scope,audit

router=Router()


@router.get('/directory')
@list_page
def directory(request):
    require(request.user,'staff_assign')
    users=User.objects.filter(is_active=True,profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus).exclude(profile__role='Learner')
    return [{'id':u.id,'name':u.first_name or u.username,'roles':sorted(roles(u))} for u in users.select_related('profile').order_by('first_name','id')]


class AssignmentIn(Schema):
    user_id:int
    active:bool=True


@router.get('/courses/{course_id}')
@list_page
def assigned(request,course_id:int):
    require(request.user,'staff_assign');course_access(request.user,course_id)
    return [{'id':r.id,'user_id':r.user_id,'name':r.user.first_name,'roles':sorted(roles(r.user)),'active':r.is_active} for r in CourseStaffAssignment.objects.filter(course_id=course_id).select_related('user__profile')]


@router.post('/courses/{course_id}')
@transaction.atomic
def assign(request,course_id:int,data:AssignmentIn):
    require(request.user,'staff_assign');course=course_access(request.user,course_id)
    user=get_object_or_404(User,pk=data.user_id,profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus)
    if data.active and (not user.is_active or not roles(user)&{'Teacher','Author','Reviewer','TA','Translator'}):raise HttpError(400,'Select active teaching, authoring, review, translation or assistant staff')
    row,_=CourseStaffAssignment.objects.update_or_create(course=course,user=user,defaults={'is_active':data.active,'granted_by':request.user})
    audit(request.user,'course.staff_assign' if data.active else 'course.staff_revoke',row,{'active':data.active,'roles':sorted(roles(user))})
    return {'id':row.id,'active':row.is_active}
