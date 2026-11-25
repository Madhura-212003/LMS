from .permissions import require as require_capability,roles as actor_roles,permits
from .listing import list_page
import json
import mimetypes
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Avg, Q
from django.forms.models import model_to_dict
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema, File, Form
from ninja.files import UploadedFile
from ninja.errors import HttpError
from pydantic import Field
from .models import *
from .services import learner_course_access, scope, courses, course_access, require_role, audit, progress, enrol
from .teaching_runner import run, RunnerError
from .execution import execute
from django.conf import settings

router = Router()
CATALOGUES = {'library': LibraryResource, 'live': LiveClass, 'lectures': Lecture, 'paths': LearningPath,
              'activities': Activity, 'coding': CodingProblem, 'labs': ProgrammingLab,
              'skills': DigitalSkill, 'practice': PracticePrompt, 'exams': ExamPack}
WRITERS = ('Admin','Teacher','Coordinator','Librarian','Translator','Seller')


def manage(user, course_id=None, roles=('Admin','Teacher','Coordinator')):
    require_role(user,*roles)
    if course_id:
        if user.profile.role=='Seller':
            get_object_or_404(Course,pk=course_id,owner=user,**scope(user),is_deleted=False)
        elif 'Librarian' in actor_roles(user) and 'Librarian' in roles:
            get_object_or_404(Course, pk=course_id, **scope(user), is_deleted=False)
        elif user.profile.role=='Translator':
            course_access(user,course_id)
        else:
            course_access(user,course_id,True)


def scoped(user, model):
    qs=model.objects.filter(**scope(user))
    roles=actor_roles(user)
    if roles.intersection({'Admin','Coordinator'}):return qs
    if model is LibraryResource and 'Librarian' in roles:return qs
    if not roles.intersection({'Teacher','Seller','Learner'}) and not ('TA' in roles and model in (LiveClass,Lecture)):return qs.none()
    return qs.filter(course__in=courses(user))


def accessible(user, model, pk, write=False):
    obj=get_object_or_404(scoped(user,model),pk=pk)
    if write:manage(user,obj.course_id)
    elif user.profile.role=='Learner' and hasattr(obj,'status') and obj.status not in ('Published','Scheduled','Live','Ended','Cancelled'):
        raise HttpError(403,'This item is not published')
    return obj


def serial(obj, exclude=()):
    d=model_to_dict(obj,exclude=exclude)
    for name in ('created_at','updated_at','submitted_at','started_at','completed_at','joined_at','awarded_at'):
        if hasattr(obj,name):
            value=getattr(obj,name)
            d[name]=value.isoformat() if value else None
    return json.loads(json.dumps(d,cls=DjangoJSONEncoder))


def attachment(user, pk, course_id):
    if not pk:return None
    a=get_object_or_404(Attachment,pk=pk,course_id=course_id,**scope(user))
    if a.owner_id!=user.id and not permits(user,'teaching_read'):
        library='Librarian' in actor_roles(user) and LibraryResource.objects.filter(attachment=a,**scope(user)).exists()
        source=any(a.id in l.attachments for l in Lesson.objects.filter(course_id=course_id))
        if not library and not source:raise HttpError(403,'Use an uploaded file you own or can already access')
    return a


def learner(user):
    require_role(user,'Learner')


def datetime_field(value,name):
    try:v=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except (TypeError,ValueError):raise HttpError(400,name+' must be a valid date and time')
    if timezone.is_naive(v):raise HttpError(400,name+' requires a timezone')
    return v


class ItemIn(Schema):
    course_id: int
    title: str = Field(min_length=1,max_length=200)
    description: str = Field(default='',max_length=60000)
    status: str = 'Published'
    subject: str = Field(default='General',max_length=100)
    language: str = Field(default='English',max_length=50)
    resource_type: str = Field(default='Article',max_length=40)
    body: str = Field(default='',max_length=60000)
    attachment_id: int | None = None
    captions_id: int | None = None
    topic: str = Field(default='General',max_length=100)
    difficulty: str = Field(default='Beginner',max_length=30)
    starter: str = Field(default='',max_length=12000)
    tests: list[dict] = Field(default_factory=list,max_length=50)
    steps: list = Field(default_factory=list,max_length=100)
    module: int = 172
    practice_type: str = Field(default='Writing',max_length=40)
    rubric: str = Field(default='',max_length=5000)
    level: str = Field(default='Practice',max_length=50)
    quiz_id: int | None = None
    cohort_id: int | None = None
    start_at: str = ''
    end_at: str = ''
    meeting_url: str = ''
    due_at: str = ''
    groups: list[str] = Field(default_factory=list,max_length=100)


def item_fields(user,kind,data):
    roles=('Admin','Librarian') if kind=='library' else ('Admin','Teacher','Coordinator') if kind=='live' else ('Admin','Teacher','TA','Coordinator') if kind=='lectures' else ('Admin','Teacher','Coordinator') if kind=='paths' else ('Admin','Teacher')
    manage(user,data.course_id,roles)
    if kind=='lectures':require_capability(user,'lecture_manage')
    if kind=='paths':require_capability(user,'path_manage')
    if not data.title.strip():raise HttpError(400,'Title cannot be blank')
    if kind!='live' and data.status not in ('Draft','Published'):raise HttpError(400,'Choose Draft or Published')
    base={'course_id':data.course_id,'title':data.title.strip(),'description':data.description,'status':data.status}
    if kind=='library':
        attachment(user,data.attachment_id,data.course_id)
        if not data.body.strip() and not data.attachment_id:raise HttpError(400,'Add resource text or upload a file')
        base.update(subject=data.subject,language=data.language,resource_type=data.resource_type,body=data.body,attachment_id=data.attachment_id)
    elif kind=='live':
        co=get_object_or_404(Cohort,pk=data.cohort_id,course_id=data.course_id,**scope(user))
        start,end=datetime_field(data.start_at,'Start'),datetime_field(data.end_at,'End')
        if start>=end:raise HttpError(400,'Class end must be after its start')
        if end<=timezone.now():raise HttpError(400,'Cannot schedule a class that has already ended')
        import os
        base_url=os.environ.get('JITSI_BASE_URL','https://meet.jit.si').rstrip('/')
        url=data.meeting_url or base_url+'/admiezo-'+uuid.uuid4().hex
        if urlparse(url).scheme!='https' or not urlparse(url).hostname:raise HttpError(400,'Meeting URL must use HTTPS')
        if settings.PRODUCTION and urlparse(url).hostname!=urlparse(base_url).hostname:raise HttpError(400,'Use the institution-configured live class provider')
        base.update(cohort=co,teacher=co.teacher,start_at=start,end_at=end,meeting_url=url,status='Scheduled')
    elif kind=='lectures':
        a=attachment(user,data.attachment_id,data.course_id)
        if not a or a.mime not in ('video/mp4','video/webm'):raise HttpError(400,'Upload a video file for this lecture')
        cap=attachment(user,data.captions_id,data.course_id)
        if cap and not cap.name.lower().endswith('.vtt'):raise HttpError(400,'Captions must be a WebVTT file')
        base.update(attachment=a,captions=cap,topic=data.topic)
    elif kind=='activities':
        if not data.description.strip():raise HttpError(400,'Activity prompt is required')
        base.update(due_at=datetime_field(data.due_at,'Due date'),groups=data.groups)
    elif kind=='coding':
        if not data.tests:raise HttpError(400,'At least one input/output test is required')
        if any(set(t)!={'input','output'} or not all(isinstance(v,str) and len(v)<=10000 for v in t.values()) for t in data.tests):raise HttpError(400,'Each test needs text input and output')
        if data.language not in ('English','Python','Python subset','JavaScript','Java','C++'):raise HttpError(400,'Unsupported execution language')
        base.update(topic=data.topic,difficulty=data.difficulty,language='Python' if data.language=='English' else data.language,starter=data.starter,tests=data.tests)
    elif kind=='labs':
        if not data.steps or any(not isinstance(x,str) or not x.strip() for x in data.steps):raise HttpError(400,'Add at least one lab instruction')
        if data.language not in ('English','Python','Python subset','JavaScript','Java','C++'):raise HttpError(400,'Unsupported execution language')
        base.update(subject=data.subject,difficulty=data.difficulty,steps=data.steps,starter=data.starter,language='Python' if data.language=='English' else data.language)
    elif kind=='skills':
        if not data.steps or any(not isinstance(x,str) or not x.strip() for x in data.steps):raise HttpError(400,'Add at least one skill step')
        base.update(steps=data.steps)
    elif kind=='practice':
        if data.module not in (172,176,177,178):raise HttpError(400,'Invalid practice module')
        if data.practice_type not in ('Writing','Speaking','Interview','GD','Resume','Portfolio','Mains'):raise HttpError(400,'Invalid practice type')
        base.update(module=data.module,practice_type=data.practice_type,rubric=data.rubric)
    elif kind=='exams':
        if data.module not in (173,174,175,176,177):raise HttpError(400,'Invalid exam module')
        quiz=get_object_or_404(Quiz,pk=data.quiz_id,course_id=data.course_id)
        if data.status=='Published' and quiz.status!='Published':raise HttpError(400,'Publish the linked assessment before publishing this exam pack')
        base.update(module=data.module,subject=data.subject,level=data.level,quiz=quiz)
    elif kind=='paths':
        from .path_workflow import validate_steps
        validate_steps(user,data.steps,published=data.status=='Published')
    return base


