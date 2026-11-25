from .permissions import require as require_capability,permits
from .listing import list_page
"""Final SRS lifecycle and dashboard endpoints, sharing the module access rules."""
from datetime import datetime,timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router,Schema
from ninja.errors import HttpError
from pydantic import Field
from .models import *
from .services import learner_course_access,courses,course_access,require_role,audit,scope,progress
from .feature_api import BankIn

router=Router()


@router.post('/question-bank/{item_id}/edit')
@transaction.atomic
def question_edit(request,item_id:int,data:BankIn):
    require_capability(request.user,"assessment_write")
    row=get_object_or_404(Question,pk=item_id)
    require_role(request.user,'Admin','Teacher')
    course_access(request.user,row.quiz.course_id,True)
    quiz=Quiz.objects.select_for_update().get(pk=row.quiz_id)
    if data.quiz_id!=quiz.id:raise HttpError(400,'A question cannot move assessments; use Copy instead')
    if quiz.attempt_set.exists():raise HttpError(400,'This assessment has attempts; copy it into a new version before editing questions')
    from .assessment import validate_question
    validate_question(data)
    for k,v in data.model_dump(exclude={'quiz_id'}).items():setattr(row,k,v)
    row.save();audit(request.user,'question.edit',row)
    return {'id':row.id}


class ReviewIn(Schema):
    rating:int=Field(ge=1,le=5)
    body:str=Field(default='',max_length=4000)


@router.post('/courses/{item_id}/review')
@transaction.atomic
def course_review(request,item_id:int,data:ReviewIn):
    require_role(request.user,'Learner')
    c=learner_course_access(request.user,item_id)
    row,_=CourseReview.objects.update_or_create(course=c,user=request.user,defaults={**data.model_dump(),**scope(request.user)})
    audit(request.user,'course.review',row)
    return {'id':row.id,'rating':row.rating}


@router.get('/files/{item_id}/metadata')
def file_metadata(request,item_id:int):
    # Reuse exactly the download authorization, without opening or transferring file bytes.
    from .feature_api import get_file
    response=get_file(request,item_id)
    response.close()
    a=get_object_or_404(Attachment,pk=item_id,**scope(request.user))
    return {'id':a.id,'name':a.name,'mime':a.mime}


@router.get('/dashboard')
def dashboard(request):
    user=request.user
    allowed=courses(user)
    now=timezone.now()
    live=LiveClass.objects.filter(course__in=allowed,end_at__gt=now).exclude(status__in=['Cancelled','Ended','Draft'])
    if user.profile.role=='Learner':live=live.filter(cohort__enrolment__user=user,cohort__enrolment__status__in=['Enrolled','Completed'])
    due=Assignment.objects.filter(course__in=allowed,status='Published',due_at__gte=now)
    if user.profile.role=='Learner':due=due.exclude(submission__user=user)
    notifications=Notification.objects.filter(user=user,announcement__course__in=allowed,read_at=None)
    return {'upcoming':list(live.order_by('start_at').values('id','title','start_at','end_at','teacher__first_name')[:10]),
            'due':list(due.order_by('due_at').values('id','title','due_at')[:10]),
            'notifications':list(notifications.order_by('-id').values('id','announcement__title')[:5]),
            'insights':{'cohorts':Cohort.objects.filter(course__in=allowed).count(),
                        'learners':Enrolment.objects.filter(cohort__course__in=allowed,status__in=['Enrolled','Completed']).values('user_id').distinct().count(),
                        'pending_marking':Submission.objects.filter(assignment__course__in=allowed,status__in=['Submitted','Late','Re-evaluation requested']).count() if user.profile.role in ('Admin','Teacher','Coordinator') else 0}}


