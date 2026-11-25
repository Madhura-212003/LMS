from .permissions import require as require_capability,permits
from .listing import list_page
import hashlib
from datetime import date, datetime, timedelta
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError, ValidationError
from ninja.security import django_auth
from pydantic import Field
from typing import Any
from .models import *
from .services import learner_course_access, scope, audit, require_role, courses, course_access, enrol, review, progress, complete, expired, finish_attempt, validate_answers
from . import ai_service
from django.conf import settings
from .identity import session_auth,EntraBearer,configured

api = NinjaAPI(title='Admiezo LMS API', version='0.3.1', auth=[session_auth,EntraBearer()],docs_url=None if settings.PRODUCTION else '/docs')
from .feature_api import router as feature_router
api.add_router('/features', feature_router)
from .final_api import router as final_router
api.add_router('/final',final_router)
from .staff_api import router as staff_router
api.add_router('/staff',staff_router)
from .lists_api import router as lists_router
api.add_router('/lists',lists_router)


@api.exception_handler(ValidationError)
def invalid(request, exc):
    errors=[{'field':'.'.join(str(x) for x in e.get('loc',[]) if x not in ('body','data')),'message':e.get('msg','Invalid value')} for e in exc.errors]
    return JsonResponse({'detail':'; '.join(e['field']+': '+e['message'] for e in errors),'errors':errors},status=400)


@api.exception_handler(Exception)
def service_error(request, exc):
    import logging
    logging.getLogger('lms').exception('LMS request failed',exc_info=exc)
    return JsonResponse({'detail':'The service could not complete this request. Retry, or contact your administrator if it continues.'},status=500)


class LoginIn(Schema):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def identity(user):
    from .permissions import roles,permissions
    return {'roles':sorted(roles(user)),'permissions':permissions(user),'id': user.id, 'name': user.first_name or user.username, 'email': user.email, 'role': user.profile.role, 'tenant': user.profile.tenant, 'campus': user.profile.campus}


@api.get('/auth/csrf', auth=None)
def csrf(request):
    return {'csrfToken': get_token(request)}


@api.get('/auth/config',auth=None)
def auth_config(request):
    import os
    return {'institution_sign_in':configured(),'password_sign_in':not settings.PRODUCTION,'environment':os.environ.get('LMS_ENV','development'),'execution_service':bool(os.environ.get('EXECUTION_SERVICE_URL')),'ui_languages':['en','hi','kn']}


@api.get('/health/live',auth=None)
def live_health(request):return {'status':'ok','version':'0.3.1'}


@api.get('/health/ready',auth=None)
def ready_health(request):
    from django.db import connection
    from django.core.cache import cache
    try:
        with connection.cursor() as cursor:cursor.execute('SELECT 1');cursor.fetchone()
        cache.set('lms-readiness','ok',timeout=10)
        if cache.get('lms-readiness')!='ok':raise RuntimeError('cache')
    except Exception:return JsonResponse({'status':'unavailable'},status=503)
    return {'status':'ready'}


@api.post('/auth/login', auth=None)
def sign_in(request, data: LoginIn):
    if settings.PRODUCTION:raise HttpError(403,'Use your institution sign-in. Password/demo login is disabled in production.')
    # Unauthenticated Ninja operations need explicit CSRF checking.
    from django.middleware.csrf import CsrfViewMiddleware
    if CsrfViewMiddleware(lambda r: None).process_view(request, lambda r: None, (), {}):
        raise HttpError(403, 'Refresh the page and retry sign in')
    key = hashlib.sha256(data.email.strip().lower().encode()).hexdigest()
    with transaction.atomic():
        guard, _ = LoginThrottle.objects.select_for_update().get_or_create(key=key)
        if guard.locked_until and guard.locked_until > timezone.now():
            raise HttpError(429, 'Too many failed attempts. Try again in 15 minutes.')
        if guard.locked_until:
            guard.failures = 0
            guard.locked_until = None
        user = authenticate(request, username=data.email.strip().lower(), password=data.password)
        if not user:
            guard.failures += 1
            if guard.failures >= 5:
                guard.locked_until = timezone.now() + timedelta(minutes=15)
            guard.save()
        else:
            guard.failures = 0
            guard.locked_until = None
            guard.save()
    if not user:
        raise HttpError(401, 'Invalid email or password')
    login(request, user)
    audit(user, 'auth.login', user)
    return identity(user)