def path_steps(user,path):
    rows=[]
    for step in path.pathstep_set.order_by('position','id'):
        done=False
        if step.kind=='lesson':done=LessonCompletion.objects.filter(user=user,lesson_id=step.reference).exists()
        elif step.kind=='course':
            course=Course.objects.filter(pk=step.reference).first()
            total=Lesson.objects.filter(course=course,status='Published').count() if course else 0
            done=total>0 and LessonCompletion.objects.filter(user=user,lesson__course=course,lesson__status='Published').count()>=total
        elif step.kind=='quiz':done=Attempt.objects.filter(user=user,quiz_id=step.reference,status='Submitted',score__gt=0).exists()
        elif step.kind=='lab':done=LabSession.objects.filter(user=user,lab_id=step.reference,status='Completed').exists()
        target_course=step.reference if step.kind=='course' else path.course_id
        if step.kind in ('lesson','quiz','lab'):
            model={'lesson':Lesson,'quiz':Quiz,'lab':ProgrammingLab}[step.kind]
            target_course=model.objects.filter(pk=step.reference).values_list('course_id',flat=True).first() or path.course_id
        model={'lesson':Lesson,'quiz':Quiz,'lab':ProgrammingLab,'course':Course}[step.kind]
        target=model.objects.filter(pk=step.reference).first()
        available=target is not None and courses(user).filter(pk=target_course).exists() and (user.profile.role!='Learner' or target.status=='Published')
        rows.append({**serial(step),'completed':done,'course_id':target_course,'available':available,'unavailable_reason':'' if available else 'This activity is unpublished or requires enrolment in its course.'})
    for i,row in enumerate(rows):row['unlocked']=all(x['completed'] for x in rows[:i])
    return rows


def item_row(user,kind,obj):
    d=serial(obj,exclude=('tests',))
    d['course_title']=obj.course.title
    d['owner']=obj.course.owner.first_name
    d['course_id']=obj.course_id
    if kind=='library':
        loan=LibraryLoan.objects.filter(resource=obj,user=user).first()
        d.update(loan=serial(loan) if loan else None,loans=obj.libraryloan_set.exclude(status='Returned').count())
        d['readable']=user.profile.role!='Learner' or obj.status=='Published'
        if not d['readable']:
            d.update(body='',attachment=None,description='This resource is unavailable for reading. You can still return an active loan.')
    elif kind=='live':
        d.update(participants=obj.attendance_set.filter(left_at=None).count(),owner=obj.teacher.first_name)
        from .live_workflow import availability
        d.update(availability(user,obj))
    elif kind=='lectures':
        p=LectureProgress.objects.filter(lecture=obj,user=user).first();d['progress']=serial(p) if p else None
    elif kind=='paths':
        steps=path_steps(user,obj)
        d.update(steps=steps,started=PathProgress.objects.filter(path=obj,user=user).exists(),structure_locked=PathProgress.objects.filter(path=obj).exists(),completed_steps=sum(step['completed'] for step in steps),total_steps=len(steps))
    elif kind=='activities':d['posts']=obj.activitypost_set.count()
    elif kind=='coding':
        d['test_count']=len(obj.tests)
        if user.profile.role in ('Admin','Teacher','Coordinator'):d['tests']=obj.tests
    elif kind=='labs':
        p=LabSession.objects.filter(lab=obj,user=user).first();d['session']=serial(p) if p else None
    elif kind=='skills':
        p=DigitalSkillProgress.objects.filter(skill=obj,user=user).first();d['completed_steps']=p.completed_steps if p else []
    elif kind=='practice':d['submissions']=list(obj.practicesubmission_set.filter(user=user).order_by('-id').values('id','status','score','feedback','body','attachment_id')[:20])
    elif kind=='exams':d.update(quiz_id=obj.quiz_id,time_limit_min=obj.quiz.time_limit_min,correct_marks=obj.quiz.correct_marks,wrong_marks=obj.quiz.wrong_marks,attempts=list(Attempt.objects.filter(quiz=obj.quiz,user=user).values('id','score','status')))
    return d


@router.get('/catalogue/{kind}')
@list_page
def catalogue(request,kind:str,q:str='',status:str='',sort:str='title',page:int=1,module:int=0,subject:str='',topic:str='',difficulty:str='',language:str='',level:str='',resource_type:str='',teacher:str=''):
    model=CATALOGUES.get(kind)
    if not model:raise HttpError(404,'Unknown catalogue')
    qs=scoped(request.user,model).select_related('course','course__owner')
    if request.user.profile.role=='Learner':
        qs=qs.filter(cohort__enrolment__user=request.user,cohort__enrolment__status__in=['Enrolled','Completed']).exclude(status='Draft') if kind=='live' else qs.filter(status='Published')
    qs=qs.filter(Q(title__icontains=q)|Q(description__icontains=q)|Q(course__title__icontains=q))
    if status and kind=='live' and status in ('Scheduled','Live','Ended'):
        now=timezone.now()
        qs=qs.filter(status='Scheduled',start_at__gt=now) if status=='Scheduled' else qs.filter(status='Scheduled',start_at__lte=now,end_at__gt=now) if status=='Live' else qs.filter(Q(status='Ended')|Q(status='Scheduled',end_at__lte=now))
    elif status:qs=qs.filter(status=status)
    if module and kind in ('practice','exams'):qs=qs.filter(module=module)
    facets={field:list(qs.order_by(field).values_list(field,flat=True).distinct()) for field in ('subject','topic','difficulty','language','level','resource_type') if any(f.name==field for f in model._meta.fields)}
    for field,value in {'subject':subject,'topic':topic,'difficulty':difficulty,'language':language,'level':level,'resource_type':resource_type}.items():
        if value and field in facets:qs=qs.filter(**{field:value})
    if teacher:qs=qs.filter(course__owner__first_name__icontains=teacher)
    if sort not in ('title','-title','-updated_at'):raise HttpError(400,'Unknown sort order')
    page=max(1,page)
    return {'facets':facets,'total':qs.count(),'items':[item_row(request.user,kind,x) for x in qs.order_by(sort,'id')[(page-1)*20:page*20]]}


@router.post('/catalogue/{kind}')
@transaction.atomic
def create_item(request,kind:str,data:ItemIn):
    model=CATALOGUES.get(kind)
    if not model:raise HttpError(404,'Unknown catalogue')
    fields=item_fields(request.user,kind,data)
    obj=model.objects.create(**scope(request.user),**fields)
    if kind=='paths':
        for i,s in enumerate(data.steps):PathStep.objects.create(path=obj,kind=s['kind'],reference=s['reference'],title=s.get('title',s['kind']),position=i+1)
    audit(request.user,kind+'.create',obj)
    return item_row(request.user,kind,obj)


@router.post('/catalogue/{kind}/{item_id}/edit')
@transaction.atomic
def edit_item(request,kind:str,item_id:int,data:ItemIn):
    model=CATALOGUES.get(kind)
    if not model:raise HttpError(404,'Unknown catalogue')
    obj=get_object_or_404(model.objects.select_for_update() if kind=='paths' else model,pk=item_id,**scope(request.user))
    if obj.course_id!=data.course_id:raise HttpError(400,'An item cannot move to a different course')
    fields=item_fields(request.user,kind,data)
    if kind=='live' and obj.status in ('Cancelled','Ended'):raise HttpError(400,'This class is closed; schedule a new class instead')
    if kind=='live' and obj.end_at<=timezone.now():raise HttpError(400,'This class has ended; schedule a new class instead')
    if kind=='live' and obj.cohort_id!=fields['cohort'].id and obj.attendance_set.exists():raise HttpError(400,'A class with attendance cannot move to another cohort')
    if kind=='lectures' and obj.attachment_id!=fields['attachment'].id and obj.lectureprogress_set.exists():raise HttpError(400,'Learners have started this recording; create a new lecture to replace its video')
    if kind=='skills' and obj.steps!=data.steps and obj.digitalskillprogress_set.exists():raise HttpError(400,'Learners have started this track; create a new version before changing its steps')
    if kind=='labs' and obj.steps!=data.steps and obj.labsession_set.exists():raise HttpError(400,'Learners have started this lab; create a new version before changing its steps')
    for k,v in fields.items():setattr(obj,k,v)
    obj.save()
    if kind=='paths':
        current=list(obj.pathstep_set.order_by('position','id').values_list('kind','reference','title'))
        incoming=[(step['kind'],step['reference'],step.get('title',step['kind'])) for step in data.steps]
        if current!=incoming:
            if PathProgress.objects.filter(path=obj).exists():raise HttpError(400,'Learners have started this path; create a new path to change its steps')
            obj.pathstep_set.all().delete()
            for i,step in enumerate(data.steps):PathStep.objects.create(path=obj,kind=step['kind'],reference=step['reference'],title=step.get('title',step['kind']),position=i+1)
    audit(request.user,kind+'.edit',obj)
    return item_row(request.user,kind,obj)


class StateIn(Schema):
    status:str


@router.post('/catalogue/{kind}/{item_id}/status')
@transaction.atomic
def item_status(request,kind:str,item_id:int,data:StateIn):
    model=CATALOGUES.get(kind)
    if not model:raise HttpError(404,'Unknown catalogue')
    obj=get_object_or_404(model.objects.select_for_update() if kind=='paths' else model,pk=item_id,**scope(request.user))
    manage(request.user,obj.course_id,('Admin','Librarian') if kind=='library' else ('Admin','Teacher','Coordinator') if kind=='live' else ('Admin','Teacher','TA','Coordinator') if kind=='lectures' else ('Admin','Teacher','Coordinator') if kind=='paths' else ('Admin','Teacher'))
    if kind=='exams' and data.status=='Published' and obj.quiz.status!='Published':raise HttpError(400,'Publish the linked assessment first')
    if data.status not in (('Scheduled','Cancelled','Ended') if kind=='live' else ('Draft','Published','Archived')):raise HttpError(400,'Invalid status')
    if kind=='paths' and data.status=='Published':
        from .path_workflow import validate_steps
        validate_steps(request.user,list(obj.pathstep_set.values('kind','reference','title')),published=True)
    before=obj.status;obj.status=data.status;obj.save();audit(request.user,kind+'.status',obj,{'before':before,'after':data.status})
    return {'status':obj.status}


