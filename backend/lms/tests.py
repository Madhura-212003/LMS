from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone
from .models import *
from .services import enrol, complete, review, finish_attempt


class WorkflowTests(TestCase):
    def setUp(self):
        self.teacher = self.user('teacher', 'Teacher')
        self.learner = self.user('learner', 'Learner')
        self.other = self.user('other', 'Learner')
        self.foreign = self.user('foreign', 'Admin', 'other-tenant')
        self.course = Course.objects.create(title='Python', description='Learn', owner=self.teacher, status='Published')
        self.cohort = Cohort.objects.create(course=self.course, name='C1', capacity=1, teacher=self.teacher, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=30))
        self.lesson = Lesson.objects.create(course=self.course, title='Variables', body='A variable refers to a value.', status='Published', author=self.teacher)
        self.client.force_login(self.learner)

    def user(self, name, role, tenant='demo'):
        u=User.objects.create_user(name, password='test-password')
        Profile.objects.create(user=u, role=role, tenant=tenant)
        return u

    def post(self, url, body):
        return self.client.post('/api/lms'+url, data=body, content_type='application/json')

    def test_enrolment_capacity_and_idempotency(self):
        self.assertEqual(enrol(self.learner,self.cohort.id).status,'Enrolled')
        self.assertEqual(enrol(self.other,self.cohort.id).status,'Waitlisted')
        enrol(self.learner,self.cohort.id)
        self.assertEqual(Enrolment.objects.count(),2)

    def test_tenant_and_learner_access(self):
        self.assertEqual(self.client.get('/api/lms/courses/'+str(self.course.id)).status_code,403)
        enrol(self.learner,self.cohort.id)
        self.assertEqual(self.client.get('/api/lms/courses/'+str(self.course.id)).status_code,200)
        self.client.force_login(self.foreign)
        self.assertEqual(self.client.get('/api/lms/courses/'+str(self.course.id)).status_code,403)

    @patch('lms.ai_service.generate')
    def test_ai_denied_before_provider(self, provider):
        self.assertEqual(self.post('/ai/lesson/summary',{'lesson_id':self.lesson.id}).status_code,403)
        provider.assert_not_called()

    @patch('lms.ai_service.generate',return_value='A variable refers to a value. Quote: "A variable refers to a value."')
    def test_ai_grounding_and_limits(self, provider):
        enrol(self.learner,self.cohort.id)
        self.assertEqual(self.post('/ai/lesson/summary',{'lesson_id':self.lesson.id}).status_code,200)
        self.assertEqual(provider.call_args.args[1],self.lesson.body)
        provider.reset_mock()
        self.assertEqual(self.post('/ai/chat',{'question':'x'*2001}).status_code,400)
        provider.assert_not_called()
        self.assertFalse(AuditLog.objects.filter(details__icontains=self.lesson.body).exists())

    def test_review_state_machine_and_audit(self):
        self.lesson.status='Draft';self.lesson.save()
        self.client.force_login(self.teacher)
        url='/content/'+str(self.lesson.id)+'/review'
        self.assertEqual(self.post(url,{'decision':'Published'}).status_code,400)
        self.assertEqual(ContentReview.objects.count(),0)
        for state in ['In Review','Approved','Published']:
            self.assertEqual(self.post(url,{'decision':state}).status_code,200)
        self.assertEqual(ContentReview.objects.count(),3)
        self.assertEqual(AuditLog.objects.filter(action='content.review').count(),3)

    def test_completion_awards_once_and_verifies(self):
        enrol(self.learner,self.cohort.id)
        Credential.objects.create(course=self.course,title='Python award',description='Done')
        self.assertEqual(complete(self.learner,self.lesson),100)
        complete(self.learner,self.lesson)
        self.assertEqual(Certificate.objects.count(),1)
        self.assertEqual(CredentialAward.objects.count(),1)
        code=str(Certificate.objects.get().code)
        self.assertEqual(Client().get('/api/lms/certificates/verify/'+code).json()['status'],'Valid')
        self.assertEqual(Client().get('/api/lms/certificates/verify/invalid').status_code,404)

    def test_assignment_marking_validation(self):
        enrol(self.learner,self.cohort.id)
        a=Assignment.objects.create(course=self.course,title='Task',instructions='Explain',due_at=timezone.now()-timedelta(hours=1),total_marks=10)
        response=self.post('/assignments/'+str(a.id)+'/submit',{'body':'My work'})
        self.assertEqual(response.json()['status'],'Late')
        sid=response.json()['id']
        self.assertEqual(self.post('/submissions/'+str(sid)+'/mark',{'marks':5,'feedback':'Good'}).status_code,403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.post('/submissions/'+str(sid)+'/mark',{'marks':11,'feedback':'Good'}).status_code,400)
        self.assertEqual(self.post('/submissions/'+str(sid)+'/mark',{'marks':8,'feedback':'Good'}).status_code,200)
        self.assertEqual(Submission.objects.get().marks,8)

    def test_quiz_hides_answers_and_scores_negative_marks(self):
        enrol(self.learner,self.cohort.id)
        q=Quiz.objects.create(course=self.course,title='NEET mock',exam_type='NEET',correct_marks=4,wrong_marks=-1)
        a=Question.objects.create(quiz=q,prompt='Q1',options=['A','B'],answer=0)
        b=Question.objects.create(quiz=q,prompt='Q2',options=['A','B'],answer=0)
        started=self.post('/quizzes/'+str(q.id)+'/attempts',{}).json()
        self.assertNotIn('answer',started['questions'][0])
        response=self.post('/attempts/'+str(started['id'])+'/submit',{'answers':{str(a.id):0,str(b.id):1}})
        self.assertEqual(response.json()['score'],3)
        self.assertIn('answer',response.json()['questions'][0])

    def test_quiz_expiry_rejects_late_answers(self):
        q=Quiz.objects.create(course=self.course,title='Timed',time_limit_min=1,correct_marks=4)
        a=Question.objects.create(quiz=q,prompt='Q',options=['A','B'],answer=0)
        attempt=Attempt.objects.create(quiz=q,user=self.learner)
        Attempt.objects.filter(pk=attempt.id).update(started_at=timezone.now()-timedelta(minutes=2))
        result=finish_attempt(self.learner,attempt.id,{str(a.id):0})
        self.assertEqual(result.score,0)
        self.assertEqual(result.status,'Submitted')

    def test_five_failed_logins_lock_account(self):
        self.client.logout()
        for _ in range(5):
            self.assertEqual(self.post('/auth/login',{'email':'learner','password':'wrong'}).status_code,401)
        self.assertEqual(self.post('/auth/login',{'email':'learner','password':'test-password'}).status_code,429)

    def test_csrf_is_required_for_session_writes(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.teacher)
        r=client.post('/api/lms/courses',data={'title':'Bad'},content_type='application/json')
        self.assertEqual(r.status_code,403)

    def test_content_catalogue_lists_accessible_lessons_not_courses(self):
        enrol(self.learner, self.cohort.id)
        draft = Lesson.objects.create(course=self.course, title='Hidden draft', body='Not published', author=self.teacher)
        response = self.client.get('/api/lms/content').json()
        self.assertEqual(response['total'], 1)
        self.assertEqual(response['items'][0]['id'], self.lesson.id)
        self.assertEqual(response['items'][0]['body'], self.lesson.body)
        self.assertNotIn(draft.id, [x['id'] for x in response['items']])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/lms/content').json()['total'], 0)
        self.client.force_login(self.foreign)
        self.assertEqual(self.client.get('/api/lms/content').json()['total'], 0)

    def test_content_search_filter_and_review_queue(self):
        self.client.force_login(self.teacher)
        draft = Lesson.objects.create(course=self.course, title='Review me', body='Full content', status='In Review', author=self.teacher)
        response = self.client.get('/api/lms/content', {'status':'In Review','q':'Python'}).json()
        self.assertEqual([x['id'] for x in response['items']], [draft.id])
        self.assertEqual(self.client.get('/api/lms/content', {'q':'does not exist'}).json()['total'], 0)
        self.assertEqual(self.client.get('/api/lms/content', {'sort':'invalid'}).status_code, 400)

    def test_lesson_editor_preserves_reviewed_content(self):
        self.client.force_login(self.teacher)
        draft = Lesson.objects.create(course=self.course,title='Draft',body='Original',author=self.teacher)
        payload={'course_id':self.course.id,'title':'Revised','body':'Updated lesson','position':2}
        self.assertEqual(self.post('/content/'+str(draft.id)+'/edit',payload).status_code,200)
        draft.refresh_from_db()
        self.assertEqual(draft.body,'Updated lesson')
        self.assertEqual(AuditLog.objects.filter(action='lesson.edit').count(),1)
        self.assertEqual(self.post('/content/'+str(self.lesson.id)+'/edit',payload).status_code,400)
        self.client.force_login(self.learner)
        self.assertEqual(self.post('/content/'+str(draft.id)+'/edit',payload).status_code,403)