@api.post('/auth/logout')
def sign_out(request):
    audit(request.user, 'auth.logout', request.user)
    logout(request)
    return {'message': 'Signed out'}


@api.get('/auth/me')
def me(request):
    return identity(request.user)


def course_row(c, user):
    from .course_workflow import course_cohorts
    cohort_options = course_cohorts(c, user)
    own_states = [x['enrolment_status'] for x in cohort_options]
    enrolment_status = next((state for state in ('Enrolled', 'Completed', 'Waitlisted') if state in own_states), None)
    cohort = next((x for x in cohort_options if x['can_join']), None)
    listing=MarketplaceListing.objects.filter(course=c,status='Published').first()
    from django.db.models import Avg
    rating=CourseReview.objects.filter(course=c).aggregate(value=Avg('rating'))['value']
    return {'cover_id':c.cover_id,'duration_minutes':c.duration_minutes,'rating':round(rating,1) if rating is not None else None,'price':str(listing.price) if listing else '0.00','id': c.id, 'title': c.title, 'description': c.description, 'subject': c.subject, 'level': c.level, 'status': c.status, 'owner': c.owner.first_name, 'updated_at': c.updated_at.isoformat(), 'progress': round(c._progress) if hasattr(c,'_progress') else progress(user,c), 'cohort_id': cohort['id'] if cohort else None, 'cohorts': cohort_options, 'owner_id': c.owner_id, 'enrolment_status': enrolment_status, 'enrolled': courses(user).filter(pk=c.pk).exists(), 'outcomes': c.outcomes, 'modules': c.modules}


@api.get('/personalisation-workflow')
def personalisation_workflow(request):
    from .personalisation_workflow import workflow
    return workflow(request.user)


@api.get('/tutor-workflow')
def tutor_workflow(request):
    from .tutor_workflow import workflow
    return workflow(request.user)


@api.get('/language-workflow')
def language_workflow(request):
    from .language_workflow import workflow
    return workflow(request.user)


@api.get('/path-workflow')
def path_workflow(request):
    from .path_workflow import workflow
    return workflow(request.user)


@api.get('/lecture-workflow')
def lecture_workflow(request):
    from .lecture_workflow import workflow
    return workflow(request.user)


@api.get('/live-workflow')
def live_workflow(request):
    from .live_workflow import workflow
    return workflow(request.user)


@api.get('/library-workflow')
def library_workflow(request):
    from .library_workflow import workflow
    return workflow(request.user)


@api.get('/content-workflow')
def content_workflow(request):
    from .content_workflow import workflow
    return workflow(request.user)


@api.get('/course-workflow')
def course_workflow(request):
    from .permissions import permissions
    from .course_workflow import workflow_screens
    return {'module_id':156, 'screens': workflow_screens(request.user), 'permissions': permissions(request.user), 'course_statuses': ['Draft', 'Published'],
            'default_course_status': Course._meta.get_field('status').default,
            'max_cohort_capacity': next(item.le for item in CohortIn.model_fields['capacity'].metadata if hasattr(item, 'le')),
            'metric_labels': {'cohorts': 'Cohorts', 'learners': 'Enrolled learners',
                              'waitlisted': 'Waiting enrolments', 'published_lessons': 'Published lessons',
                              'average_progress': 'Average learner progress'}}


@api.get('/home')
def home(request):
    ids = courses(request.user).values_list('id', flat=True)
    return {'courses': [course_row(c, request.user) for c in courses(request.user)[:6]],
            'counts': {'courses': len(ids), 'lessons': LessonCompletion.objects.filter(user=request.user, lesson__course_id__in=ids).count(), 'credentials': CredentialAward.objects.filter(user=request.user).count(), 'assignments': Assignment.objects.filter(course_id__in=ids).count()},
            'due_items': list(Assignment.objects.filter(course_id__in=ids,status='Published',due_at__gte=timezone.now()).exclude(submission__user=request.user).order_by('due_at').values('id', 'title', 'due_at')[:5])}