@router.post('/files')
def upload(request,course_id:Form[int],file:File[UploadedFile]):
    if 'Librarian' in actor_roles(request.user):
        get_object_or_404(Course,pk=course_id,**scope(request.user),is_deleted=False)
    else:course_access(request.user,course_id)
    if file.size>settings.MAX_UPLOAD_BYTES:raise HttpError(400,f'Files must be {settings.MAX_UPLOAD_BYTES//(1024*1024)} MB or smaller')
    from .scanning import scan_upload
    scan_upload(file)
    extension=Path(file.name).suffix.lower()
    allowed={'.pdf':'application/pdf','.txt':'text/plain','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.mp4':'video/mp4','.webm':'video/webm','.mp3':'audio/mpeg','.wav':'audio/wav','.vtt':'text/vtt','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    if extension not in allowed:raise HttpError(400,'Use PDF, text, images, Office files, MP4/WebM, MP3/WAV or VTT')
    a=Attachment(course_id=course_id,owner=request.user,name=Path(file.name).name,mime=allowed[extension],**scope(request.user))
    try:
        with transaction.atomic():
            a.file.save(uuid.uuid4().hex+extension,file,save=False);a.save();audit(request.user,'file.upload',a)
    except Exception:
        if a.file:a.file.delete(save=False)
        raise
    return {'id':a.id,'name':a.name,'mime':a.mime}


@router.get('/files/{file_id}')
def get_file(request,file_id:int):
    a=get_object_or_404(Attachment,pk=file_id,**scope(request.user))
    roles=actor_roles(request.user)
    public_cover=Course.objects.filter(cover=a,status='Published',is_deleted=False,**scope(request.user)).exists()
    library_context='Librarian' in roles and (a.owner_id==request.user.id or LibraryResource.objects.filter(attachment=a,**scope(request.user)).exists())
    if not public_cover and not library_context:
        course_access(request.user,a.course_id)
        if not roles.intersection({'Admin','Teacher','Coordinator','TA'}) and a.owner_id!=request.user.id:
            source_file=any(a.id in l.attachments for l in Lesson.objects.filter(course=a.course))
            if roles.intersection({'Author','Reviewer','Translator','Seller'}):
                if not source_file:raise HttpError(403,'This file is outside your assigned content work')
            else:
                published=(LibraryResource.objects.filter(attachment=a,status='Published').exists() or Lecture.objects.filter(Q(attachment=a)|Q(captions=a),status='Published').exists() or PreviousPaper.objects.filter(Q(attachment=a)|Q(solutions=a)).exists() or any(a.id in l.attachments for l in Lesson.objects.filter(course=a.course,status='Published')) or any(a.id in task.attachments for task in Assignment.objects.filter(course=a.course,status='Published')))
                if not published:raise HttpError(403,'This file is not available to you')
    if settings.PRODUCTION:
        from django.http import HttpResponseRedirect
        response=HttpResponseRedirect(a.file.storage.url(a.file.name))
        response['Cache-Control']='private, no-store'
        return response
    try:response=FileResponse(a.file.open('rb'),content_type=a.mime,filename=a.name,as_attachment=a.mime not in ('application/pdf','text/plain','text/vtt','video/mp4','video/webm','audio/mpeg','audio/wav','image/png','image/jpeg'))
    except (FileNotFoundError,OSError):raise HttpError(404,'File storage is unavailable. Ask the owner to upload again.')
    response['X-Content-Type-Options']='nosniff'
    response['Content-Security-Policy']="sandbox; default-src 'none'"
    return response


class ActionIn(Schema):
    action:str


@router.get('/library/resources/{item_id}')
def library_resource(request,item_id:int):
    return item_row(request.user,'library',accessible(request.user,LibraryResource,item_id))


@router.post('/library/{item_id}/loan')
@transaction.atomic
def library_loan(request,item_id:int,data:ActionIn):
    obj=get_object_or_404(scoped(request.user,LibraryResource),pk=item_id) if data.action=='Returned' else accessible(request.user,LibraryResource,item_id)
    if data.action not in ('Saved','Borrowed','Returned'):raise HttpError(400,'Unknown library action')
    LibraryResource.objects.select_for_update().get(pk=obj.pk)
    current=LibraryLoan.objects.select_for_update().filter(resource=obj,user=request.user).first()
    if current and (current.status==data.action or current.status=='Borrowed' and data.action=='Saved'):
        return serial(current)
    if data.action=='Returned' and (not current or current.status!='Borrowed'):
        raise HttpError(400,'There is no active loan to return')
    loan,_=LibraryLoan.objects.update_or_create(resource=obj,user=request.user,defaults={'status':data.action,'due_at':timezone.now()+timedelta(days=settings.LIBRARY_LOAN_DAYS) if data.action=='Borrowed' else None})
    audit(request.user,'library.'+data.action.lower(),loan)
    return serial(loan)


@router.get('/library/mine')
@list_page
def my_library(request):
    qs=LibraryLoan.objects.filter(user=request.user,resource__course__in=courses(request.user)).exclude(status='Returned')
    if request.user.profile.role=='Learner':qs=qs.filter(Q(resource__status='Published')|Q(status='Borrowed'))
    return [item_row(request.user,'library',x.resource) for x in qs.select_related('resource__course__owner')]


@router.get('/library/insights')
def library_insights(request):
    require_capability(request.user,'library_manage')
    qs=LibraryLoan.objects.filter(resource__tenant=request.user.profile.tenant,resource__campus=request.user.profile.campus)
    if request.GET.get('summary')=='1':return {'resources':LibraryResource.objects.filter(**scope(request.user)).count(),'published':LibraryResource.objects.filter(**scope(request.user),status='Published').count(),'saved':qs.filter(status='Saved').count(),'borrowed':qs.filter(status='Borrowed').count(),'overdue':qs.filter(status='Borrowed',due_at__lt=timezone.now()).count()}
    return {'borrowed':qs.filter(status='Borrowed').count(),'overdue':qs.filter(status='Borrowed',due_at__lt=timezone.now()).count(),'resources':list(LibraryResource.objects.filter(**scope(request.user)).annotate(usage=Count('libraryloan')).order_by('-usage').values('title','usage'))}


def live_access(user,pk):
    require_role(user,'Admin','Teacher','Coordinator','TA','Learner')
    obj=accessible(user,LiveClass,pk)
    if user.profile.role=='Learner' and not Enrolment.objects.filter(user=user,cohort=obj.cohort,status__in=['Enrolled','Completed']).exists():raise HttpError(403,'You are not enrolled in this class cohort')
    return obj


@router.get('/live/classes/{item_id}')
def live_class_detail(request,item_id:int):
    obj=live_access(request.user,item_id)
    row=Attendance.objects.filter(live_class=obj,user=request.user).first()
    return {**item_row(request.user,'live',obj),'attendance':serial(row) if row else None}


@router.post('/live/{item_id}/join')
@transaction.atomic
def join_live(request,item_id:int):
    obj=live_access(request.user,item_id)
    if settings.PRODUCTION:
        import os
        if urlparse(obj.meeting_url).hostname!=urlparse(os.environ['JITSI_BASE_URL']).hostname:raise HttpError(503,'This class uses an old meeting provider. Ask the coordinator to update its meeting link.')
    if obj.status in ('Cancelled','Ended'):raise HttpError(400,'This class is '+obj.status.lower())
    if timezone.now()<obj.start_at:raise HttpError(400,'This class has not started yet')
    if timezone.now()>=obj.end_at:raise HttpError(400,'This class has ended')
    row,new=Attendance.objects.get_or_create(live_class=obj,user=request.user,defaults={'status':'Late' if timezone.now()>obj.start_at+timedelta(minutes=settings.LIVE_LATE_AFTER_MINUTES) else 'Present'})
    row.left_at=None;row.hand_raised=False;row.save();audit(request.user,'class.join',row)
    meeting_url=obj.meeting_url
    import os
    if os.environ.get('JITSI_JWT_SECRET'):
        import jwt
        from urllib.parse import urlencode
        now=int(timezone.now().timestamp())
        token=jwt.encode({'aud':'jitsi','iss':os.environ['JITSI_JWT_APP_ID'],'sub':os.environ.get('JITSI_JWT_SUB',urlparse(meeting_url).hostname),'room':urlparse(meeting_url).path.strip('/'),'iat':now,'nbf':now-5,'exp':min(now+3600,int(obj.end_at.timestamp())),'context':{'user':{'id':str(request.user.id),'name':request.user.first_name,'moderator':permits(request.user,'classroom_manage')}}},os.environ['JITSI_JWT_SECRET'],algorithm='HS256')
        meeting_url+=('&' if '?' in meeting_url else '?')+urlencode({'jwt':token})
    return {'meeting_url':meeting_url,'attendance':serial(row)}


@router.get('/live/{item_id}/room')
def room(request,item_id:int):
    obj=live_access(request.user,item_id)
    if not Attendance.objects.filter(live_class=obj,user=request.user,left_at=None).exists():raise HttpError(403,'Join this classroom before reading its participants or discussion')
    rows=obj.attendance_set.all()
    from .live_workflow import availability
    return {'class_id':obj.id,'open':availability(request.user,obj)['can_join'],'participants':[{'id':a.id,'name':a.user.first_name,'raised':a.hand_raised,'status':a.status,'left':a.left_at is not None} for a in rows], 'messages':list(obj.roommessage_set.order_by('-id')[:100].values('id','body','user__first_name','created_at'))[::-1]}


class RoomIn(Schema):
    action:str
    body:str=Field(default='',max_length=2000)


@router.post('/live/{item_id}/room')
@transaction.atomic
def room_action(request,item_id:int,data:RoomIn):
    obj=live_access(request.user,item_id)
    a=get_object_or_404(Attendance,live_class=obj,user=request.user)
    if data.action!='leave' and a.left_at is not None:raise HttpError(403,'Join the classroom before taking part')
    if data.action=='leave':a.left_at=a.left_at or timezone.now();a.hand_raised=False;a.save()
    elif data.action=='hand':
        if obj.status in ('Cancelled','Ended') or timezone.now()>=obj.end_at:raise HttpError(400,'This classroom is closed')
        a.hand_raised=not a.hand_raised;a.save()
    elif data.action=='chat':
        if not data.body.strip():raise HttpError(400,'Enter a message')
        if obj.status in ('Cancelled','Ended') or timezone.now()>=obj.end_at:raise HttpError(400,'Class chat is closed')
        RoomMessage.objects.create(live_class=obj,user=request.user,body=data.body)
    else:raise HttpError(400,'Unknown room action')
    audit(request.user,'class.'+data.action,a)
    return {'message':'Class '+data.action+' updated'}


@router.get('/live/attendance/all')
@list_page
def attendance(request):
    if request.user.profile.role not in ('Admin','Teacher','Coordinator','TA','Learner'):return []
    qs=LiveClass.objects.filter(course__in=courses(request.user))
    rows=[]
    for c in qs:
        audience=Enrolment.objects.filter(cohort=c.cohort,status__in=['Enrolled','Completed'])
        if request.user.profile.role=='Learner':audience=audience.filter(user=request.user)
        for e in audience:
            a=Attendance.objects.filter(live_class=c,user=e.user).first()
            rows.append({'class_id':c.id,'user_id':e.user_id,'cohort':c.cohort.name,'class_title':c.title,'learner':e.user.first_name,'status':'Cancelled' if c.status=='Cancelled' else a.status if a else ('Absent' if timezone.now()>c.end_at else 'Not joined'),'joined_at':a.joined_at.isoformat() if a and a.status!='Absent' else None})
    return rows


@router.get('/lectures/resources/{item_id}')
def lecture_resource(request,item_id:int):
    return item_row(request.user,'lectures',accessible(request.user,Lecture,item_id))


class LectureIn(Schema):
    position:float=Field(default=0,ge=0,le=86400)
    completed:bool=False
    notes:str|None=Field(default=None,max_length=20000)


@router.post('/lectures/{item_id}/progress')
@transaction.atomic
def lecture_progress(request,item_id:int,data:LectureIn):
    learner(request.user)
    obj=accessible(request.user,Lecture,item_id)
    Lecture.objects.select_for_update().get(pk=obj.pk)
    old=LectureProgress.objects.select_for_update().filter(lecture=obj,user=request.user).first()
    values=data.dict(exclude_none=True);values['completed']=data.completed or bool(old and old.completed)
    row,_=LectureProgress.objects.update_or_create(lecture=obj,user=request.user,defaults=values)
    audit(request.user,'lecture.progress',row)
    return serial(row)


@router.get('/paths/options')
@list_page
def path_options(request,kind:str='lesson'):
    from .path_workflow import STEP_MODELS
    require_capability(request.user,'path_manage')
    model=STEP_MODELS.get(kind)
    if not model:raise HttpError(400,'Choose a supported activity kind')
    qs=courses(request.user) if model is Course else model.objects.filter(course__in=courses(request.user))
    return [{'id':obj.id,'title':obj.title,'kind':kind,'status':obj.status} for obj in qs.order_by('title','id')]


@router.get('/paths/resources/{item_id}')
def path_resource(request,item_id:int):
    return item_row(request.user,'paths',accessible(request.user,LearningPath,item_id))


@router.post('/paths/{item_id}/steps/{step_id}/open')
def path_open_step(request,item_id:int,step_id:int):
    learner(request.user)
    path=accessible(request.user,LearningPath,item_id)
    if not PathProgress.objects.filter(path=path,user=request.user).exists():raise HttpError(400,'Start this path before opening its steps')
    step=next((row for row in path_steps(request.user,path) if row['id']==step_id),None)
    if not step:raise HttpError(404,'Step not found in this path')
    if not step['unlocked']:raise HttpError(403,'Complete the earlier path steps first')
    if not step['available']:raise HttpError(403,step['unavailable_reason'])
    return {**step,'path_id':path.id}


@router.get('/labs/resources/{item_id}')
def lab_resource(request,item_id:int):
    return item_row(request.user,'labs',accessible(request.user,ProgrammingLab,item_id))


@router.post('/paths/{item_id}/start')
@transaction.atomic
def path_start(request,item_id:int):
    learner(request.user);obj=accessible(request.user,LearningPath,item_id)
    learner_course_access(request.user,obj.course_id)
    obj=LearningPath.objects.select_for_update().get(pk=obj.pk)
    if obj.status!='Published':raise HttpError(400,'This path is not published')
    row,created=PathProgress.objects.get_or_create(path=obj,user=request.user)
    if created:audit(request.user,'path.start',row)
    return item_row(request.user,'paths',obj)


class PreferenceIn(Schema):
    goals:str|None=Field(default=None,max_length=4000)
    pace:str|None=None
    language:str|None=Field(default=None,min_length=1,max_length=50)
    notifications:bool|None=None
    ui_language:str|None=None


@router.get('/preferences')
def preferences(request):
    row=Preference.objects.filter(user=request.user).first()
    if row:return serial(row)
    from .personalisation_workflow import preference_values
    return preference_values(request.user)


@router.post('/preferences')
@transaction.atomic
def save_preferences(request,data:PreferenceIn):
    from .personalisation_workflow import UI_LANGUAGES,PACES
    changes=data.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):raise HttpError(400,'Preference values cannot be null')
    if 'ui_language' in changes and changes['ui_language'] not in UI_LANGUAGES:raise HttpError(400,'Choose a supported interface language')
    if 'pace' in changes and changes['pace'] not in PACES:raise HttpError(400,'Choose a supported pace')
    if 'language' in changes and not changes['language'].strip():raise HttpError(400,'Content language cannot be blank')
    User.objects.select_for_update().get(pk=request.user.pk)
    obj,_=Preference.objects.update_or_create(user=request.user,defaults=changes)
    audit(request.user,'preferences.save',obj)
    return serial(obj)