@router.get('/class-topics')
@list_page
def class_topics(request,cohort_id:int=0):
    require_role(request.user,'Admin','Teacher','Coordinator')
    qs=Attempt.objects.filter(quiz__course__in=courses(request.user),submitted_at__isnull=False).select_related('quiz')
    if cohort_id:
        cohort=get_object_or_404(Cohort,pk=cohort_id,course__in=courses(request.user))
        qs=qs.filter(quiz__course=cohort.course,user__enrolment__cohort=cohort,user__enrolment__status__in=['Enrolled','Completed']).distinct()
    from .assessment import correct
    topics={}
    for attempt in qs:
        for q in attempt.quiz.question_set.all():
            row=topics.setdefault((attempt.quiz.course_id,q.topic),{'course':attempt.quiz.course.title,'topic':q.topic,'responses':0,'correct':0})
            row['responses']+=1
            row['correct']+=int(correct(q,attempt.answers.get(str(q.id))))
    return [{**r,'accuracy':round(100*r['correct']/r['responses']),'status':'Strength' if 100*r['correct']/r['responses']>=settings.PERSONALISATION_REVIEW_BELOW_PERCENT else 'Needs practice'} for r in topics.values()]


@router.get('/translation-coverage')
def translation_coverage(request,language:str):
    lessons=Lesson.objects.filter(course__in=courses(request.user),status='Published')
    return [{'course':c.title,'total':lessons.filter(course=c).count(),'translated':lessons.filter(course=c,translation__language=language,translation__status='Translated').count()} for c in courses(request.user)]


@router.get('/teaching-courses')
@list_page
def teaching_courses(request):
    require_role(request.user,'Admin','Teacher','Coordinator','Seller')
    from .api import course_row
    return [course_row(c,request.user) for c in courses(request.user).order_by('title','id')]


@router.get('/skill-progress')
@list_page
def skill_progress(request):
    require_role(request.user,'Admin','Teacher','Coordinator')
    rows=[]
    for skill in DigitalSkill.objects.filter(course__in=courses(request.user)):
        for e in Enrolment.objects.filter(cohort__course=skill.course,status__in=['Enrolled','Completed']).select_related('cohort','user'):
            p=DigitalSkillProgress.objects.filter(skill=skill,user=e.user).first()
            count=len(p.completed_steps) if p else 0
            rows.append({'skill':skill.title,'learner':e.user.first_name,'cohort':e.cohort.name,'completed':count,'total':len(skill.steps),'status':'Completed' if count==len(skill.steps) and count else 'In progress' if count else 'Not started'})
    return rows


@router.get('/attempts/{item_id}')
def review_attempt(request,item_id:int):
    from .api import attempt_row
    a=get_object_or_404(Attempt,pk=item_id,quiz__course__in=courses(request.user))
    if not permits(request.user,'teaching_read') and a.user_id!=request.user.id:raise HttpError(403,'This attempt belongs to another learner')
    if a.submitted_at is None:raise HttpError(400,'Only submitted attempts can be reviewed here')
    return attempt_row(a)


class QuizSettings(Schema):
    title:str=Field(min_length=1,max_length=200)
    time_limit_min:int=Field(gt=0,le=360)
    max_attempts:int=Field(gt=0,le=100)
    correct_marks:float=Field(gt=0,allow_inf_nan=False)
    wrong_marks:float=Field(le=0,allow_inf_nan=False)
    status:str


@router.post('/quizzes/{item_id}/edit')
@transaction.atomic
def edit_quiz(request,item_id:int,data:QuizSettings):
    require_capability(request.user,"assessment_write")
    q=get_object_or_404(Quiz.objects.select_for_update(),pk=item_id)
    course_access(request.user,q.course_id,True)
    if data.status not in ('Draft','Published','Archived'):raise HttpError(400,'Choose Draft, Published or Archived')
    if not data.title.strip():raise HttpError(400,'Quiz title is required')
    if q.attempt_set.exists() and any(getattr(q,k)!=v for k,v in data.model_dump(exclude={'status'}).items()):raise HttpError(400,'This quiz has attempts; create a new version to change its questions or scoring')
    if data.status=='Published' and not q.question_set.exists():raise HttpError(400,'Add questions before publishing')
    if data.status!='Published' and q.attempt_set.filter(submitted_at=None).exists():raise HttpError(400,'Wait for active attempts to finish before closing this quiz')
    for k,v in data.model_dump().items():setattr(q,k,v)
    q.save();audit(request.user,'quiz.edit',q,{'status':q.status})
    return {'id':q.id,'status':q.status}