@api.get('/courses')
@list_page
def list_courses(request, catalogue: bool = False, mine: bool = False, q: str = '', status: str = '', sort: str = 'title', page: int = 1):
    qs = courses(request.user, catalogue).filter(title__icontains=q)
    if mine and request.user.profile.role == 'Learner':
        qs = Course.objects.filter(**scope(request.user), is_deleted=False, cohort__enrolment__user=request.user, cohort__enrolment__status__in=['Enrolled','Completed','Waitlisted']).distinct().filter(title__icontains=q)
    if status:
        qs = qs.filter(status=status)
    if sort not in ('title', '-title', '-updated_at'):
        raise HttpError(400, 'Unknown sort order')
    page = max(1, page)
    return {'items': [course_row(c, request.user) for c in qs.order_by(sort)[(page-1)*20:page*20]], 'total': qs.count()}


class CourseIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=20000)
    outcomes: list[str] = Field(min_length=1)
    modules: list[str] = Field(min_length=1)
    subject: str = Field(default='Technology', max_length=80)
    level: str = Field(default='Beginner', max_length=40)
    status: str = 'Draft'
    owner_id:int|None=None
    duration_minutes:int=Field(default=0,ge=0,le=1000000)


@api.post('/courses')
@transaction.atomic
def create_course(request, data: CourseIn):
    require_capability(request.user,"course_manage")
    require_role(request.user, 'Admin', 'Teacher', 'Coordinator', 'Seller')
    if not data.title.strip() or not data.description.strip() or not data.subject.strip() or not data.level.strip() or not all(x.strip() for x in data.outcomes + data.modules):
        raise HttpError(400, 'Title, outcomes and modules cannot be blank')
    if data.status not in ('Draft', 'Published'):
        raise HttpError(400, 'Choose Draft or Published')
    owner=request.user
    if data.owner_id and data.owner_id!=request.user.id:
        require_role(request.user,'Admin','Coordinator')
        owner=get_object_or_404(__import__('django.contrib.auth.models',fromlist=['User']).User,pk=data.owner_id,profile__role='Teacher',profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus,is_active=True)
    c = Course.objects.create(owner=owner, **scope(request.user), **data.dict(exclude={'owner_id'}))
    audit(request.user, 'course.create', c)
    return course_row(c, request.user)


@api.get('/courses/{course_id}')
def get_course(request, course_id: int):
    require_role(request.user,'Admin','Teacher','Coordinator','Seller','Learner','Translator','Author','Reviewer','TA')
    c = course_access(request.user, course_id)
    qs = Lesson.objects.filter(course=c).order_by('position', 'id')
    if request.user.profile.role == 'Learner':
        qs = qs.filter(status='Published')
    return {**course_row(c, request.user), 'lessons': [{'id': l.id, 'title': l.title, 'body': l.body, 'status': l.status,'attachments':l.attachments,'quiz_links':l.quiz_links, 'owner': l.author.first_name, 'updated_at': l.updated_at.isoformat(), 'completed': LessonCompletion.objects.filter(lesson=l, user=request.user).exists()} for l in qs]}


class CohortIn(Schema):
    course_id: int
    name: str = Field(min_length=1, max_length=120)
    capacity: int = Field(gt=0, le=10000)
    start_date: date
    end_date: date
    teacher_id:int|None=None


@api.post('/cohorts')
@transaction.atomic
def create_cohort(request, data: CohortIn):
    require_capability(request.user,"roster_manage")
    course_access(request.user, data.course_id, True)
    if data.start_date >= data.end_date:
        raise HttpError(400, 'End date must be after start date')
    if not data.name.strip():raise HttpError(400, 'Cohort name cannot be blank')
    if data.end_date < timezone.localdate():raise HttpError(400, 'A new cohort cannot have already ended')
    teacher=course_access(request.user, data.course_id, True).owner
    if data.teacher_id:
        teacher=get_object_or_404(__import__('django.contrib.auth.models',fromlist=['User']).User,pk=data.teacher_id,profile__role='Teacher',profile__tenant=request.user.profile.tenant,profile__campus=request.user.profile.campus,is_active=True)
    c = Cohort.objects.create(teacher=teacher, **scope(request.user), **data.dict(exclude={'teacher_id'}))
    audit(request.user, 'cohort.create', c)
    return {'id': c.id, 'name': c.name}