@router.get('/recommendations')
def recommendations(request):
    learner(request.user)
    from .personalisation_workflow import next_steps
    return next_steps(request.user)['items']


@router.get('/personalisation/next')
def personalisation_next(request):
    learner(request.user)
    from .personalisation_workflow import next_steps
    return next_steps(request.user)


@router.get('/activities/resources/{item_id}')
def activity_resource(request,item_id:int):
    return item_row(request.user,'activities',accessible(request.user,Activity,item_id))


@router.get('/insights/{kind}')
def insights(request,kind:str,module:int=0):
    require_role(request.user,'Admin','Teacher','Coordinator')
    allowed=courses(request.user)
    if kind=='lessons':
        return [{'title':c.title,'learners':Enrolment.objects.filter(cohort__course=c,status__in=['Enrolled','Completed']).values('user_id').distinct().count(),'completed_lessons':LessonCompletion.objects.filter(lesson__course=c,lesson__status='Published',user_id__in=Enrolment.objects.filter(cohort__course=c,status__in=['Enrolled','Completed']).values('user_id')).count(),'lessons':Lesson.objects.filter(course=c,status='Published').count()} for c in allowed]
    if kind=='practice':
        qs=PracticeSubmission.objects.filter(prompt__course__in=allowed)
        if module:qs=qs.filter(prompt__module=module)
        return list(qs.values('prompt__title').annotate(submissions=Count('id'),average=Avg('score')))
    if kind=='exams':
        packs=ExamPack.objects.filter(course__in=allowed,module=module)
        rows=[]
        for p in packs:
            attempts=Attempt.objects.filter(quiz=p.quiz,submitted_at__isnull=False)
            weak={};topics={}
            for q in p.quiz.question_set.all():
                from .assessment import correct
                wrong=sum(not correct(q,a.answers.get(str(q.id))) for a in attempts)
                weak[q.prompt]=wrong
                topics[q.topic]=topics.get(q.topic,0)+wrong
            rows.append({'title':p.title,'subject':p.subject,'attempts':attempts.count(),'average':attempts.aggregate(v=Avg('score'))['v'],'weak_questions':weak,'weak_topics':topics})
        return rows
    if kind=='skills':return [{'title':s.title,'learners':s.digitalskillprogress_set.count(),'completed_steps':sum(len(p.completed_steps) for p in s.digitalskillprogress_set.all()),'steps':len(s.steps)} for s in DigitalSkill.objects.filter(course__in=allowed)]
    if kind=='paths':
        rows=[]
        for path in LearningPath.objects.filter(course__in=allowed):
            learners=[]
            for e in Enrolment.objects.filter(cohort__course=path.course,status__in=['Enrolled','Completed']).select_related('user','cohort'):
                steps=path_steps(e.user,path)
                learners.append({'name':e.user.first_name,'cohort':e.cohort.name,'completed':sum(s['completed'] for s in steps),'total':len(steps),'steps':' · '.join(str(i+1)+': '+('Completed' if s['completed'] else 'Pending') for i,s in enumerate(steps)),'status':'Started' if PathProgress.objects.filter(path=path,user=e.user).exists() else 'Not started'})
            rows.append({'title':path.title,'learners':learners})
        return rows
    raise HttpError(404,'Unknown insight group')


class TranslationIn(Schema):
    lesson_id:int
    language:str=Field(min_length=1,max_length=50)
    body:str=Field(min_length=1,max_length=60000)
    source_updated_at:str|None=None
    translation_updated_at:str|None=None


