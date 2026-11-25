import io,json
from datetime import timedelta
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase,override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from .models import *


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RoleAndListTests(TestCase):
    def user(self,name,role,tenant='demo',campus='main'):
        u=User.objects.create_user(name,password='test',first_name=name)
        Profile.objects.create(user=u,role=role,tenant=tenant,campus=campus)
        return u

    def setUp(self):
        self.admin=self.user('admin','Admin');self.teacher=self.user('teacher','Teacher');self.student=self.user('student','Learner')
        self.author=self.user('author','Author');self.reviewer=self.user('reviewer','Reviewer');self.ta=self.user('assistant','TA');self.translator=self.user('translator','Translator')
        self.course=Course.objects.create(owner=self.teacher,title='Course',description='Description',status='Published',outcomes=['Learn'],modules=['One'])
        self.cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Cohort',capacity=40,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(user=self.student,cohort=self.cohort)
        self.lesson=Lesson.objects.create(course=self.course,author=self.teacher,title='Lesson',body='Source',status='Draft')
        self.client.force_login(self.admin)

    def post(self,path,body=None):return self.client.post('/api/lms'+path,body or {},content_type='application/json')
    def get(self,path,**query):
        from urllib.parse import urlsplit,parse_qsl
        url=urlsplit(path)
        return self.client.get('/api/lms'+url.path,{**dict(parse_qsl(url.query)),**query})
    def assign(self,user):
        self.client.force_login(self.admin)
        self.assertEqual(self.post(f'/staff/courses/{self.course.id}',{'user_id':user.id}).status_code,200)
        self.client.force_login(user)

    def test_author_reviewer_are_separate_assigned_roles(self):
        body={'course_id':self.course.id,'title':'Draft','body':'Source'}
        self.client.force_login(self.author)
        self.assertEqual(self.post('/content',body).status_code,403)
        self.assign(self.author)
        self.assertEqual(self.post('/content',body).status_code,200)
        self.assertEqual(self.post(f'/content/{self.lesson.id}/review',{'decision':'In Review'}).status_code,200)
        self.assertEqual(self.post(f'/content/{self.lesson.id}/review',{'decision':'Approved'}).status_code,403)
        self.assign(self.reviewer)
        self.assertEqual(self.post('/content',body).status_code,403)
        self.assertEqual(self.post(f'/content/{self.lesson.id}/review',{'decision':'Approved'}).status_code,200)
        self.assertEqual(self.post(f'/content/{self.lesson.id}/review',{'decision':'Published'}).status_code,200)
        self.assertTrue(AuditLog.objects.filter(action='content.review',user=self.reviewer).exists())

    def test_ta_can_mark_and_assist_class_but_cannot_author_or_manage_roles(self):
        assignment=Assignment.objects.create(course=self.course,title='Assignment',instructions='Task',due_at=timezone.now())
        submission=Submission.objects.create(assignment=assignment,user=self.student,body='Response')
        self.assign(self.ta)
        self.assertEqual(self.post(f'/submissions/{submission.id}/mark',{'marks':80,'feedback':'Good evidence'}).status_code,200)
        self.assertEqual(self.post(f'/features/submissions/{submission.id}/resubmit').status_code,200)
        self.assertEqual(self.post('/features/catalogue/live',{'course_id':self.course.id,'cohort_id':self.cohort.id,'title':'Session','start_at':timezone.now().isoformat(),'end_at':(timezone.now()+timedelta(hours=1)).isoformat()}).status_code,403)
        self.assertEqual(self.post('/courses',{'title':'No','description':'No','outcomes':['No'],'modules':['No']}).status_code,403)
        self.assertEqual(self.post('/quizzes',{'course_id':self.course.id,'title':'No','time_limit_min':10,'max_attempts':1,'questions':[{'prompt':'Pick','options':['A','B'],'answer':0}]}).status_code,403)
        self.assertEqual(self.get('/staff/directory').status_code,403)

    def test_translator_requires_course_and_reviewer_approves_translation(self):
        body={'lesson_id':self.lesson.id,'language':'Hindi','body':'Translation'}
        self.client.force_login(self.translator);self.assertEqual(self.post('/features/translations',body).status_code,403)
        self.assign(self.translator);response=self.post('/features/translations',body);self.assertEqual(response.status_code,200)
        pk=response.json()['id'];self.assertEqual(self.post(f'/features/translations/{pk}/approve').status_code,403)
        self.assign(self.reviewer);self.assertEqual(self.post(f'/features/translations/{pk}/approve').status_code,200)

    def test_assignment_revocation_and_foreign_campus_are_enforced_and_audited(self):
        self.assign(self.author)
        self.assertEqual(self.get('/content',list_page=1).json()['total'],1)
        self.client.force_login(self.admin);self.post(f'/staff/courses/{self.course.id}',{'user_id':self.author.id,'active':False})
        self.client.force_login(self.author);self.assertEqual(self.get('/content',list_page=1).json()['total'],0)
        self.assertEqual(self.post(f'/content/{self.lesson.id}/edit',{'course_id':self.course.id,'title':'Changed','body':'Changed'}).status_code,403)
        foreign=self.user('foreign','Author',campus='foreign')
        self.client.force_login(self.admin);self.assertEqual(self.post(f'/staff/courses/{self.course.id}',{'user_id':foreign.id}).status_code,404)
        self.assertEqual(CourseStaffAssignment.objects.count(),1)
        self.assertTrue(AuditLog.objects.filter(action='course.staff_revoke').exists())

    def test_multiple_narrow_roles_do_not_imply_teacher(self):
        self.author.profile.roles=['Author','Reviewer'];self.author.profile.save()
        self.assign(self.author)
        me=self.get('/auth/me').json()
        self.assertIn('content_write',me['permissions']);self.assertIn('content_review',me['permissions']);self.assertNotIn('assessment_write',me['permissions'])
        self.assertEqual(self.post('/courses',{'title':'No','description':'No','outcomes':['No'],'modules':['No']}).status_code,403)

    def test_private_attachments_cannot_be_laundered_into_content_or_library(self):
        private=Attachment.objects.create(course=self.course,owner=self.student,name='private.txt',mime='text/plain',file='private.txt')
        self.assign(self.author)
        self.assertEqual(self.post('/content',{'course_id':self.course.id,'title':'Draft','body':'Source','attachments':[private.id]}).status_code,403)
        librarian=self.user('librarian','Librarian');self.client.force_login(librarian)
        self.assertEqual(self.post('/features/catalogue/library',{'course_id':self.course.id,'title':'Resource','body':'Read','attachment_id':private.id}).status_code,403)
        self.assertFalse(LibraryResource.objects.exists())

    def test_reviewers_cannot_enumerate_other_learners_answers_or_certificates(self):
        q=Quiz.objects.create(course=self.course,title='Quiz')
        attempt=Attempt.objects.create(quiz=q,user=self.student,status='Submitted',submitted_at=timezone.now(),score=0)
        credential=Credential.objects.create(course=self.course,title='Credential',description='Earn')
        award=CredentialAward.objects.create(credential=credential,user=self.student);certificate=Certificate.objects.create(award=award)
        self.assign(self.reviewer)
        self.assertEqual(self.get(f'/final/attempts/{attempt.id}').status_code,403)
        self.assertEqual(self.get(f'/features/certificates/{certificate.id}/qr').status_code,403)

    def test_conflicting_learner_staff_actor_context_is_rejected(self):
        from .identity import resolve_user
        from ninja.errors import HttpError
        with self.settings(ENTRA_TENANT_ID='tenant'):
            with self.assertRaises(HttpError):resolve_user({'tid':'tenant','oid':'subject','roles':['Teacher','Learner']})
        self.teacher.profile.roles=['Teacher','Learner'];self.teacher.profile.save()
        self.client.force_login(self.teacher)
        self.assertEqual(self.get('/auth/me').status_code,401)

    def test_revoking_an_inactive_staff_assignment_is_allowed(self):
        self.assign(self.author)
        self.author.is_active=False;self.author.save()
        self.client.force_login(self.admin)
        response=self.post(f'/staff/courses/{self.course.id}',{'user_id':self.author.id,'active':False})
        self.assertEqual(response.status_code,200)
        self.assertFalse(CourseStaffAssignment.objects.get(user=self.author).is_active)

    def test_jitsi_moderation_uses_explicit_assistant_capability(self):
        import jwt,os
        from unittest.mock import patch
        from urllib.parse import urlsplit,parse_qs
        self.reviewer.profile.roles=['Reviewer','TA'];self.reviewer.profile.save()
        live=LiveClass.objects.create(course=self.course,cohort=self.cohort,teacher=self.teacher,title='Class',meeting_url='https://meet.jit.si/test-room',start_at=timezone.now()-timedelta(minutes=1),end_at=timezone.now()+timedelta(hours=1),status='Scheduled')
        self.assign(self.reviewer)
        with patch.dict(os.environ,{'JITSI_JWT_APP_ID':'test','JITSI_JWT_SECRET':'s'*64}):
            for user,moderator in [(self.reviewer,True),(self.student,False)]:
                self.client.force_login(user)
                response=self.post(f'/features/live/{live.id}/join')
                self.assertEqual(response.status_code,200,response.content)
                token=parse_qs(urlsplit(response.json()['meeting_url']).query)['jwt'][0]
                claims=jwt.decode(token,'s'*64,algorithms=['HS256'],audience='jitsi',issuer='test')
                self.assertEqual(claims['context']['user']['moderator'],moderator)

    def test_reconcile_evidence_supports_old_writers_without_changing_work(self):
        from django.core.management import call_command
        q=Quiz.objects.create(course=self.course,title='Quiz')
        question=Question.objects.create(quiz=q,prompt='Pick',options=['A','B'],answer=0,topic='Topic')
        attempt=Attempt(quiz=q,user=self.student,answers={str(question.id):0},score=1,status='Submitted',submitted_at=timezone.now())
        Attempt.objects.bulk_create([attempt])
        self.assertFalse(QuestionEvidence.objects.exists())
        for _ in range(2):call_command('rebuild_question_evidence',stdout=io.StringIO())
        self.assertEqual(QuestionEvidence.objects.count(),1)
        attempt.refresh_from_db();self.assertEqual(attempt.answers,{str(question.id):0});self.assertEqual(attempt.score,1)
        self.assertTrue(QuestionEvidence.objects.get().is_correct)

    def test_existing_cursor_cannot_restore_revoked_course_access(self):
        for i in range(24):Lesson.objects.create(course=self.course,author=self.teacher,title=f'Lesson {i}',body='Source')
        self.assign(self.reviewer);page=self.get('/content',list_page=1).json()
        self.client.force_login(self.admin);self.post(f'/staff/courses/{self.course.id}',{'user_id':self.reviewer.id,'active':False})
        self.client.force_login(self.reviewer)
        page=self.get('/content',list_page=1,cursor=page['next_cursor']).json()
        self.assertEqual(page['total'],0);self.assertEqual(page['items'],[])

    def test_my_path_filter_runs_before_the_first_page(self):
        for i in range(24):LearningPath.objects.create(course=self.course,title=f'A path {i}')
        path=LearningPath.objects.create(course=self.course,title='Z started path')
        PathProgress.objects.create(path=path,user=self.student)
        self.client.force_login(self.student)
        page=self.get('/features/catalogue/paths',list_page=1,started=1).json()
        self.assertEqual(page['total'],1);self.assertEqual(page['items'][0]['id'],path.id)

    def test_role_scoped_lists_are_not_cacheable(self):
        self.client.force_login(self.teacher)
        response=self.get('/courses',list_page=1)
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertIn('Cookie',response['Vary']);self.assertIn('Authorization',response['Vary'])

    def test_keyset_ties_backwards_insert_and_sql_limit_no_offset(self):
        for i in range(43):Assignment.objects.create(course=self.course,title='Same title',instructions='Task',due_at=timezone.now())
        self.client.force_login(self.teacher)
        with CaptureQueriesContext(connection) as queries:r=self.get('/assignments',list_page=1,sort='title').json()
        self.assertEqual(len(r['items']),20)
        sql='\n'.join(q['sql'].upper() for q in queries.captured_queries)
        self.assertIn('LIMIT 20',sql);self.assertNotIn('OFFSET',sql)
        first=[x['id'] for x in r['items']]
        Assignment.objects.create(course=self.course,title='AAA inserted before page',instructions='Task',due_at=timezone.now())
        second=self.get('/assignments',list_page=1,sort='title',cursor=r['next_cursor']).json()
        self.assertFalse(set(first)&{x['id'] for x in second['items']})
        backwards=self.get('/assignments',list_page=1,sort='title',cursor=second['previous_cursor']).json()
        self.assertEqual([x['id'] for x in backwards['items']],first)
        changed=self.get('/assignments',list_page=1,sort='-title',cursor=r['next_cursor']);self.assertEqual(changed.status_code,400)
        self.client.force_login(self.student);self.assertEqual(self.get('/assignments',list_page=1,sort='title',cursor=r['next_cursor']).status_code,400)

    def test_nullable_sort_is_stable_in_both_directions(self):
        for i in range(31):
            a=Assignment.objects.create(course=self.course,title=f'A{i}',instructions='Task',due_at=timezone.now())
            u=self.user('u'+str(i),'Learner');Enrolment.objects.create(user=u,cohort=self.cohort)
            Submission.objects.create(assignment=a,user=u,body='Response',marks=None if i%3==0 else i)
        self.client.force_login(self.teacher)
        for sort in ('marks','-marks'):
            first=self.get('/lists/submissions',sort=sort).json();second=self.get('/lists/submissions',sort=sort,cursor=first['next_cursor']).json()
            self.assertEqual(len(first['items'])+len(second['items']),31)
            self.assertFalse({x['id'] for x in first['items']}&{x['id'] for x in second['items']})
            back=self.get('/lists/submissions',sort=sort,cursor=second['previous_cursor']).json()
            self.assertEqual([x['id'] for x in back['items']],[x['id'] for x in first['items']])

    def test_all_catalogues_and_report_queries_share_sql_list_contract(self):
        now=timezone.now();file=Attachment.objects.create(course=self.course,owner=self.teacher,name='sample.mp4',mime='video/mp4',file='fixture.mp4')
        library=LibraryResource.objects.create(course=self.course,title='Resource',subject='Science',body='Read');LibraryLoan.objects.create(resource=library,user=self.student,status='Borrowed')
        live=LiveClass.objects.create(course=self.course,cohort=self.cohort,teacher=self.teacher,title='Class',start_at=now,end_at=now+timedelta(hours=1),status='Scheduled')
        Lecture.objects.create(course=self.course,title='Recording',attachment=file)
        path=LearningPath.objects.create(course=self.course,title='Path');PathStep.objects.create(path=path,kind='lesson',reference=self.lesson.id,position=1,title='Step')
        Activity.objects.create(course=self.course,title='Discussion',due_at=now+timedelta(days=1))
        CodingProblem.objects.create(course=self.course,title='Problem',topic='Math',tests=[{'input':'','output':'5'}])
        ProgrammingLab.objects.create(course=self.course,title='Lab',subject='Programming',steps=['One'])
        DigitalSkill.objects.create(course=self.course,title='Typing',steps=['One'])
        PracticePrompt.objects.create(course=self.course,title='Writing',module=172)
        q=Quiz.objects.create(course=self.course,title='Quiz');question=Question.objects.create(quiz=q,prompt='Choose',options=['A','B'],answer=0,topic='Topic')
        Attempt.objects.create(quiz=q,user=self.student,status='Submitted',submitted_at=now,answers={str(question.id):1},score=0)
        ExamPack.objects.create(course=self.course,title='NEET',subject='Physics',module=174,quiz=q)
        credential=Credential.objects.create(course=self.course,title='Credential',description='Earn');award=CredentialAward.objects.create(credential=credential,user=self.student);Certificate.objects.create(award=award)
        MarketplaceListing.objects.create(course=self.course,seller=self.teacher,price=0)
        announcement=Announcement.objects.create(course=self.course,title='News',body='Update',sender=self.teacher);Notification.objects.create(announcement=announcement,user=self.teacher)
        self.client.force_login(self.admin)
        paths=['/courses','/content','/cohorts','/assignments','/quizzes','/results','/credentials','/features/library/mine','/features/live/attendance/all','/features/translations','/features/glossary','/features/activities/participation/all','/features/work/coding','/features/work/labs','/features/work/practice','/features/papers?module=174','/features/marketplace','/features/marketplace/seller/dashboard','/features/tutor/flags','/features/submissions/history/all','/features/credentials/rules','/features/certificates','/features/notifications','/features/question-bank','/final/class-topics','/final/teaching-courses','/final/skill-progress','/staff/directory',f'/staff/courses/{self.course.id}']
        paths+=['/features/catalogue/'+kind for kind in ('library','live','lectures','paths','activities','coding','labs','skills','practice','exams')]
        paths+=['/lists/'+name+'?module=174' for name in ('attendance','participation','class_topics','exam_topics','exam_questions','skill_progress','path_steps','practice_insights','exam_insights','lesson_insights','library_usage','progress_courses','progress_learners','translation_coverage','roster','submissions')]
        for path in paths:
            with self.subTest(path=path):
                response=self.get(path,list_page=1)
                self.assertEqual(response.status_code,200,response.content)
                data=response.json();self.assertEqual(data['page_size'],20);self.assertIn('next_cursor',data);self.assertLessEqual(len(data['items']),20)
                if data['statuses']:
                    filtered=self.get(path,list_page=1,_status=data['statuses'][0])
                    self.assertEqual(filtered.status_code,200,filtered.content)