class AssignmentEdit(Schema):
    title:str=Field(min_length=1,max_length=200)
    instructions:str=Field(min_length=1,max_length=20000)
    due_at:datetime
    total_marks:int=Field(gt=0,le=10000)
    status:str
    attachments:list[int]=Field(default_factory=list,max_length=20)


@router.post('/assignments/{item_id}/edit')
@transaction.atomic
def edit_assignment(request,item_id:int,data:AssignmentEdit):
    require_capability(request.user,"assessment_write")
    a=get_object_or_404(Assignment.objects.select_for_update(),pk=item_id)
    course_access(request.user,a.course_id,True)
    if data.status not in ('Draft','Published','Archived'):raise HttpError(400,'Choose Draft, Published or Archived')
    if not data.title.strip() or not data.instructions.strip():raise HttpError(400,'Title and instructions are required')
    if timezone.is_naive(data.due_at):raise HttpError(400,'Due date requires a timezone')
    if a.submission_set.exists() and data.total_marks!=a.total_marks:raise HttpError(400,'Existing submissions retain their marking scale; create a new assignment to change total marks')
    from .api import validate_attachments
    validate_attachments(request.user,a.course_id,data.attachments)
    for k,v in data.model_dump().items():setattr(a,k,v)
    a.save();audit(request.user,'assignment.edit',a,{'status':a.status})
    return {'id':a.id,'status':a.status}


class LabMark(Schema):
    score:float=Field(ge=0,le=100,allow_inf_nan=False)
    feedback:str=Field(min_length=1,max_length=10000)


class AttendanceIn(Schema):
    status:str


@router.post('/live/{class_id}/attendance/{user_id}')
@transaction.atomic
def correct_attendance(request,class_id:int,user_id:int,data:AttendanceIn):
    require_capability(request.user,"classroom_manage")
    require_role(request.user,'Admin','Teacher','Coordinator','TA')
    live=get_object_or_404(LiveClass,pk=class_id,course__in=courses(request.user))
    if live.status=='Cancelled':raise HttpError(400,'Cancelled classes are not attendance obligations')
    if data.status not in ('Present','Absent','Late'):raise HttpError(400,'Choose Present, Absent or Late')
    get_object_or_404(Enrolment,cohort=live.cohort,user_id=user_id,status__in=['Enrolled','Completed'])
    row,new=Attendance.objects.get_or_create(live_class=live,user_id=user_id,defaults={'status':data.status,'left_at':timezone.now()})
    before=None if new else row.status
    row.status=data.status
    row.save();audit(request.user,'attendance.correct',row,{'before':before,'after':data.status})
    return {'status':row.status}


@router.post('/labs/{item_id}/review')
@transaction.atomic
def lab_mark(request,item_id:int,data:LabMark):
    require_capability(request.user,"mark")
    row=get_object_or_404(LabSession.objects.select_for_update(),pk=item_id)
    require_role(request.user,'Admin','Teacher','TA')
    course_access(request.user,row.lab.course_id,True)
    if row.status!='Completed':raise HttpError(400,'Only a completed lab can be marked')
    if not data.feedback.strip():raise HttpError(400,'Feedback is required')
    row.score,row.feedback=data.score,data.feedback;row.save()
    audit(request.user,'lab.mark',row,data.model_dump())
    return {'id':row.id,'score':row.score,'feedback':row.feedback}