@router.get('/translations')
@list_page
def translations(request,language:str=''):
    lessons=Lesson.objects.filter(course__in=courses(request.user))
    if request.user.profile.role=='Learner':lessons=lessons.filter(status='Published')
    lang=language or preferences(request)['language']
    return [{'id':l.id,'title':l.title,'course_id':l.course_id,'course':l.course.title,'original':l.body,'source_updated_at':l.updated_at.isoformat(),'language':lang,'translation':serial(t) if (t:=Translation.objects.filter(lesson=l,language=lang).first()) and (t.status=='Translated' or request.user.profile.role!='Learner') else None} for l in lessons]


@router.post('/translations')
@transaction.atomic
def translate(request,data:TranslationIn):
    require_capability(request.user,'translate')
    l=get_object_or_404(Lesson.objects.select_for_update(),pk=data.lesson_id);course_access(request.user,l.course_id)
    if data.source_updated_at and data.source_updated_at!=l.updated_at.isoformat():raise HttpError(400,'The source lesson changed. Refresh and review the current source before submitting.')
    existing=Translation.objects.filter(lesson=l,language=data.language.strip()).first()
    if data.translation_updated_at is not None and data.translation_updated_at!=(existing.updated_at.isoformat() if existing else ''):raise HttpError(400,'Another translation was saved. Refresh before editing it.')
    if not data.language.strip() or not data.body.strip():raise HttpError(400,'Language and translation cannot be blank')
    t,_=Translation.objects.update_or_create(lesson=l,language=data.language.strip(),defaults={'body':data.body,'translator':request.user,'status':'In translation',**scope(request.user)})
    audit(request.user,'translation.submit',t);return serial(t)


@router.post('/translations/{item_id}/approve')
@transaction.atomic
def approve_translation(request,item_id:int,updated_at:str=''):
    require_capability(request.user,'translation_review')
    candidate=get_object_or_404(Translation,pk=item_id,**scope(request.user))
    course_access(request.user,candidate.lesson.course_id)
    Lesson.objects.select_for_update().get(pk=candidate.lesson_id)
    t=Translation.objects.select_for_update().get(pk=candidate.pk)
    if updated_at and updated_at!=t.updated_at.isoformat():raise HttpError(400,'The translation changed. Refresh and review its current text.')
    if not t.body.strip():raise HttpError(400,'A blank translation cannot be approved')
    t.status='Translated';t.save();audit(request.user,'translation.approve',t);return serial(t)


class GlossaryIn(Schema):
    term:str=Field(min_length=1,max_length=200)
    definition:str=Field(min_length=1,max_length=4000)
    language:str=Field(min_length=1,max_length=50)


@router.get('/glossary')
@list_page
def glossary(request,language:str=''):
    qs=GlossaryTerm.objects.filter(**scope(request.user))
    if language:qs=qs.filter(language=language)
    return list(qs.values())


@router.post('/glossary')
@transaction.atomic
def add_glossary(request,data:GlossaryIn):
    require_capability(request.user,'glossary_manage')
    values={key:value.strip() for key,value in data.model_dump().items()}
    if not all(values.values()):raise HttpError(400,'Term, definition and language are required')
    obj=GlossaryTerm.objects.create(**scope(request.user),**values);audit(request.user,'glossary.create',obj);return serial(obj)


class PostIn(Schema):
    body:str=Field(min_length=1,max_length=10000)
    parent_id:int|None=None
    group_id:int|None=None


def check_group(user,activity,group_id):
    if not group_id:return None
    group=get_object_or_404(ActivityGroup,pk=group_id,activity=activity)
    if user.profile.role=='Learner' and not group.members.filter(pk=user.id).exists():raise HttpError(403,'You are not assigned to this study group')
    return group


class GroupIn(Schema):
    name:str=Field(min_length=1,max_length=100)
    user_ids:list[int]=Field(min_length=1,max_length=1000)


@router.get('/activities/{item_id}/groups')
def activity_groups(request,item_id:int):
    obj=accessible(request.user,Activity,item_id)
    qs=ActivityGroup.objects.filter(activity=obj)
    if request.user.profile.role=='Learner':qs=qs.filter(members=request.user)
    return [{'id':g.id,'name':g.name,'members':list(g.members.values('id','first_name'))} for g in qs]


@router.post('/activities/{item_id}/groups')
@transaction.atomic
def save_group(request,item_id:int,data:GroupIn):
    obj=accessible(request.user,Activity,item_id,True)
    allowed=set(Enrolment.objects.filter(cohort__course=obj.course,status__in=['Enrolled','Completed']).values_list('user_id',flat=True))
    if not set(data.user_ids)<=allowed:raise HttpError(400,'All group members must be enrolled in this course')
    group,_=ActivityGroup.objects.get_or_create(activity=obj,name=data.name.strip())
    group.members.set(data.user_ids)
    audit(request.user,'activity.group',group,{'members':data.user_ids})
    return {'id':group.id,'name':group.name}


@router.get('/activities/{item_id}/posts')
def activity_posts(request,item_id:int,group_id:int=0):
    obj=accessible(request.user,Activity,item_id)
    group=check_group(request.user,obj,group_id)
    return [{'id':p.id,'body':p.body,'parent_id':p.parent_id,'author':p.user.first_name,'created_at':p.created_at.isoformat(),'reactions':p.reactions.count(),'reacted':p.reactions.filter(pk=request.user.id).exists()} for p in obj.activitypost_set.filter(group=group).select_related('user').order_by('id')]


@router.post('/activities/{item_id}/posts')
@transaction.atomic
def add_post(request,item_id:int,data:PostIn):
    obj=accessible(request.user,Activity,item_id)
    if timezone.now()>obj.due_at or obj.status!='Published':raise HttpError(400,'This discussion is closed')
    group=check_group(request.user,obj,data.group_id)
    if data.parent_id:get_object_or_404(ActivityPost,pk=data.parent_id,activity=obj,group=group)
    p=ActivityPost.objects.create(activity=obj,user=request.user,body=data.body,parent_id=data.parent_id,group=group);audit(request.user,'activity.post',p);return {'id':p.id}


@router.post('/activities/posts/{post_id}/react')
@transaction.atomic
def react(request,post_id:int):
    p=get_object_or_404(ActivityPost,pk=post_id);accessible(request.user,Activity,p.activity_id)
    check_group(request.user,p.activity,p.group_id)
    if p.reactions.filter(pk=request.user.id).exists():p.reactions.remove(request.user)
    else:p.reactions.add(request.user)
    audit(request.user,'activity.react',p);return {'reactions':p.reactions.count()}


@router.get('/activities/participation/all')
@list_page
def participation(request):
    require_role(request.user,'Admin','Teacher','Coordinator')
    rows=[]
    for activity in Activity.objects.filter(course__in=courses(request.user)):
        users=User.objects.filter(enrolment__cohort__course=activity.course,enrolment__status__in=['Enrolled','Completed']).distinct()
        for user in users:
            posts=activity.activitypost_set.filter(user=user)
            rows.append({'activity__title':activity.title,'user__first_name':user.first_name,'posts':posts.count(),'replies':posts.filter(parent__isnull=False).count(),'reactions':ActivityPost.objects.filter(activity=activity,reactions=user).count()})
    return rows


class CodeIn(Schema):
    code:str=Field(min_length=1,max_length=12000)
    inputs:str=Field(default='',max_length=10000)


@router.post('/coding/{item_id}/run')
def code_run(request,item_id:int,data:CodeIn):
    obj=accessible(request.user,CodingProblem,item_id)
    try:return {'output':execute(data.code,data.inputs,obj.language),'engine':'Isolated execution service' if __import__('os').environ.get('EXECUTION_SERVICE_URL') else 'Bounded Python teaching interpreter'}
    except RunnerError as e:raise HttpError(400,str(e))


@router.post('/coding/{item_id}/submit')
@transaction.atomic
def code_submit(request,item_id:int,data:CodeIn):
    learner(request.user);obj=accessible(request.user,CodingProblem,item_id)
    learner_course_access(request.user,obj.course_id)
    import time
    started=time.monotonic()
    results=[]
    for i,test in enumerate(obj.tests):
        if time.monotonic()-started>120:raise HttpError(503,'The test suite exceeded its execution budget. Your code is preserved; ask your teacher to reduce the test workload.')
        try:
            output=execute(data.code,test['input'],obj.language);results.append({'test':i+1,'passed':output.strip()==test['output'].strip(),'output':output})
        except RunnerError as e:results.append({'test':i+1,'passed':False,'error':str(e)})
    score=round(100*sum(r['passed'] for r in results)/len(results)) if results else 0
    row=CodingAttempt.objects.create(problem=obj,user=request.user,code=data.code,result={'tests':results},score=score);audit(request.user,'coding.submit',row,{'score':score});return serial(row)


@router.get('/work/{kind}')
@list_page
def submitted_work(request,kind:str,module:int=0):
    if request.user.profile.role not in ('Admin','Teacher','Coordinator','TA','Learner'):return []
    mapping={'coding':(CodingAttempt,'problem'),'labs':(LabSession,'lab'),'practice':(PracticeSubmission,'prompt')}
    if kind not in mapping:raise HttpError(404,'Unknown work type')
    model,related=mapping[kind]
    qs=model.objects.filter(**{related+'__course__in':courses(request.user)})
    if request.user.profile.role=='Learner':qs=qs.filter(user=request.user)
    if module and kind=='practice':qs=qs.filter(prompt__module=module)
    return [{**serial(x),'learner':x.user.first_name,'title':getattr(x,related).title,'course_id':getattr(x,related).course_id} for x in qs.select_related('user',related).order_by('-id')]


class LabIn(Schema):
    observations:dict[str,str]=Field(default_factory=dict)
    code:str=Field(default='',max_length=12000)
    inputs:str=Field(default='',max_length=10000)
    complete:bool=False


