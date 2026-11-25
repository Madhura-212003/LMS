"""List ownership: authorized ORM query, supported fields and per-row serializer."""
from django.db.models import Q,F,Value,Case,When,CharField,Count,Avg,Sum,OuterRef,Subquery,Exists,FloatField,Min
from django.db.models.functions import Coalesce,Cast,Concat
from django.utils import timezone
from ninja.errors import HttpError
from .models import *
from .services import courses,scope,require_role,progress
from .permissions import permits,require
from .keyset import ListQuery


def plan(qs,row,search=(),sorts=None,default='id',status=None,**kwargs):
    return ListQuery(qs,row,search,sorts or {'id':'pk'},default,status,**kwargs)


def query_for(name,request,args=None):
    from .api import course_row
    from .feature_api import serial,item_row,scoped,preferences
    args=args or {};u=request.user;allowed=courses(u);role=u.profile.role
    def arg(key,default=''):return args.get(key,request.GET.get(key,default))
    def own(qs,relation='user'):
        if role=='Learner':return qs.filter(**{relation:u})
        return qs if permits(u,'teaching_read') else qs.none()
    common={'title':'title','updated_at':'updated_at','id':'pk'}
    if name in ('directory','assigned'):
        require(u,'staff_assign')
        from .permissions import roles
        if name=='directory':
            qs=__import__('django.contrib.auth.models',fromlist=['User']).User.objects.filter(is_active=True,profile__tenant=u.profile.tenant,profile__campus=u.profile.campus).exclude(profile__role='Learner').select_related('profile')
            return plan(qs,lambda x:{'id':x.id,'name':x.first_name or x.username,'roles':sorted(roles(x))},('first_name','username','profile__role'),{'name':'first_name','role':'profile__role','id':'pk'},'name','profile__role',status_label='Primary role')
        from .services import course_access
        course_access(u,arg('course_id'))
        qs=CourseStaffAssignment.objects.filter(course_id=arg('course_id')).select_related('user__profile').annotate(display_status=Case(When(is_active=True,then=Value('Active')),default=Value('Revoked')))
        return plan(qs,lambda x:{'id':x.id,'user_id':x.user_id,'name':x.user.first_name,'roles':sorted(roles(x.user)),'active':x.is_active},('user__first_name','user__profile__role'),{'name':'user__first_name','updated_at':'updated_at','id':'pk'},'name','display_status')
    if name in ('list_courses','teaching_courses'):
        if name=='teaching_courses':require(u,'course_manage')
        qs=courses(u,str(arg('catalogue','false')).lower() in ('true','1'))
        if name=='list_courses' and role=='Learner' and str(arg('mine','false')).lower() in ('true','1'):
            qs=Course.objects.filter(**scope(u),is_deleted=False).filter(Exists(Enrolment.objects.filter(cohort__course_id=OuterRef('pk'),user=u,status__in=['Enrolled','Completed','Waitlisted'])))
        total=Lesson.objects.filter(course_id=OuterRef('pk'),status='Published').values('course_id').annotate(n=Count('pk')).values('n')[:1]
        done=LessonCompletion.objects.filter(lesson__course_id=OuterRef('pk'),lesson__status='Published',user=u).values('lesson__course_id').annotate(n=Count('pk')).values('n')[:1]
        qs=qs.annotate(_total=Coalesce(Subquery(total),Value(0)),_done=Coalesce(Subquery(done),Value(0))).annotate(_progress=Case(When(_total=0,then=Value(0.0)),default=100.0*F('_done')/F('_total'),output_field=FloatField()))
        def course_item(c):
            row=course_row(c,u)
            if name=='teaching_courses':
                from .course_workflow import teaching_metrics
                row['metrics']=teaching_metrics(c)
            return row
        return plan(qs,course_item,('title','description','owner__first_name'),{**common,'progress':'_progress'},'title','status',filters={'subject':'subject','level':'level'},facets=('subject','level'))
    if name=='content_reviews':
        from .services import course_access
        if not (permits(u,'content_write') or permits(u,'content_review')):
            raise HttpError(403,'Content review history requires an author or reviewer role')
        lesson=Lesson.objects.filter(pk=arg('lesson_id')).first()
        if not lesson:raise HttpError(404,'Lesson not found')
        course_access(u,lesson.course_id)
        qs=ContentReview.objects.filter(lesson=lesson).select_related('reviewer')
        return plan(qs,lambda r:{'id':r.id,'decision':r.decision,'comment':r.comment,'created_at':r.created_at.isoformat(),'reviewer':r.reviewer.first_name or r.reviewer.username},('comment','reviewer__first_name'),{'created_at':'created_at','id':'pk'},'-created_at','decision')
    if name=='path_options':
        from .path_workflow import STEP_MODELS
        require(u,'path_manage');kind=arg('kind','lesson');model=STEP_MODELS.get(kind)
        if not model:raise HttpError(400,'Choose a supported activity kind')
        qs=allowed if model is Course else model.objects.filter(course__in=allowed).select_related('course')
        return plan(qs,lambda obj:{'id':obj.id,'kind':kind,'title':obj.title,'status':obj.status,'course_id':obj.id if model is Course else obj.course_id,'course_title':obj.title if model is Course else obj.course.title},('title',) if model is Course else ('title','course__title'),common,'title','status')
    if name=='list_content':
        qs=Lesson.objects.filter(course__in=allowed).select_related('course','author')
        if role=='Librarian':qs=qs.none()
        if role=='Learner':qs=qs.filter(status='Published')
        def row(l):return {**serial(l),'course_id':l.course_id,'course':l.course.title,'owner':l.author.first_name,'completed':LessonCompletion.objects.filter(lesson=l,user=u).exists()}
        return plan(qs,row,('title','course__title'),common,'title','status')
    if name=='catalogue':
        from .feature_api import CATALOGUES
        kind=arg('kind');model=CATALOGUES.get(kind)
        if not model:raise HttpError(404,'Unknown catalogue')
        qs=scoped(u,model).select_related('course','course__owner')
        if role=='Learner':
            qs=qs.filter(cohort__enrolment__user=u,cohort__enrolment__status__in=['Enrolled','Completed']).exclude(status='Draft') if kind=='live' else qs.filter(status='Published')
        if arg('module',0) and kind in ('practice','exams'):qs=qs.filter(module=int(arg('module')))
        if kind=='paths' and str(arg('started','')) in ('1','true'):qs=qs.filter(pathprogress__user=u)
        if kind=='live':qs=qs.annotate(display_status=Case(When(status='Scheduled',end_at__lte=timezone.now(),then=Value('Ended')),When(status='Scheduled',start_at__lte=timezone.now(),then=Value('Live')),default=F('status'),output_field=CharField()))
        names={f.name for f in model._meta.fields}
        facets=tuple(k for k in ('subject','topic','difficulty','language','level','resource_type') if k in names)
        filters={k:k for k in facets};filters['teacher']='teacher__first_name__icontains' if kind=='live' else 'course__owner__first_name__icontains'
        return plan(qs,lambda x:item_row(u,kind,x),('title','description','course__title')+(('topic',) if kind=='lectures' else ()),{**common,**({'start_at':'start_at'} if kind=='live' else {})},'start_at' if kind=='live' else 'title','display_status' if kind=='live' else 'status',filters=filters,facets=facets)
    if name=='cohorts':
        qs=Cohort.objects.filter(course__in=allowed).select_related('course','teacher').annotate(display_status=Case(When(end_date__lt=timezone.localdate(),then=Value('Ended')),When(start_date__gt=timezone.localdate(),then=Value('Upcoming')),default=Value('Active')))
        if role=='Learner':qs=qs.filter(enrolment__user=u,enrolment__status__in=['Enrolled','Completed'])
        def row(c):
            from .course_workflow import cohort_row
            return {**cohort_row(c,u),'enrolments':[]}
        return plan(qs,row,('name','course__title'),{'name':'name','start_date':'start_date','capacity':'capacity','id':'pk'},'name','display_status')
    if name=='roster':
        require(u,'teaching_read');qs=Enrolment.objects.filter(cohort__course__in=allowed)
        if arg('cohort_id'):qs=qs.filter(cohort_id=arg('cohort_id'))
        return plan(qs.select_related('user','cohort'),lambda e:{'id':e.id,'user_id':e.user_id,'name':e.user.first_name,'cohort':e.cohort.name,'status':e.status},('user__first_name','cohort__name'),{'name':'user__first_name','cohort':'cohort__name','enrolled_at':'enrolled_at','id':'pk'},'name','status')
    if name=='assignments':
        qs=Assignment.objects.filter(course__in=allowed).select_related('course__owner')
        if not permits(u,'teaching_read') and role!='Learner':qs=qs.none()
        if role=='Learner':qs=qs.filter(status='Published')
        def row(a):
            subs=a.submission_set.none()
            if role=='Learner':subs=a.submission_set.filter(user=u)
            return {**serial(a),'course_id':a.course_id,'course':a.course.title,'owner':a.course.owner.first_name,'submissions':list(subs.values('id','user__first_name','body','status','marks','feedback','attachments','submitted_at'))}
        return plan(qs,row,('title','course__title'),{**common,'due_at':'due_at'},'due_at','status')
    if name=='submissions':
        qs=own(Submission.objects.filter(assignment__course__in=allowed)).select_related('user','assignment')
        if arg('queue')=='marking':qs=qs.filter(status__in=['Submitted','Late','Re-evaluation requested'])
        elif arg('queue')=='feedback':qs=qs.filter(status__in=['Marked','Re-evaluation requested'])
        return plan(qs,lambda s:{**serial(s),'learner':s.user.first_name,'title':s.assignment.title,'course_id':s.assignment.course_id,'total_marks':s.assignment.total_marks},('assignment__title','user__first_name'),{'title':'assignment__title','learner':'user__first_name','submitted_at':'submitted_at','marks':'marks','id':'pk'},'-submitted_at','status')
    if name=='quizzes':
        qs=Quiz.objects.filter(course__in=allowed)
        if role=='Learner':qs=qs.filter(status='Published')
        return plan(qs,lambda x:{**serial(x),'course_id':x.course_id},('title','course__title'),common,'title','status')
    if name=='results':
        from .assessment import correct
        qs=own(Attempt.objects.filter(quiz__course__in=allowed,submitted_at__isnull=False)).select_related('user','quiz')
        return plan(qs,lambda a:{'id':a.id,'learner':a.user.first_name,'quiz':a.quiz.title,'score':a.score,'submitted_at':a.submitted_at.isoformat(),'per_question':[{'topic':q.topic,'question':q.prompt,'correct':correct(q,a.answers.get(str(q.pk)))} for q in a.quiz.question_set.all()]},('quiz__title','user__first_name'),{'quiz':'quiz__title','learner':'user__first_name','score':'score','submitted_at':'submitted_at','id':'pk'},'-submitted_at','status')
    if name in ('credentials','rules'):
        qs=Credential.objects.filter(course__in=allowed,**scope(u)).select_related('course')
        qs=qs.annotate(display_status=Coalesce(Subquery(CredentialRule.objects.filter(credential_id=OuterRef('pk')).values('trigger')[:1]),Value('Course completion'))) if name=='rules' else qs.annotate(display_status=Case(When(Exists(CredentialAward.objects.filter(credential_id=OuterRef('pk'),user=u)),then=Value('Earned')),default=Value('Not earned')))
        def row(c):
            if name=='rules':return {**serial(c),'rule':serial(CredentialRule.objects.get(credential=c)) if CredentialRule.objects.filter(credential=c).exists() else {'trigger':'Course completion','threshold':100}}
            return {'id':c.id,'title':c.title,'description':c.description,'course':c.course.title,'progress':progress(u,c.course),'certificates':[{'code':str(t.code),'status':t.status} for t in Certificate.objects.filter(award__credential=c,award__user=u)]}
        return plan(qs,row,('title','course__title'),common,'title','display_status',status_label='Trigger' if name=='rules' else 'Achievement')
    if name=='my_library':
        qs=LibraryLoan.objects.filter(user=u,resource__course__in=allowed).exclude(status='Returned').select_related('resource__course__owner')
        if role=='Learner':qs=qs.filter(Q(resource__status='Published')|Q(status='Borrowed'))
        return plan(qs,lambda x:item_row(u,'library',x.resource),('resource__title','resource__subject'),{'title':'resource__title','due_at':'due_at','id':'pk'},'title','status')
    if name=='translations':
        lang=arg('language') or preferences(request)['language'];qs=Lesson.objects.filter(course__in=allowed).select_related('course')
        if role=='Learner':qs=qs.filter(status='Published')
        qs=qs.annotate(translation_status=Coalesce(Subquery(Translation.objects.filter(lesson_id=OuterRef('pk'),language=lang).values('status')[:1]),Value('Not translated')))
        def row(l):
            t=Translation.objects.filter(lesson=l,language=lang).first()
            return {'id':l.id,'title':l.title,'course_id':l.course_id,'course':l.course.title,'original':l.body,'source_updated_at':l.updated_at.isoformat(),'language':lang,'status':l.translation_status,'translation':serial(t) if t and (t.status=='Translated' or role!='Learner') else None}
        return plan(qs,row,('title','course__title'),common,'title','translation_status')
    if name=='glossary':return plan(GlossaryTerm.objects.filter(**scope(u)),serial,('term','definition'),{'term':'term','language':'language','id':'pk'},'term','language',filters={'language':'language'},status_label='Language')
    if name=='submitted_work':
        kind=arg('kind');mapping={'coding':(CodingAttempt,'problem'),'labs':(LabSession,'lab'),'practice':(PracticeSubmission,'prompt')}
        if kind not in mapping:raise HttpError(404,'Unknown work type')
        model,related=mapping[kind];qs=own(model.objects.filter(**{related+'__course__in':allowed})).select_related('user',related)
        if kind=='practice' and arg('module',0):qs=qs.filter(prompt__module=int(arg('module')))
        if kind=='coding':qs=qs.annotate(display_status=Case(When(score=100,then=Value('Passed')),default=Value('Needs practice')))
        return plan(qs,lambda x:{**serial(x),'learner':x.user.first_name,'title':getattr(x,related).title,'course_id':getattr(x,related).course_id},(related+'__title','user__first_name'),{'title':related+'__title','learner':'user__first_name','score':'score','id':'pk'},'-id','display_status' if kind=='coding' else 'status')
    if name=='papers':
        qs=PreviousPaper.objects.filter(module=arg('module'),attachment__course__in=allowed,**scope(u))
        return plan(qs,serial,('title',),{'title':'title','year':'year','id':'pk'},'-year','year',filters={'year':'year'},status_label='Year')
    if name in ('marketplace','seller_dashboard'):
        qs=MarketplaceListing.objects.filter(**scope(u)).select_related('course__owner','seller').annotate(price_group=Case(When(price=0,then=Value('Free')),default=Value('Paid')),purchase_count=Count('marketplacepurchase'),earnings=Coalesce(Sum('marketplacepurchase__amount'),Value(0),output_field=models.DecimalField(max_digits=16,decimal_places=2)))
        if name=='seller_dashboard':
            require_role(u,'Admin','Teacher','Seller')
            if role!='Admin':qs=qs.filter(seller=u)
            row=lambda l:{'id':l.id,'title':l.course.title,'price':str(l.price),'enrolments':l.purchase_count,'preview_earnings':str(l.earnings)}
        else:
            qs=qs.filter(status='Published',course__status='Published',course__is_deleted=False)
            if str(arg('free','false')).lower() in ('true','1'):qs=qs.filter(price=0)
            def row(l):return {'id':l.id,'course_id':l.course_id,'title':l.course.title,'description':l.course.description,'syllabus':l.course.modules,'teacher':l.course.owner.first_name,'seller':l.seller.first_name,'price':str(l.price),'duration_minutes':l.course.duration_minutes,'rating':l.course.coursereview_set.aggregate(v=Avg('rating'))['v'],'reviews':[{'learner':x.user.first_name,'rating':x.rating,'body':x.body,'updated_at':x.updated_at.isoformat()} for x in l.course.coursereview_set.select_related('user').order_by('-updated_at')[:20]],'status':l.status,'owner':l.seller.first_name,'updated_at':l.updated_at.isoformat(),'enrolled':allowed.filter(pk=l.course_id).exists(),'purchased':MarketplacePurchase.objects.filter(listing=l,user=u).exists()}
        return plan(qs,row,('course__title','course__description','seller__first_name'),{'title':'course__title','price':'price','updated_at':'updated_at','id':'pk'},'title','price_group',status_label='Price')
    if name=='tutor_flags':
        from .tutor_workflow import flags_for
        qs=flags_for(u)
        return plan(qs,lambda x:{**serial(x),'course_title':x.course.title,'learner':x.user.first_name},('course__title','user__first_name','reason'),common,'-updated_at','status')
    if name=='marking_history':
        qs=MarkingHistory.objects.filter(submission__assignment__course__in=allowed)
        if arg('submission_id'):qs=qs.filter(submission_id=arg('submission_id'))
        if role=='Learner':qs=qs.filter(submission__user=u)
        elif not permits(u,'teaching_read'):qs=qs.none()
        return plan(qs.select_related('submission__assignment'),lambda x:{**serial(x),'assignment':x.submission.assignment.title},('submission__assignment__title',),{'assignment':'submission__assignment__title','marks':'marks','created_at':'created_at','id':'pk'},'-created_at','marker__first_name',status_label='Marker')
    if name=='certificate_list':
        qs=Certificate.objects.filter(award__credential__course__in=allowed).select_related('award__user','award__credential')
        if role=='Learner':qs=qs.filter(award__user=u)
        elif not permits(u,'teaching_read'):qs=qs.none()
        return plan(qs,lambda c:{'id':c.id,'code':str(c.code),'status':c.status,'title':c.award.credential.title,'learner':c.award.user.first_name,'issued_at':c.award.awarded_at.isoformat()},('award__credential__title','award__user__first_name'),{'title':'award__credential__title','learner':'award__user__first_name','issued_at':'award__awarded_at','id':'pk'},'-issued_at','status')
    if name=='notifications':
        qs=Notification.objects.filter(user=u,announcement__course__in=allowed).select_related('announcement__course').annotate(display_status=Case(When(read_at=None,then=Value('Unread')),default=Value('Read'),output_field=CharField()))
        return plan(qs,lambda n:{'id':n.id,'title':n.announcement.title,'body':n.announcement.body,'read':n.read_at is not None,'course':n.announcement.course.title,'status':n.display_status},('announcement__title','announcement__body'),{'title':'announcement__title','read_at':'read_at','id':'pk'},'-id','display_status')
    if name=='question_bank':
        require(u,'assessment_write');qs=Question.objects.filter(quiz__course__in=allowed).select_related('quiz')
        def row(x):return {**serial(x),'quiz_id':x.quiz_id,'course_id':x.quiz.course_id,'quiz':x.quiz.title}
        return plan(qs,row,('prompt','topic'),{'prompt':'prompt','topic':'topic','difficulty':'difficulty','id':'pk'},'id','kind',status_label='Question type',filters={'topic':'topic__icontains','difficulty':'difficulty'})
    from .report_queries import report_query
    return report_query(name,request,args)
