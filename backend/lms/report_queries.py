"""Computed lists aggregate/filter/page in SQL, not after building Python report arrays."""
from django.db import models
from django.conf import settings
from django.db.models import Q,F,Value,Case,When,Count,Avg,Min,Sum,OuterRef,Subquery,Exists,CharField,FloatField,IntegerField
from django.db.models.functions import Cast,Concat,Coalesce,Round
from django.utils import timezone
from ninja.errors import HttpError
from .models import *
from .services import courses,scope,require_role
from .permissions import require,permits
from .keyset import ListQuery


class JsonLength(models.Func):
    output_field=IntegerField()
    function='jsonb_array_length'
    def as_sqlite(self,compiler,connection,**extra):return super().as_sql(compiler,connection,function='json_array_length',**extra)


def report_query(name,request,args):
    u=request.user;allowed=courses(u);role=u.profile.role;query=request.GET
    def arg(k,default=''):return args.get(k,query.get(k,default))
    def result(qs,sorts,search=(),default='id',status=None,key='pk'):
        return ListQuery(qs,lambda row:row,search,sorts,default,status,key=key)
    if name=='attendance':
        qs=LiveClass.objects.filter(course__in=allowed,cohort__enrolment__status__in=['Enrolled','Completed'])
        if role=='Learner':qs=qs.filter(cohort__enrolment__user=u)
        elif not permits(u,'teaching_read'):qs=qs.none()
        audience='cohort__enrolment__user'
        attendance=Attendance.objects.filter(live_class_id=OuterRef('pk'),user_id=OuterRef(audience))
        qs=qs.annotate(class_id=F('pk'),user_id=F(audience),cohort_name=F('cohort__name'),class_title=F('title'),learner=F(audience+'__first_name'),
            display_status=Case(When(status='Cancelled',then=Value('Cancelled')),default=Coalesce(Subquery(attendance.values('status')[:1]),Case(When(end_at__lt=timezone.now(),then=Value('Absent')),default=Value('Not joined')))),
            joined=Subquery(attendance.values('joined_at')[:1]),anchor=Concat(Cast('pk',CharField()),Value(':'),Cast('cohort__enrolment__pk',CharField())))
        qs=qs.values('class_id','user_id','cohort_name','class_title','learner','display_status','joined','anchor')
        p=result(qs,{'class_title':'class_title','learner':'learner','joined_at':'joined'},('class_title','learner'),'class_title','display_status','anchor')
        p.row=lambda r:{**r,'cohort':r['cohort_name'],'status':r['display_status'],'joined_at':r['joined'] if r['display_status']!='Absent' else None}
        return p
    if name not in ('library_usage','progress_courses','translation_coverage'):require(u,'teaching_read')
    if name=='translation_coverage':
        base=Q(lesson__status='Published')
        qs=allowed.annotate(total=Count('lesson',filter=base,distinct=True),translated=Count('lesson',filter=base&Q(lesson__translation__language=arg('language'),lesson__translation__status='Translated'),distinct=True)).annotate(display_status=Case(When(translated=0,then=Value('Untranslated')),When(total=F('translated'),then=Value('Complete')),default=Value('Partial'))).values('id','title','total','translated','display_status')
        p=result(qs,{'course':'title','total':'total','translated':'translated'},('title',),'course','display_status',key='id');p.row=lambda r:{**r,'course':r['title']};return p
    if name in ('class_topics','exam_topics'):
        qs=QuestionEvidence.objects.filter(attempt__quiz__course__in=allowed)
        if arg('cohort_id'):
            qs=qs.filter(attempt__user__enrolment__cohort_id=arg('cohort_id'),attempt__user__enrolment__status__in=['Enrolled','Completed'],attempt__quiz__course__cohort__id=arg('cohort_id')).distinct()
        if name=='exam_topics':qs=qs.filter(attempt__quiz__exampack__module=arg('module'))
        qs=qs.values('attempt__quiz__course_id','attempt__quiz__course__title','topic').annotate(anchor=Min('pk'),responses=Count('pk',distinct=True),correct=Count('pk',filter=Q(is_correct=True),distinct=True))
        cutoff=settings.PERSONALISATION_REVIEW_BELOW_PERCENT if name=='class_topics' else 70
        qs=qs.annotate(accuracy=Round(100.0*F('correct')/F('responses')),display_status=Case(When(correct__gte=F('responses')*cutoff/100.0,then=Value('Strength')),default=Value('Needs practice'),output_field=CharField()))
        p=result(qs,{'topic':'topic','course':'attempt__quiz__course__title','accuracy':'accuracy'},('topic','attempt__quiz__course__title'),'topic','display_status','anchor')
        p.row=lambda r:{**r,'course':r['attempt__quiz__course__title'],'status':r['display_status']};return p
    if name=='exam_questions':
        qs=QuestionEvidence.objects.filter(attempt__quiz__course__in=allowed,attempt__quiz__exampack__module=arg('module')).values('question_id','question__prompt','topic')
        qs=qs.annotate(anchor=Min('pk'),responses=Count('pk'),incorrect=Count('pk',filter=Q(is_correct=False)))
        p=result(qs,{'question':'question__prompt','topic':'topic','incorrect':'incorrect'},('question__prompt','topic'),'-incorrect','topic',key='anchor');p.row=lambda r:{**r,'question':r['question__prompt']};return p
    if name in ('skill_progress','participation'):
        kind='digitalskill' if name=='skill_progress' else 'activity'
        qs=Enrolment.objects.filter(cohort__course__in=allowed,status__in=['Enrolled','Completed'],**{'cohort__course__'+kind+'__isnull':False})
        target='cohort__course__'+kind
        qs=qs.annotate(item_id=F(target+'__pk'),title=F(target+'__title'),learner=F('user__first_name'),cohort_name=F('cohort__name'),anchor=Concat(Cast('pk',CharField()),Value(':'),Cast(target+'__pk',CharField())))
        if name=='skill_progress':
            records=DigitalSkillProgress.objects.filter(skill_id=OuterRef(target+'__pk'),user_id=OuterRef('user_id')).annotate(length=JsonLength('completed_steps'))
            qs=qs.annotate(completed=Coalesce(Subquery(records.values('length')[:1]),Value(0)),total=JsonLength(target+'__steps'))
            qs=qs.annotate(display_status=Case(When(completed=0,then=Value('Not started')),When(completed=F('total'),then=Value('Completed')),default=Value('In progress')))
            qs=qs.values('anchor','title','learner','cohort_name','completed','total','display_status')
            p=result(qs,{'title':'title','learner':'learner','completed':'completed'},('title','learner','cohort_name'),'title','display_status','anchor')
            p.row=lambda r:{**r,'skill':r['title'],'cohort':r['cohort_name'],'status':r['display_status']};return p
        posts=ActivityPost.objects.filter(activity_id=OuterRef(target+'__pk'),user_id=OuterRef('user_id')).values('activity_id').annotate(n=Count('pk'))
        qs=qs.annotate(posts=Coalesce(Subquery(posts.values('n')[:1]),Value(0))).annotate(display_status=Case(When(posts=0,then=Value('No contributions')),default=Value('Contributed')))
        qs=qs.values('anchor','title','learner','cohort_name','posts','display_status')
        p=result(qs,{'title':'title','learner':'learner','posts':'posts'},('title','learner','cohort_name'),'title','display_status',key='anchor')
        p.row=lambda r:{**r,'activity__title':r['title'],'user__first_name':r['learner'],'cohort':r['cohort_name']};return p
    if name=='path_steps':
        qs=PathStep.objects.filter(path__course__in=allowed,path__course__cohort__enrolment__status__in=['Enrolled','Completed'],**({'path__course__cohort__pk':arg('cohort_id')} if arg('cohort_id') else {}))
        if arg('path_id'):qs=qs.filter(path_id=arg('path_id'))
        user='path__course__cohort__enrolment__user_id'
        qs=qs.annotate(path_title=F('path__title'),learner=F(user.replace('_id','')+'__first_name'),cohort_name=F('path__course__cohort__name'),anchor=Concat(Cast('pk',CharField()),Value(':'),Cast('path__course__cohort__enrolment__pk',CharField())))
        lesson=Exists(LessonCompletion.objects.filter(lesson_id=OuterRef('reference'),user_id=OuterRef(user)))
        quiz=Exists(Attempt.objects.filter(quiz_id=OuterRef('reference'),user_id=OuterRef(user),status='Submitted',score__gt=0))
        lab=Exists(LabSession.objects.filter(lab_id=OuterRef('reference'),user_id=OuterRef(user),status='Completed'))
        total=Lesson.objects.filter(course_id=OuterRef('reference'),status='Published').values('course_id').annotate(n=Count('pk')).values('n')[:1]
        done=LessonCompletion.objects.filter(lesson__course_id=OuterRef('reference'),lesson__status='Published',user_id=OuterRef(user)).values('lesson__course_id').annotate(n=Count('pk')).values('n')[:1]
        qs=qs.annotate(path_started=Exists(PathProgress.objects.filter(path_id=OuterRef('path_id'),user_id=OuterRef(user))))
        qs=qs.annotate(course_total=Coalesce(Subquery(total),Value(0)),course_done=Coalesce(Subquery(done),Value(0)))
        qs=qs.annotate(completed=Case(When(kind='lesson',then=lesson),When(kind='quiz',then=quiz),When(kind='lab',then=lab),When(kind='course',course_total__gt=0,course_done=F('course_total'),then=Value(True)),default=Value(False),output_field=models.BooleanField()))
        qs=qs.annotate(display_status=Case(When(completed=True,then=Value('Completed')),default=Value('Pending'))).values('anchor','path_title','learner','cohort_name','title','position','completed','display_status','path_started')
        p=result(qs,{'path':'path_title','learner':'learner','position':'position'},('path_title','learner','cohort_name','title'),'path','display_status','anchor');p.row=lambda r:{**r,'path':r['path_title'],'cohort':r['cohort_name'],'status':r['display_status'],'path_state':'Started' if r['path_started'] else 'Not started'};return p
    if name=='practice_insights':
        qs=PracticePrompt.objects.filter(course__in=allowed,module=arg('module')).annotate(submissions=Count('practicesubmission'),average=Avg('practicesubmission__score')).values('id','title','submissions','average')
        p=result(qs,{'title':'title','submissions':'submissions','average':'average'},('title',),'title','status',key='id');p.row=lambda r:{**r,'prompt__title':r['title']};return p
    if name=='exam_insights':
        qs=ExamPack.objects.filter(course__in=allowed,module=arg('module')).annotate(attempts=Count('quiz__attempt',filter=Q(quiz__attempt__submitted_at__isnull=False)),average=Avg('quiz__attempt__score')).values('id','title','subject','attempts','average')
        return result(qs,{'title':'title','subject':'subject','average':'average','attempts':'attempts'},('title','subject'),'title','status',key='id')
    if name=='lesson_insights':
        active=Enrolment.objects.filter(cohort__course_id=OuterRef('lesson__course_id'),user_id=OuterRef('user_id'),status__in=['Enrolled','Completed'])
        learner_filter=Q(cohort__enrolment__status__in=['Enrolled','Completed'])
        qs=allowed
        if arg('cohort_id'):
            qs=qs.filter(cohort__pk=arg('cohort_id'))
            active=active.filter(cohort_id=arg('cohort_id'))
            learner_filter &= Q(cohort__pk=arg('cohort_id'))
        completed=LessonCompletion.objects.filter(lesson__course_id=OuterRef('pk'),lesson__status='Published').filter(Exists(active)).values('lesson__course_id').annotate(n=Count('pk')).values('n')[:1]
        qs=qs.annotate(learners=Count('cohort__enrolment__user',filter=learner_filter,distinct=True),lessons=Count('lesson',filter=Q(lesson__status='Published'),distinct=True),completed_lessons=Coalesce(Subquery(completed),Value(0))).values('id','title','learners','lessons','completed_lessons')
        return result(qs,{'title':'title','learners':'learners','lessons':'lessons','completed_lessons':'completed_lessons'},('title',),'title','status',key='id')
    if name in ('progress_courses','progress_learners'):
        qs=allowed if name=='progress_courses' else Enrolment.objects.filter(cohort__course__in=allowed,status__in=['Enrolled','Completed'])
        course_ref='pk' if name=='progress_courses' else 'cohort__course_id'
        total=Lesson.objects.filter(course_id=OuterRef(course_ref),status='Published').values('course_id').annotate(n=Count('pk')).values('n')[:1]
        completed=LessonCompletion.objects.filter(lesson__course_id=OuterRef(course_ref),lesson__status='Published')
        completed=completed.filter(user=u) if name=='progress_courses' else completed.filter(user_id=OuterRef('user_id'))
        completed=completed.values('lesson__course_id').annotate(n=Count('pk')).values('n')[:1]
        qs=qs.annotate(total=Coalesce(Subquery(total),Value(0)),done=Coalesce(Subquery(completed),Value(0))).annotate(progress=Case(When(total=0,then=Value(0.0)),default=Round(100.0*F('done')/F('total')),output_field=FloatField()))
        qs=qs.annotate(display_status=Case(When(progress=0,then=Value('Not started')),When(progress=100,then=Value('Completed')),default=Value('In progress')))
        if name=='progress_courses':qs=qs.values('id','title','progress','display_status');return result(qs,{'title':'title','progress':'progress'},('title',),'title','display_status',key='id')
        qs=qs.annotate(learner=F('user__first_name'),course_title=F('cohort__course__title')).values('id','learner','course_title','progress','display_status')
        p=result(qs,{'learner':'learner','course':'course_title','progress':'progress'},('learner','course_title'),'learner','display_status',key='id');p.row=lambda r:{**r,'course':r['course_title']};return p
    if name=='library_usage':
        require_role(u,'Admin','Librarian')
        qs=LibraryResource.objects.filter(**scope(u)).annotate(usage=Count('libraryloan')).annotate(display_status=Case(When(usage=0,then=Value('Unused')),default=Value('Used'))).values('id','title','usage','display_status')
        return result(qs,{'title':'title','usage':'usage'},('title',),'-usage','display_status',key='id')
    raise HttpError(404,'Unknown list')