@router.post('/labs/{item_id}/session')
@transaction.atomic
def lab_session(request,item_id:int,data:LabIn):
    learner(request.user);obj=accessible(request.user,ProgrammingLab,item_id)
    learner_course_access(request.user,obj.course_id)
    if any(k not in [str(i) for i in range(len(obj.steps))] or len(v)>5000 for k,v in data.observations.items()):raise HttpError(400,'Invalid lab observation')
    if data.complete and any(not data.observations.get(str(i),'').strip() for i in range(len(obj.steps))):raise HttpError(400,'Complete an observation for every lab step')
    old=LabSession.objects.select_for_update().filter(lab=obj,user=request.user).first()
    if old and old.status=='Completed':raise HttpError(400,'This lab is completed; its submitted notebook is read-only')
    if data.complete and not data.code.strip():raise HttpError(400,'Run an experiment before completing this programming lab')
    output=''
    if data.code:
        try:output=execute(data.code,data.inputs,obj.language)
        except RunnerError as e:raise HttpError(400,str(e))
    row,_=LabSession.objects.update_or_create(lab=obj,user=request.user,defaults={'observations':data.observations,'code':data.code,'inputs':data.inputs,'output':output,'status':'Completed' if data.complete else 'In progress','completed_at':timezone.now() if data.complete else None})
    audit(request.user,'lab.submit' if data.complete else 'lab.save',row);return serial(row)


class SkillIn(Schema):
    step:int=Field(ge=0)


@router.post('/skills/{item_id}/complete')
@transaction.atomic
def skill_complete(request,item_id:int,data:SkillIn):
    learner(request.user);obj=accessible(request.user,DigitalSkill,item_id)
    learner_course_access(request.user,obj.course_id)
    if data.step>=len(obj.steps):raise HttpError(400,'Unknown skill step')
    row,_=DigitalSkillProgress.objects.get_or_create(skill=obj,user=request.user)
    row=DigitalSkillProgress.objects.select_for_update().get(pk=row.pk)
    if any(i not in row.completed_steps for i in range(data.step)):raise HttpError(400,'Complete earlier steps first')
    row.completed_steps=sorted(set(row.completed_steps+[data.step]));row.save();audit(request.user,'skill.complete',row);return serial(row)


class PracticeIn(Schema):
    body:str=Field(default='',max_length=50000)
    attachment_id:int|None=None


@router.post('/practice/{item_id}/submit')
@transaction.atomic
def practice_submit(request,item_id:int,data:PracticeIn):
    learner(request.user);obj=accessible(request.user,PracticePrompt,item_id)
    learner_course_access(request.user,obj.course_id)
    a=attachment(request.user,data.attachment_id,obj.course_id)
    if a and a.owner_id!=request.user.id:raise HttpError(403,'Use your own uploaded file')
    if not data.body.strip() and not a:raise HttpError(400,'Write a response or attach a recording/document')
    row=PracticeSubmission.objects.create(prompt=obj,user=request.user,body=data.body,attachment=a);audit(request.user,'practice.submit',row);return serial(row)


class FeedbackIn(Schema):
    score:float=Field(ge=0,le=100)
    feedback:str=Field(min_length=1,max_length=10000)


@router.post('/practice/submissions/{item_id}/review')
@transaction.atomic
def practice_review(request,item_id:int,data:FeedbackIn):
    require_capability(request.user,"mark")
    row=get_object_or_404(PracticeSubmission,pk=item_id);manage(request.user,row.prompt.course_id,('Admin','Teacher','TA'))
    row.score=data.score;row.feedback=data.feedback;row.status='Reviewed';row.save();audit(request.user,'practice.review',row,data.dict());return serial(row)


@router.get('/papers')
@list_page
def papers(request,module:int):
    return [serial(p) for p in PreviousPaper.objects.filter(module=module,attachment__course__in=courses(request.user),**scope(request.user))]


class PaperIn(Schema):
    module:int
    title:str=Field(min_length=1,max_length=200)
    year:int=Field(ge=1950,le=2100)
    course_id:int
    attachment_id:int
    solutions_id:int|None=None


@router.post('/papers')
@transaction.atomic
def add_paper(request,data:PaperIn):
    manage(request.user,data.course_id)
    if data.module not in (173,174,175,176,177):raise HttpError(400,'Unknown exam type')
    a=attachment(request.user,data.attachment_id,data.course_id);sol=attachment(request.user,data.solutions_id,data.course_id)
    p=PreviousPaper.objects.create(**scope(request.user),module=data.module,title=data.title,year=data.year,attachment=a,solutions=sol);audit(request.user,'paper.create',p);return serial(p)


class ListingIn(Schema):
    course_id:int
    price:Decimal=Field(ge=0,max_digits=10,decimal_places=2)


@router.get('/marketplace')
@list_page
def marketplace(request,q:str='',free:bool=False):
    qs=MarketplaceListing.objects.filter(**scope(request.user),status='Published',course__status='Published',course__is_deleted=False,course__title__icontains=q)
    if free:qs=qs.filter(price=0)
    return [{'id':l.id,'course_id':l.course_id,'title':l.course.title,'description':l.course.description,'syllabus':l.course.modules,'teacher':l.course.owner.first_name,'seller':l.seller.first_name,'price':str(l.price),'duration_minutes':l.course.duration_minutes,'rating':l.course.coursereview_set.aggregate(v=Avg('rating'))['v'],'reviews':[{'learner':x.user.first_name,'rating':x.rating,'body':x.body,'updated_at':x.updated_at.isoformat()} for x in l.course.coursereview_set.select_related('user').order_by('-updated_at')[:50]],'status':l.status,'owner':l.seller.first_name,'updated_at':l.updated_at.isoformat(),'enrolled':courses(request.user).filter(pk=l.course_id).exists(),'purchased':MarketplacePurchase.objects.filter(listing=l,user=request.user).exists()} for l in qs.select_related('course','seller','course__owner').order_by('course__title')]


@router.post('/marketplace/listings')
@transaction.atomic
def listing(request,data:ListingIn):
    manage(request.user,data.course_id,('Admin','Teacher','Seller'))
    obj,created=MarketplaceListing.objects.get_or_create(course_id=data.course_id,defaults={'seller':request.user,'price':data.price,**scope(request.user)})
    if not created:
        if obj.seller_id!=request.user.id and request.user.profile.role!='Admin':raise HttpError(403,'This listing belongs to another seller')
        obj.price=data.price;obj.save()
    audit(request.user,'marketplace.save',obj);return serial(obj)


@router.post('/marketplace/{item_id}/enrol')
@transaction.atomic
def marketplace_enrol(request,item_id:int):
    learner(request.user)
    obj=get_object_or_404(MarketplaceListing,pk=item_id,status='Published',course__status='Published',**scope(request.user))
    co=Cohort.objects.filter(course=obj.course).order_by('id').first()
    if not co:raise HttpError(400,'This course has no open cohort. Contact the seller.')
    row=enrol(request.user,co.id)
    if row.status=='Waitlisted':return {'status':'Waitlisted','message':'Cohort is full; you joined the waitlist. No preview purchase was recorded.'}
    purchase,_=MarketplacePurchase.objects.get_or_create(listing=obj,user=request.user,defaults={'amount':obj.price})
    audit(request.user,'marketplace.preview_enrol',purchase)
    return {'status':row.status,'message':'Preview enrolment completed. No payment was taken.'}


@router.get('/marketplace/seller/dashboard')
@list_page
def seller_dashboard(request):
    require_role(request.user,'Admin','Teacher','Seller')
    qs=MarketplaceListing.objects.filter(**scope(request.user))
    if request.user.profile.role!='Admin':qs=qs.filter(seller=request.user)
    return [{'id':l.id,'title':l.course.title,'price':str(l.price),'enrolments':l.marketplacepurchase_set.count(),'preview_earnings':str(sum((p.amount for p in l.marketplacepurchase_set.all()),Decimal('0')))} for l in qs]


class PolicyIn(Schema):
    course_id:int
    allowed_topics:list[str]=Field(default_factory=list,max_length=100)
    blocked_topics:list[str]=Field(default_factory=list,max_length=100)
    tone:str=Field(default='Supportive',max_length=100)
    escalation:str=Field(default='Ask your teacher for help.',max_length=200)


@router.get('/tutor/policies')
def policies(request):
    return [serial(p) for p in TutorPolicy.objects.filter(course__in=courses(request.user))]


@router.post('/tutor/policies')
@transaction.atomic
def save_policy(request,data:PolicyIn):
    require_capability(request.user,'tutor_policy')
    manage(request.user,data.course_id,('Admin','Coordinator'))
    values=data.model_dump(exclude={'course_id'})
    for key in ('allowed_topics','blocked_topics'):
        values[key]=list(dict.fromkeys(term.strip() for term in values[key] if term.strip()))
        if any(len(term)>200 for term in values[key]):raise HttpError(400,'Topic phrases are limited to 200 characters')
    for key in ('tone','escalation'):
        values[key]=values[key].strip()
        if not values[key]:raise HttpError(400,'Tone and escalation guidance cannot be blank')
    Course.objects.select_for_update().get(pk=data.course_id)
    p,_=TutorPolicy.objects.update_or_create(course_id=data.course_id,defaults={**values,**scope(request.user)})
    audit(request.user,'tutor.policy',p);return serial(p)


@router.get('/tutor/policies/{course_id}')
def tutor_policy_detail(request,course_id:int):
    c=course_access(request.user,course_id)
    from .tutor_workflow import workflow
    row=TutorPolicy.objects.filter(course=c).first()
    return {**(serial(row) if row else workflow(request.user)['policy_defaults']),'course':c.id,'saved':row is not None}