@api.post('/cohorts/{cohort_id}/enrolments')
def join_cohort(request, cohort_id: int):
    row = enrol(request.user, cohort_id)
    return {'id': row.id, 'status': row.status}


@api.get('/cohorts')
@list_page
def cohorts(request):
    qs = Cohort.objects.filter(course__in=courses(request.user))
    if request.user.profile.role == 'Learner':
        qs = qs.filter(enrolment__user=request.user,enrolment__status__in=['Enrolled','Completed'])
    return [{'id': c.id, 'name': c.name, 'course_id': c.course_id, 'course_title':c.course.title, 'capacity': c.capacity, 'start_date':str(c.start_date), 'end_date':str(c.end_date), 'enrolments': list(c.enrolment_set.values('id', 'user_id', 'user__first_name', 'status')) if request.user.profile.role in ('Admin','Teacher','Coordinator','TA') else []} for c in qs]


class LessonIn(Schema):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=60000)
    position: int = Field(default=1, ge=1)
    attachments: list[int] = Field(default_factory=list,max_length=20)
    quiz_links:list[int]=Field(default_factory=list,max_length=20)


@api.get('/content')
@list_page
def list_content(request, q: str = '', status: str = '', sort: str = 'title', page: int = 1):
    if request.user.profile.role=='Librarian':return {'items':[],'total':0}
    qs = Lesson.objects.filter(course__in=courses(request.user)).select_related('course', 'author')
    if request.user.profile.role == 'Learner':
        qs = qs.filter(status='Published')
    qs = qs.filter(models.Q(title__icontains=q) | models.Q(course__title__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if sort not in ('title', '-title', '-updated_at'):
        raise HttpError(400, 'Unknown sort order')
    page = max(1, page)
    done = set(LessonCompletion.objects.filter(user=request.user).values_list('lesson_id', flat=True))
    return {'total': qs.count(), 'items': [
        {'id': l.id, 'course_id': l.course_id, 'course': l.course.title, 'title': l.title,
         'body': l.body, 'position': l.position, 'status': l.status, 'attachments':l.attachments,'quiz_links':l.quiz_links,
         'owner': l.author.first_name, 'updated_at': l.updated_at.isoformat(), 'completed': l.id in done}
        for l in qs.order_by(sort, 'id')[(page-1)*20:page*20]
    ]}


@api.post('/content/{lesson_id}/edit')
@transaction.atomic
def edit_lesson(request, lesson_id: int, data: LessonIn):
    require_capability(request.user,"content_write")
    l = get_object_or_404(Lesson.objects.select_for_update(), pk=lesson_id)
    course_access(request.user, l.course_id, True)
    if data.course_id != l.course_id:
        raise HttpError(400, 'A lesson cannot be moved to a different course')
    if l.status not in ('Draft', 'Needs Changes'):
        raise HttpError(400, 'Only Draft or Needs Changes content can be edited')
    if not data.title.strip() or not data.body.strip():
        raise HttpError(400, 'Title and lesson content are required')
    source_changed=l.title!=data.title or l.body!=data.body
    l.title, l.body, l.position = data.title, data.body, data.position
    validate_attachments(request.user,data.course_id,data.attachments)
    l.attachments=data.attachments
    validate_quiz_links(request.user,data.course_id,data.quiz_links)
    l.quiz_links=data.quiz_links
    l.save()
    if source_changed:Translation.objects.filter(lesson=l).update(status='In translation',updated_at=timezone.now())
    audit(request.user, 'lesson.edit', l)
    return {'id': l.id, 'status': l.status}


@api.post('/content')
@transaction.atomic
def create_lesson(request, data: LessonIn):
    require_capability(request.user,"content_write")
    course_access(request.user, data.course_id, True)
    if not data.title.strip() or not data.body.strip():
        raise HttpError(400, 'Title and lesson content are required')
    validate_attachments(request.user,data.course_id,data.attachments)
    validate_quiz_links(request.user,data.course_id,data.quiz_links)
    l = Lesson.objects.create(author=request.user, **scope(request.user), **data.dict())
    audit(request.user, 'lesson.create', l)
    return {'id': l.id, 'status': l.status}


def validate_quiz_links(user,course_id,ids):
    if len(set(ids))!=len(ids) or Quiz.objects.filter(pk__in=ids,course_id=course_id).count()!=len(ids):
        raise HttpError(400,'Select unique assessments from this lesson course')


class ReviewIn(Schema):
    decision: str
    comment: str = Field(default='', max_length=4000)


@api.get('/content/{lesson_id}/reviews')
@list_page
def content_reviews(request, lesson_id: int):
    require_role(request.user, 'Admin', 'Teacher', 'Author', 'Reviewer')
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    course_access(request.user, lesson.course_id)
    return list(ContentReview.objects.filter(lesson=lesson).order_by('-created_at', '-id').values(
        'id', 'decision', 'comment', 'created_at', 'reviewer__first_name'))


@api.post('/content/{lesson_id}/review')
def review_lesson(request, lesson_id: int, data: ReviewIn):
    with transaction.atomic():
        l = get_object_or_404(Lesson.objects.select_for_update(), pk=lesson_id)
        review(request.user, l, data.decision, data.comment)
    return {'status': l.status}


@api.post('/content/{lesson_id}/complete')
def complete_lesson(request, lesson_id: int):
    l = get_object_or_404(Lesson, pk=lesson_id)
    return {'progress': complete(request.user, l)}


@api.get('/assignments')
@list_page
def assignments(request):
    if request.user.profile.role not in ('Admin','Teacher','Coordinator','TA','Learner'):return []
    rows = []
    for a in Assignment.objects.filter(course__in=courses(request.user)).filter(**({'status':'Published'} if request.user.profile.role=='Learner' else {})).order_by('due_at'):
        submissions = a.submission_set.all()
        if request.user.profile.role == 'Learner':
            submissions = submissions.filter(user=request.user)
        rows.append({'id': a.id, 'course_id':a.course_id,'status':a.status,'updated_at':a.updated_at.isoformat(),'owner':a.course.owner.first_name,'title': a.title, 'course': a.course.title, 'instructions': a.instructions, 'attachments':a.attachments,'due_at': a.due_at.isoformat(), 'total_marks': a.total_marks, 'submissions': list(submissions.values('id', 'user__first_name', 'body', 'status', 'marks', 'feedback', 'attachments', 'submitted_at'))})
    return rows


class AssignmentIn(Schema):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=20000)
    due_at: datetime
    total_marks: int = Field(gt=0, le=10000)
    status:str='Published'
    attachments:list[int]=Field(default_factory=list,max_length=20)


@api.post('/assignments')
@transaction.atomic
def create_assignment(request, data: AssignmentIn):
    require_capability(request.user,"assessment_write")
    course_access(request.user, data.course_id, True)
    if data.status not in ('Draft','Published'):raise HttpError(400,'Choose Draft or Published')
    if not data.title.strip() or not data.instructions.strip():raise HttpError(400,'Title and instructions are required')
    if timezone.is_naive(data.due_at):
        raise HttpError(400, 'Due date needs a timezone')
    validate_attachments(request.user,data.course_id,data.attachments)
    a = Assignment.objects.create(**scope(request.user), **data.dict())
    audit(request.user, 'assignment.create', a)
    return {'id': a.id}


class SubmissionIn(Schema):
    body: str = Field(default='', max_length=50000)
    attachments:list[int]=Field(default_factory=list,max_length=20)


@api.post('/assignments/{assignment_id}/submit')
@transaction.atomic
def submit_assignment(request, assignment_id: int, data: SubmissionIn):
    require_role(request.user, 'Learner')
    a = get_object_or_404(Assignment.objects.select_for_update(), pk=assignment_id)
    learner_course_access(request.user, a.course_id)
    if a.status!='Published':raise HttpError(400,'This assignment is not open for submissions')
    validate_attachments(request.user,a.course_id,data.attachments,own=True)
    if not data.body.strip() and not data.attachments:raise HttpError(400,'Write a response or attach your work')
    old = Submission.objects.filter(assignment=a, user=request.user).first()
    if old and old.status != 'Resubmit':
        raise HttpError(400, 'Already submitted. Ask your teacher to allow resubmission.')
    row, _ = Submission.objects.update_or_create(assignment=a, user=request.user, defaults={'body': data.body,'attachments':data.attachments, 'status': 'Late' if timezone.now() > a.due_at else 'Submitted', 'submitted_at': timezone.now(), 'marks': None, 'feedback': ''})
    audit(request.user, 'assignment.submit', row)
    return {'id': row.id, 'status': row.status}


class RubricCriterion(Schema):
    criterion:str=Field(min_length=1,max_length=200)
    marks:float=Field(ge=0,allow_inf_nan=False)
    max_marks:float|None=Field(default=None,gt=0,allow_inf_nan=False)


class MarkIn(Schema):
    marks: float = Field(ge=0,allow_inf_nan=False)
    feedback: str = Field(min_length=1, max_length=10000)
    rubric:list[RubricCriterion]=Field(default_factory=list,max_length=30)


@api.post('/submissions/{submission_id}/mark')
@transaction.atomic
def mark(request, submission_id: int, data: MarkIn):
    require_capability(request.user,"mark")
    require_role(request.user, 'Admin', 'Teacher','TA')
    s = get_object_or_404(Submission.objects.select_for_update(), pk=submission_id)
    course_access(request.user, s.assignment.course_id, True)
    if not data.feedback.strip() or any(not c.criterion.strip() for c in data.rubric):raise HttpError(400,'Feedback and rubric criteria cannot be blank')
    if s.status=='Resubmit':raise HttpError(400,'Wait for the learner to resubmit before marking')
    if data.marks > s.assignment.total_marks:
        raise HttpError(400, 'Marks exceed the assignment total')
    if data.rubric:
        import math
        if not math.isclose(sum(c.marks for c in data.rubric),data.marks,abs_tol=0.001):raise HttpError(400,'Rubric scores must add up to the awarded marks')
        if any(c.marks>(c.max_marks if c.max_marks is not None else s.assignment.total_marks) for c in data.rubric):raise HttpError(400,'A rubric score exceeds its criterion maximum')
        if all(c.max_marks is not None for c in data.rubric) and not math.isclose(sum(c.max_marks for c in data.rubric),s.assignment.total_marks,abs_tol=0.001):raise HttpError(400,'Rubric maximum marks must add up to the assignment total')
    s.marks, s.feedback, s.marker, s.status = data.marks, data.feedback, request.user, 'Marked'
    s.save()
    MarkingHistory.objects.create(submission=s,marker=request.user,marks=data.marks,feedback=data.feedback,rubric=[c.dict() for c in data.rubric])
    Reevaluation.objects.filter(submission=s,status='Requested').update(status='Reviewed')
    from .services import evaluate_credentials
    evaluate_credentials(s.user,s.assignment.course)
    audit(request.user, 'submission.mark', s, data.dict())
    return {'status': s.status}


def validate_attachments(user,course_id,ids,own=False):
    qs=Attachment.objects.filter(pk__in=ids,course_id=course_id,**scope(user))
    if own:qs=qs.filter(owner=user)
    if qs.count()!=len(set(ids)):raise HttpError(400,'One or more attachments are not accessible for this course')
    if not own:
        from .feature_api import attachment
        for pk in ids:attachment(user,pk,course_id)


@api.get('/quizzes')
@list_page
def quizzes(request):
    qs=Quiz.objects.filter(course__in=courses(request.user))
    if request.user.profile.role=='Learner':qs=qs.filter(status='Published')
    return list(qs.values('id','course_id','status','updated_at','title','time_limit_min','max_attempts','exam_type','correct_marks','wrong_marks'))


class QuestionIn(Schema):
    prompt: str = Field(min_length=1, max_length=5000)
    options: list[str] = Field(default_factory=list, max_length=8)
    answer: int = Field(default=0,ge=0)
    explanation: str = Field(default='', max_length=5000)
    topic:str=Field(default='General',max_length=100)
    difficulty:str=Field(default='Beginner',max_length=30)
    kind:str='Single choice'
    answer_set:list[int]=Field(default_factory=list,max_length=8)
    numeric_answer:float|None=None
    tolerance:float=Field(default=0,ge=0)
    correct_marks:float|None=Field(default=None,ge=0)
    wrong_marks:float|None=Field(default=None,le=0)


class QuizIn(Schema):
    course_id: int
    title: str = Field(min_length=1, max_length=200)
    time_limit_min: int = Field(gt=0, le=360)
    max_attempts: int = Field(gt=0, le=100)
    exam_type: str = 'Practice'
    correct_marks: float = Field(default=1, gt=0)
    wrong_marks: float = Field(default=0, le=0)
    status:str='Published'
    questions: list[QuestionIn] = Field(min_length=1, max_length=200)


@api.post('/quizzes')
@transaction.atomic
def create_quiz(request, data: QuizIn):
    require_capability(request.user,"assessment_write")
    course_access(request.user, data.course_id, True)
    if data.status not in ('Draft','Published'):raise HttpError(400,'Choose Draft or Published')
    import math
    if not math.isfinite(data.correct_marks) or not math.isfinite(data.wrong_marks):raise HttpError(400,'Marking rules must use finite numbers')
    for q in data.questions:
        from .assessment import validate_question
        validate_question(q)
    row = Quiz.objects.create(**scope(request.user), **data.dict(exclude={'questions'}))
    for q in data.questions:
        Question.objects.create(quiz=row, **q.dict())
    audit(request.user, 'quiz.create', row)
    return {'id': row.id}


def attempt_row(a):
    qs = a.quiz.question_set.all()
    weak={}
    if a.submitted_at:
        from .assessment import correct
        for q in qs:
            if not correct(q,a.answers.get(str(q.id))):weak[q.topic]=weak.get(q.topic,0)+1
    return {'weak_topics':weak,'id': a.id, 'quiz': a.quiz.title, 'status': a.status, 'score': a.score, 'answers': a.answers, 'deadline': (a.started_at + timedelta(minutes=a.quiz.time_limit_min)).isoformat(), 'questions': [{'id': q.id, 'prompt': q.prompt,'topic':q.topic, 'options': q.options,'kind':q.kind,'correct_marks':q.correct_marks if q.correct_marks is not None else a.quiz.correct_marks,'wrong_marks':q.wrong_marks if q.wrong_marks is not None else a.quiz.wrong_marks, **({'answer': q.answer,'answer_set':q.answer_set,'numeric_answer':q.numeric_answer,'tolerance':q.tolerance, 'explanation': q.explanation} if a.submitted_at else {})} for q in qs]}


@api.post('/quizzes/{quiz_id}/attempts')
@transaction.atomic
def start_attempt(request, quiz_id: int):
    require_role(request.user, 'Learner')
    q = get_object_or_404(Quiz.objects.select_for_update(), pk=quiz_id, status='Published')
    learner_course_access(request.user, q.course_id)
    active = Attempt.objects.filter(quiz=q, user=request.user, submitted_at=None).first()
    if active:
        if expired(active):
            active = finish_attempt(request.user, active.id)
        return attempt_row(active)
    if Attempt.objects.filter(quiz=q, user=request.user).count() >= q.max_attempts:
        raise HttpError(400, 'Maximum attempts reached')
    if not q.question_set.exists():raise HttpError(400,'This quiz has no questions. Ask the teacher to finish authoring it.')
    a = Attempt.objects.create(quiz=q, user=request.user)
    audit(request.user, 'quiz.start', a)
    return attempt_row(a)


class AnswersIn(Schema):
    answers: dict[str, Any]=Field(max_length=200)


@api.post('/attempts/{attempt_id}/save')
@transaction.atomic
def save_attempt(request, attempt_id: int, data: AnswersIn):
    a = get_object_or_404(Attempt.objects.select_for_update(), pk=attempt_id, user=request.user)
    if expired(a) or a.submitted_at:
        return attempt_row(finish_attempt(request.user, a.id))
    course_access(request.user,a.quiz.course_id)
    validate_answers(a.quiz, data.answers)
    a.answers = data.answers
    a.save()
    audit(request.user, 'quiz.autosave', a)
    return attempt_row(a)


@api.post('/attempts/{attempt_id}/submit')
def submit_attempt(request, attempt_id: int, data: AnswersIn):
    own=get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    course_access(request.user,own.quiz.course_id)
    return attempt_row(finish_attempt(request.user, attempt_id, data.answers))


@api.get('/results')
@list_page
def results(request):
    if request.user.profile.role not in ('Admin','Teacher','Coordinator','TA','Learner'):return []
    qs = Attempt.objects.filter(quiz__course__in=courses(request.user), submitted_at__isnull=False)
    if request.user.profile.role == 'Learner':
        qs = qs.filter(user=request.user)
    return [{'id': a.id, 'learner': a.user.first_name, 'quiz': a.quiz.title, 'score': a.score, 'submitted_at': a.submitted_at.isoformat(),'per_question':[{'topic':q.topic,'question':q.prompt,'correct':__import__('lms.assessment',fromlist=['correct']).correct(q,a.answers.get(str(q.id)))} for q in a.quiz.question_set.all()]} for a in qs.order_by('-submitted_at')]


@api.get('/credentials')
@list_page
def credentials(request):
    return [{'id': c.id, 'title': c.title, 'description': c.description, 'course': c.course.title, 'progress': progress(request.user, c.course), 'certificates': [{'code': str(cert.code), 'status': cert.status} for cert in Certificate.objects.filter(award__credential=c, award__user=request.user)]} for c in Credential.objects.filter(**scope(request.user), course__in=courses(request.user))]


@api.get('/certificates/verify/{code}', auth=None)
def verify(request, code: str):
    try:
        cert = Certificate.objects.select_related('award__user', 'award__credential').get(code=code)
    except (Certificate.DoesNotExist, ValueError, __import__('django.core.exceptions', fromlist=['ValidationError']).ValidationError):
        raise HttpError(404, 'Certificate not found. Check the verification code.')
    return {'status': cert.status, 'credential': cert.award.credential.title, 'learner': cert.award.user.first_name, 'issued_at': cert.award.awarded_at.isoformat()}


class AIIn(Schema):
    question: str = Field(default='', max_length=2000)
    lesson_id: int | None = None
    lesson_text: str = Field(default='', max_length=60000)


def ai_response(request, data, lesson_mode=False, summary=False):
    lesson = None
    if lesson_mode:
        if data.lesson_id:
            l = get_object_or_404(Lesson, pk=data.lesson_id)
            course_access(request.user, l.course_id)
            if request.user.profile.role == 'Learner' and l.status != 'Published':
                raise HttpError(403, 'You do not have access to this lesson')
            lesson = l.body
        else:
            lesson = data.lesson_text
        if not lesson or not lesson.strip():
            raise HttpError(400, 'Provide lesson content first')
    if not summary and not data.question.strip():
        raise HttpError(400, 'Enter a question')
    from .ai_limits import enforce_quota
    enforce_quota(request.user)
    try:
        text = ai_service.generate('' if summary else data.question, lesson)
    except HttpError:
        audit(request.user, 'ai.error', request.user, {'mode': 'Lesson' if lesson_mode else 'General', 'lesson_id': data.lesson_id})
        raise
    audit(request.user, 'ai.success', request.user, {'mode': 'Lesson' if lesson_mode else 'General', 'lesson_id': data.lesson_id})
    return {'text': text, 'disclosure': 'Generated by AI — please check'}


@api.post('/ai/chat')
def general_ai(request, data: AIIn):
    return ai_response(request, data)


@api.post('/ai/lesson/summary')
def summary_ai(request, data: AIIn):
    return ai_response(request, data, True, True)


@api.post('/ai/lesson/question')
def question_ai(request, data: AIIn):
    return ai_response(request, data, True)