class TutorIn(Schema):
    course_id:int
    question:str=Field(min_length=1,max_length=2000)


@router.post('/tutor/chat')
def tutor_chat(request,data:TutorIn):
    from . import ai_service
    c=learner_course_access(request.user,data.course_id)
    if c.status!='Published':raise HttpError(403,'This course is not published')
    question=data.question.strip()
    if not question:raise HttpError(400,'Enter a question')
    p=TutorPolicy.objects.filter(course=c).first()
    if p:
        blocked=any(x.strip() and x.strip().casefold() in question.casefold() for x in p.blocked_topics)
        topics=[x.strip() for x in p.allowed_topics if x.strip()]
        outside=bool(topics) and not any(x.casefold() in question.casefold() for x in topics)
        if blocked or outside:raise HttpError(400,'This topic is not allowed by the course tutor policy. '+p.escalation)
    body='\n'.join(Lesson.objects.filter(course=c,status='Published').order_by('position','id').values_list('body',flat=True))[:60000]
    if not body:raise HttpError(400,'This course has no published lesson content')
    from .ai_limits import enforce_quota
    enforce_quota(request.user)
    text=ai_service.generate((f'Use a {p.tone} tone. ' if p else '')+question,body)
    if p and any(x.strip() and x.strip().casefold() in text.casefold() for x in p.blocked_topics):text='The response was withheld by the course tutor policy. '+p.escalation
    audit(request.user,'tutor.answer',c,{'mode':'Course'})
    return {'text':text,'disclosure':'Generated by AI — please check'}


class FlagIn(Schema):
    course_id:int
    excerpt:str=Field(min_length=1,max_length=10000)
    reason:str=Field(min_length=1,max_length=2000)


@router.post('/tutor/flags')
@transaction.atomic
def tutor_flag(request,data:FlagIn):
    learner_course_access(request.user,data.course_id)
    if not data.excerpt.strip() or not data.reason.strip():raise HttpError(400,'An answer excerpt and reason are required')
    row=TutorFlag.objects.create(user=request.user,**scope(request.user),**data.dict());audit(request.user,'tutor.flag',row);return serial(row)


@router.get('/tutor/flags')
@list_page
def tutor_flags(request):
    from .tutor_workflow import flags_for
    return [{**serial(x),'course_title':x.course.title,'learner':x.user.first_name} for x in flags_for(request.user)]


class DecisionIn(Schema):
    decision:str=Field(min_length=1,max_length=4000)


@router.post('/tutor/flags/{item_id}/review')
@transaction.atomic
def review_flag(request,item_id:int,data:DecisionIn):
    require_capability(request.user,'tutor_review')
    from .tutor_workflow import flags_for
    obj=get_object_or_404(flags_for(request.user).select_for_update(),pk=item_id)
    if not data.decision.strip():raise HttpError(400,'Enter review guidance')
    obj.decision=data.decision.strip();obj.status='Reviewed';obj.save();audit(request.user,'tutor.review',obj);return serial(obj)


@router.post('/submissions/{item_id}/reevaluation')
@transaction.atomic
def reevaluate(request,item_id:int,data:DecisionIn):
    s=get_object_or_404(Submission,pk=item_id,user=request.user);course_access(request.user,s.assignment.course_id)
    if s.status!='Marked':raise HttpError(400,'Only marked work can be sent for re-evaluation')
    row=Reevaluation.objects.create(submission=s,reason=data.decision);s.status='Re-evaluation requested';s.save();audit(request.user,'submission.reevaluation',row);return serial(row)


@router.post('/submissions/{item_id}/resubmit')
@transaction.atomic
def allow_resubmit(request,item_id:int):
    require_capability(request.user,"mark")
    s=get_object_or_404(Submission,pk=item_id);manage(request.user,s.assignment.course_id,('Admin','Teacher','TA'))
    s.status='Resubmit';s.save();audit(request.user,'submission.resubmit_allowed',s);return {'status':s.status}


@router.get('/submissions/history/all')
@list_page
def marking_history(request):
    if request.user.profile.role not in ('Admin','Teacher','Coordinator','TA','Learner'):return []
    qs=MarkingHistory.objects.filter(submission__assignment__course__in=courses(request.user))
    if request.user.profile.role=='Learner':qs=qs.filter(submission__user=request.user)
    return [{**serial(x),'assignment':x.submission.assignment.title} for x in qs.order_by('-id')]


class AwardIn(Schema):
    user_id:int


class RuleIn(Schema):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(min_length=1,max_length=5000)
    trigger:str='Course completion'
    threshold:float=Field(default=100,gt=0,le=100)


@router.post('/credentials/rules')
@transaction.atomic
def credential_rule(request,data:RuleIn):
    require_capability(request.user,"assessment_write")
    manage(request.user,data.course_id,('Admin','Teacher'))
    if data.trigger not in ('Course completion','Quiz score','Assignment score'):raise HttpError(400,'Unknown credential trigger')
    c=Credential.objects.create(course_id=data.course_id,title=data.title,description=data.description,**scope(request.user))
    rule=CredentialRule.objects.create(credential=c,trigger=data.trigger,threshold=data.threshold);audit(request.user,'credential.rule',rule);return serial(rule)


@router.get('/credentials/rules')
@list_page
def rules(request):
    return [{**serial(c),'rule':serial(r) if (r:=CredentialRule.objects.filter(credential=c).first()) else {'trigger':'Course completion','threshold':100}} for c in Credential.objects.filter(course__in=courses(request.user))]


@router.post('/credentials/{item_id}/award')
@transaction.atomic
def award(request,item_id:int,data:AwardIn):
    require_capability(request.user,"assessment_write")
    c=get_object_or_404(Credential,pk=item_id);manage(request.user,c.course_id,('Admin','Teacher'))
    u=get_object_or_404(User,pk=data.user_id,profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus)
    if not Enrolment.objects.filter(user=u,cohort__course=c.course,status__in=['Enrolled','Completed']).exists():raise HttpError(400,'Learner must be enrolled in the course')
    a,new=CredentialAward.objects.get_or_create(credential=c,user=u)
    if new:Certificate.objects.create(award=a)
    audit(request.user,'credential.manual_award',a);return {'id':a.id}


@router.get('/certificates')
@list_page
def certificate_list(request):
    if request.user.profile.role not in ('Admin','Teacher','Coordinator','TA','Learner'):return []
    qs=Certificate.objects.filter(award__credential__course__in=courses(request.user))
    if request.user.profile.role=='Learner':qs=qs.filter(award__user=request.user)
    return [{'id':c.id,'code':str(c.code),'status':c.status,'title':c.award.credential.title,'learner':c.award.user.first_name,'issued_at':c.award.awarded_at.isoformat()} for c in qs]


@router.post('/certificates/{item_id}/revoke')
@transaction.atomic
def revoke(request,item_id:int):
    require_capability(request.user,"assessment_write")
    c=get_object_or_404(Certificate,pk=item_id);manage(request.user,c.award.credential.course_id,('Admin','Teacher'))
    c.status='Revoked';c.save();audit(request.user,'certificate.revoke',c);return {'status':c.status}


class AnnouncementIn(Schema):
    course_id:int
    title:str=Field(min_length=1,max_length=200)
    body:str=Field(min_length=1,max_length=5000)


@router.post('/announcements')
@transaction.atomic
def announce(request,data:AnnouncementIn):
    require_capability(request.user,"roster_manage")
    manage(request.user,data.course_id)
    obj=Announcement.objects.create(sender=request.user,**scope(request.user),**data.dict())
    ids=Enrolment.objects.filter(cohort__course_id=data.course_id,status__in=['Enrolled','Completed']).values_list('user_id',flat=True).distinct()
    recipients=(set(ids)|{request.user.id})-set(Preference.objects.filter(user_id__in=set(ids)|{request.user.id},notifications=False).values_list('user_id',flat=True))
    Notification.objects.bulk_create([Notification(announcement=obj,user_id=u) for u in recipients]);audit(request.user,'announcement.create',obj);return serial(obj)


@router.get('/notifications')
@list_page
def notifications(request):
    return [{'id':n.id,'title':n.announcement.title,'body':n.announcement.body,'read':n.read_at is not None,'course':n.announcement.course.title} for n in Notification.objects.filter(user=request.user).order_by('-id')]


@router.post('/notifications/{item_id}/read')
@transaction.atomic
def read_notification(request,item_id:int):
    n=get_object_or_404(Notification,pk=item_id,user=request.user);n.read_at=timezone.now();n.save();audit(request.user,'notification.read',n);return {'read':True}


class EnrolIn(Schema):
    user_id:int
    status:str='Enrolled'


@router.get('/learners')
def learner_directory(request):
    require_role(request.user,'Admin','Teacher','Coordinator')
    qs=User.objects.filter(profile__role='Learner',profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus,is_active=True)
    if request.user.profile.role=='Teacher':qs=qs.filter(enrolment__cohort__course__in=courses(request.user)).distinct()
    return list(qs.values('id','first_name','email'))


@router.get('/teachers')
def teacher_directory(request):
    require_role(request.user,'Admin','Teacher','Coordinator')
    return list(User.objects.filter(profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus,profile__role='Teacher',is_active=True).values('id','first_name','email'))


@router.post('/cohorts/{item_id}/enrolments')
@transaction.atomic
def roster_change(request,item_id:int,data:EnrolIn):
    require_capability(request.user,"roster_manage")
    co=get_object_or_404(Cohort.objects.select_for_update(),pk=item_id,**scope(request.user));manage(request.user,co.course_id)
    u=get_object_or_404(User,pk=data.user_id,profile__role='Learner',profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus,is_active=True)
    if data.status not in ('Enrolled','Removed'):raise HttpError(400,'Choose Enrolled or Removed')
    current=Enrolment.objects.filter(cohort=co,user=u).first()
    prior_status=current.status if current else None
    state=data.status
    if state=='Enrolled' and current and current.status in ('Enrolled','Completed','Waitlisted'):
        return serial(current)
    if state=='Enrolled' and (co.end_date < timezone.localdate() or co.course.is_deleted):raise HttpError(400,'Cannot enrol into an ended cohort or archived course')
    if state=='Enrolled' and (not current or current.status not in ('Enrolled','Completed')) and co.enrolment_set.filter(status__in=['Enrolled','Completed']).count()>=co.capacity:state='Waitlisted'
    defaults={'status':state}
    if state=='Enrolled' or state=='Waitlisted':defaults['enrolled_at']=timezone.now()
    row,_=Enrolment.objects.update_or_create(cohort=co,user=u,defaults=defaults);audit(request.user,'roster.update',row,{'status':state})
    if state=='Removed' and prior_status in ('Enrolled','Completed'):
        waiting=co.enrolment_set.filter(status='Waitlisted',user__is_active=True).order_by('enrolled_at','id').first()
        if waiting:waiting.status='Enrolled';waiting.save();audit(request.user,'roster.promote',waiting)
    return serial(row)


class CourseEditIn(Schema):
    subject:str|None=Field(default=None,max_length=80)
    level:str|None=Field(default=None,max_length=40)
    cover_id:int|None=None
    title:str=Field(min_length=1,max_length=200)
    description:str=Field(min_length=1,max_length=20000)
    outcomes:list[str]=Field(min_length=1)
    modules:list[str]=Field(min_length=1)
    status:str
    owner_id:int|None=None
    duration_minutes:int=Field(default=0,ge=0,le=1000000)


@router.post('/courses/{item_id}/edit')
@transaction.atomic
def course_edit(request,item_id:int,data:CourseEditIn):
    require_capability(request.user,"course_manage")
    c=course_access(request.user,item_id,True)
    if data.status not in ('Draft','Published'):raise HttpError(400,'Choose Draft or Published')
    if not data.title.strip() or not data.description.strip() or not all(x.strip() for x in data.outcomes+data.modules):raise HttpError(400,'Title, description, outcomes and modules cannot be blank')
    if data.owner_id and data.owner_id!=c.owner_id:
        require_role(request.user,'Admin','Coordinator')
        get_object_or_404(User,pk=data.owner_id,profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus,profile__role='Teacher',is_active=True)
        c.owner_id=data.owner_id
    if 'cover_id' in data.model_fields_set:
        cover=attachment(request.user,data.cover_id,c.id)
        if cover and cover.mime not in ('image/png','image/jpeg'):raise HttpError(400,'A course cover must be a PNG or JPEG image')
        c.cover=cover
    for k,v in data.dict(exclude={'owner_id','cover_id'}).items():
        if k in ('subject','level') and v is None:continue
        if k in ('subject','level') and not v.strip():raise HttpError(400,'Subject and level cannot be blank')
        setattr(c,k,v)
    c.save();audit(request.user,'course.edit',c);return serial(c)


@router.post('/courses/{item_id}/archive')
@transaction.atomic
def archive_course(request,item_id:int,data:ActionIn):
    require_capability(request.user,"course_manage")
    c=course_access(request.user,item_id,True)
    if data.action!='confirm':raise HttpError(400,'Confirm archiving after reviewing dependent enrolments and work')
    c.is_deleted=True;c.save();audit(request.user,'course.archive',c,{'enrolments':Enrolment.objects.filter(cohort__course=c).count(),'submissions':Submission.objects.filter(assignment__course=c).count()});return {'status':'Archived; dependent records preserved'}


@router.get('/question-bank')
@list_page
def question_bank(request,q:str='',topic:str='',difficulty:str=''):
    require_role(request.user,'Admin','Teacher')
    qs=Question.objects.filter(quiz__course__in=courses(request.user),prompt__icontains=q)
    if topic:qs=qs.filter(topic__icontains=topic)
    if difficulty:qs=qs.filter(difficulty=difficulty)
    return [{'id':x.id,'quiz_id':x.quiz_id,'course_id':x.quiz.course_id,'quiz':x.quiz.title,'prompt':x.prompt,'options':x.options,'answer':x.answer,'explanation':x.explanation,'topic':x.topic,'difficulty':x.difficulty,'kind':x.kind,'answer_set':x.answer_set,'numeric_answer':x.numeric_answer,'tolerance':x.tolerance,'correct_marks':x.correct_marks,'wrong_marks':x.wrong_marks} for x in qs.select_related('quiz')]


class BankIn(Schema):
    quiz_id:int
    prompt:str=Field(min_length=1,max_length=5000)
    options:list[str]=Field(default_factory=list,max_length=8)
    answer:int=Field(default=0,ge=0)
    explanation:str=Field(default='',max_length=5000)
    topic:str=Field(default='General',max_length=100)
    difficulty:str=Field(default='Beginner',max_length=30)
    kind:str='Single choice'
    answer_set:list[int]=Field(default_factory=list,max_length=8)
    numeric_answer:float|None=None
    tolerance:float=Field(default=0,ge=0)
    correct_marks:float|None=Field(default=None,ge=0)
    wrong_marks:float|None=Field(default=None,le=0)


@router.post('/question-bank')
@transaction.atomic
def bank_add(request,data:BankIn):
    require_capability(request.user,"assessment_write")
    quiz=get_object_or_404(Quiz.objects.select_for_update(),pk=data.quiz_id);manage(request.user,quiz.course_id,('Admin','Teacher'))
    if quiz.attempt_set.exists():raise HttpError(400,'This assessment has attempts; create a new quiz version before adding questions')
    if quiz.question_set.count()>=200:raise HttpError(400,'An assessment supports at most 200 questions')
    from .assessment import validate_question
    validate_question(data)
    row=Question.objects.create(**data.dict());audit(request.user,'question.create',row);return serial(row)


class DestinationIn(Schema):
    quiz_id:int


@router.post('/question-bank/{item_id}/copy')
@transaction.atomic
def bank_copy(request,item_id:int,data:DestinationIn):
    require_capability(request.user,"assessment_write")
    q=get_object_or_404(Question,pk=item_id);manage(request.user,q.quiz.course_id,('Admin','Teacher'))
    destination=get_object_or_404(Quiz.objects.select_for_update(),pk=data.quiz_id);manage(request.user,destination.course_id,('Admin','Teacher'))
    if destination.attempt_set.exists():raise HttpError(400,'Destination assessment already has attempts; create a new version')
    if destination.question_set.count()>=200:raise HttpError(400,'An assessment supports at most 200 questions')
    copied=Question.objects.create(quiz=destination,prompt=q.prompt,options=q.options,answer=q.answer,explanation=q.explanation,topic=q.topic,difficulty=q.difficulty,kind=q.kind,answer_set=q.answer_set,numeric_answer=q.numeric_answer,tolerance=q.tolerance,correct_marks=q.correct_marks,wrong_marks=q.wrong_marks)
    audit(request.user,'question.copy',copied);return {'id':copied.id}


@router.get('/active-attempt')
def active_attempt(request):
    from .api import attempt_row
    from .services import expired,finish_attempt
    qs=Attempt.objects.filter(user=request.user,submitted_at=None,quiz__course__in=courses(request.user)).order_by('-started_at')
    for a in qs:
        if expired(a):finish_attempt(request.user,a.id)
        else:return attempt_row(a)
    return None


@router.get('/certificates/{item_id}/qr')
def certificate_qr(request,item_id:int):
    import os
    import io
    import qrcode
    import qrcode.image.svg
    from django.http import HttpResponse
    c=get_object_or_404(Certificate,pk=item_id,award__credential__course__in=courses(request.user))
    if not permits(request.user,'teaching_read') and c.award.user_id!=request.user.id:raise HttpError(403,'This certificate belongs to another learner')
    target=os.environ.get('PUBLIC_APP_URL','http://127.0.0.1:3000').rstrip('/')+'/verify/'+str(c.code)
    image=qrcode.make(target,image_factory=qrcode.image.svg.SvgPathImage)
    output=io.BytesIO();image.save(output)
    return HttpResponse(output.getvalue(),content_type='image/svg+xml')


@router.get('/progress')
def progress_dashboard(request):
    completed=LessonCompletion.objects.filter(user=request.user,lesson__course__in=courses(request.user))
    dates=set(timezone.localtime(x.completed_at).date() for x in completed)
    day=timezone.localdate()
    if day not in dates:day-=timedelta(days=1)
    streak=0
    while day in dates:streak+=1;day-=timedelta(days=1)
    if request.GET.get('summary')=='1':
        from .report_queries import report_query
        qs=report_query('progress_courses',request,{}).queryset
        result=qs.aggregate(average=Avg('progress'),total=Count('id'),completed=Count('id',filter=Q(progress=100)))
        return {'items':[],'learners':[],'total_courses':result['total'],'streak':streak,'lessons':completed.count(),'completed_courses':result['completed'],'average':round(result['average'] or 0)}
    items=[{'id':c.id,'title':c.title,'progress':progress(request.user,c)} for c in courses(request.user)]
    learners=[]
    if request.user.profile.role in ('Admin','Teacher','Coordinator'):
        for e in Enrolment.objects.filter(cohort__course__in=courses(request.user),status__in=['Enrolled','Completed']).select_related('user','cohort__course'):
            learners.append({'id':e.id,'learner':e.user.first_name,'course':e.cohort.course.title,'progress':progress(e.user,e.cohort.course)})
    return {'items':items,'streak':streak,'lessons':completed.count(),'completed_courses':sum(c['progress']==100 for c in items),'average':round(sum(c['progress'] for c in items)/len(items)) if items else 0,'learners':learners}

