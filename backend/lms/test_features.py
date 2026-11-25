import tempfile
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import *
from .teaching_runner import run,RunnerError
from .services import evaluate_credentials


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FeatureWorkflowTests(TestCase):
    def setUp(self):
        self.teacher=self.user('teacher','Teacher')
        self.student=self.user('student','Learner')
        self.other=self.user('outsider','Learner')
        self.admin=self.user('admin','Admin')
        self.foreign=self.user('foreign','Admin','foreign')
        self.course=Course.objects.create(title='Course A',description='Test',owner=self.teacher,status='Published')
        self.cohort=Cohort.objects.create(course=self.course,name='Class A',teacher=self.teacher,capacity=3,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=self.cohort,user=self.student)
        self.lesson=Lesson.objects.create(course=self.course,title='First lesson',body='Values are assigned to variable names.',status='Published',author=self.teacher)
        self.client.force_login(self.teacher)

    def user(self,name,role,tenant='demo'):
        u=User.objects.create_user(name,password='test',first_name=name)
        Profile.objects.create(user=u,role=role,tenant=tenant)
        return u

    def post(self,path,body=None):
        return self.client.post('/api/lms/features'+path,data=body or {},content_type='application/json')

    def get(self,path):return self.client.get('/api/lms/features'+path)

    def create(self,kind,**extra):
        body={'course_id':self.course.id,'title':'Test '+kind,'description':'Instructions',**extra}
        r=self.post('/catalogue/'+kind,body)
        self.assertEqual(r.status_code,200,r.content)
        return r.json()

    def test_library_save_borrow_return_reader_and_scope(self):
        self.client.force_login(self.admin)
        obj=self.create('library',subject='Physics',body='Read this resource')
        self.client.force_login(self.student)
        for action in ['Saved','Borrowed','Returned']:
            r=self.post('/library/'+str(obj['id'])+'/loan',{'action':action});self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['status'],action)
        self.assertEqual(self.get('/library/mine').json(),[])
        self.client.force_login(self.other)
        self.assertEqual(self.get('/catalogue/library').json()['total'],0)
        self.assertEqual(self.post('/library/'+str(obj['id'])+'/loan',{'action':'Borrowed'}).status_code,404)

    def test_live_schedule_join_chat_hand_leave_and_attendance(self):
        obj=self.create('live',cohort_id=self.cohort.id,start_at=(timezone.now()-timedelta(minutes=15)).isoformat(),end_at=(timezone.now()+timedelta(hours=1)).isoformat())
        self.client.force_login(self.student)
        r=self.post('/live/'+str(obj['id'])+'/join');self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(r.json()['attendance']['status'],'Late')
        self.assertTrue(r.json()['meeting_url'].startswith('https://meet.jit.si/'))
        for action in [{'action':'hand'},{'action':'chat','body':'My question'}]:self.assertEqual(self.post('/live/'+str(obj['id'])+'/room',action).status_code,200)
        room=self.get('/live/'+str(obj['id'])+'/room').json()
        self.assertTrue(room['participants'][0]['raised']);self.assertEqual(room['messages'][0]['body'],'My question')
        self.assertEqual(self.post('/live/'+str(obj['id'])+'/room',{'action':'leave'}).status_code,200)
        self.assertEqual(self.get('/live/attendance/all').json()[0]['status'],'Late')

    def test_live_rejects_early_and_cancelled_join(self):
        obj=self.create('live',cohort_id=self.cohort.id,start_at=(timezone.now()+timedelta(hours=1)).isoformat(),end_at=(timezone.now()+timedelta(hours=2)).isoformat())
        self.client.force_login(self.student)
        self.assertEqual(self.post('/live/'+str(obj['id'])+'/join').status_code,400)
        self.client.force_login(self.teacher)
        self.assertEqual(self.post('/catalogue/live/'+str(obj['id'])+'/status',{'status':'Cancelled'}).status_code,200)
        self.client.force_login(self.student)
        self.assertEqual(self.post('/live/'+str(obj['id'])+'/join').status_code,400)

    def test_path_progress_comes_from_completed_underlying_work(self):
        obj=self.create('paths',steps=[{'kind':'lesson','reference':self.lesson.id,'title':'Read lesson'}])
        self.client.force_login(self.student)
        row=self.post('/paths/'+str(obj['id'])+'/start').json();self.assertFalse(row['steps'][0]['completed'])
        LessonCompletion.objects.create(lesson=self.lesson,user=self.student)
        self.assertTrue(self.get('/catalogue/paths').json()['items'][0]['steps'][0]['completed'])
        self.client.force_login(self.teacher)
        self.assertEqual(self.post('/catalogue/paths/'+str(obj['id'])+'/edit',{'course_id':self.course.id,'title':'New','steps':[{'kind':'lesson','reference':self.lesson.id}]}).status_code,400)

    def test_preferences_and_rule_based_recommendations(self):
        self.client.force_login(self.student)
        self.assertEqual(self.post('/preferences',{'goals':'Learn daily','pace':'Gentle','language':'Kannada','notifications':False}).status_code,200)
        self.assertEqual(self.get('/preferences').json()['language'],'Kannada')
        self.assertEqual(self.get('/recommendations').json()[0]['id'],self.lesson.id)
        LessonCompletion.objects.create(user=self.student,lesson=self.lesson)
        self.assertEqual(self.get('/recommendations').json(),[])

    def test_translation_review_and_glossary(self):
        obj=self.post('/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Translated example text'}).json()
        self.client.force_login(self.student)
        self.assertIsNone(self.get('/translations?language=Hindi').json()[0]['translation'])
        self.client.force_login(self.teacher)
        self.assertEqual(self.post('/translations/'+str(obj['id'])+'/approve').status_code,200)
        self.client.force_login(self.admin)
        self.assertEqual(self.post('/glossary',{'term':'Variable','definition':'A name for a value','language':'Hindi'}).status_code,200)
        self.client.force_login(self.student)
        self.assertEqual(self.get('/translations?language=Hindi').json()[0]['translation']['body'],'Translated example text')
        self.assertEqual(self.get('/glossary').json()[0]['term'],'Variable')

    def test_discussion_reply_reaction_and_participation(self):
        obj=self.create('activities',due_at=(timezone.now()+timedelta(days=1)).isoformat())
        self.client.force_login(self.student)
        url='/activities/'+str(obj['id'])+'/posts'
        post=self.post(url,{'body':'My contribution'}).json()
        self.assertEqual(self.post(url,{'body':'A reply','parent_id':post['id']}).status_code,200)
        self.post('/activities/posts/'+str(post['id'])+'/react')
        self.assertEqual(self.get(url).json()[0]['reactions'],1)
        self.client.force_login(self.teacher)
        self.assertEqual(self.get('/activities/participation/all').json()[0]['posts'],2)

    def test_code_runner_actual_execution_scoring_and_host_access_denial(self):
        obj=self.create('coding',tests=[{'input':'2\n3','output':'5'},{'input':'-1\n4','output':'3'}])
        self.client.force_login(self.student)
        code='a = int(input())\nb = int(input())\nprint(a+b)'
        self.assertEqual(self.post('/coding/'+str(obj['id'])+'/run',{'code':code,'inputs':'2\n3'}).json()['output'],'5')
        self.assertEqual(self.post('/coding/'+str(obj['id'])+'/submit',{'code':code}).json()['score'],100)
        self.assertEqual(self.post('/coding/'+str(obj['id'])+'/run',{'code':'import os\nprint(os.getcwd())'}).status_code,400)
        self.assertEqual(self.get('/work/coding').json()[0]['score'],100)
        self.assertIn('T',self.get('/work/coding').json()[0]['submitted_at'])
        self.assertNotIn('tests',self.get('/catalogue/coding').json()['items'][0])

    def test_runner_has_execution_and_collection_limits(self):
        with self.assertRaises(RunnerError):run('for i in range(10000):\n    print(i)')
        with self.assertRaises(RunnerError):run('x = "a" * 1000000\nprint(x)')
        with self.assertRaises(RunnerError):run('x = [[1]]\nprint(x)')
        self.assertEqual(run('n=5\ntotal=0\nfor i in range(1,n+1):\n    total += i\nprint(total)'),'15')

    def test_lab_requires_every_observation_and_persists_real_output(self):
        obj=self.create('labs',steps=['Predict','Run and explain'],subject='Python')
        self.client.force_login(self.student)
        url='/labs/'+str(obj['id'])+'/session'
        self.assertEqual(self.post(url,{'code':'print(2+3)','complete':True,'observations':{'0':'Five'}}).status_code,400)
        r=self.post(url,{'code':'print(2+3)','complete':True,'observations':{'0':'Five','1':'The output is 5'}})
        self.assertEqual(r.json()['status'],'Completed');self.assertEqual(r.json()['output'],'5')

    def test_skill_steps_are_ordered_and_idempotent(self):
        obj=self.create('skills',steps=['First','Second'])
        self.client.force_login(self.student)
        url='/skills/'+str(obj['id'])+'/complete'
        self.assertEqual(self.post(url,{'step':1}).status_code,400)
        for step in [0,0,1]:self.assertEqual(self.post(url,{'step':step}).status_code,200)
        self.assertEqual(DigitalSkillProgress.objects.get().completed_steps,[0,1])

    def test_communication_career_placement_and_mains_review(self):
        for module in [172,176,177,178]:
            self.client.force_login(self.teacher);obj=self.create('practice',module=module,practice_type='Writing',rubric='Clarity and relevance')
            self.client.force_login(self.student);response=self.post('/practice/'+str(obj['id'])+'/submit',{'body':'My structured response'});self.assertEqual(response.status_code,200)
            sid=response.json()['id'];self.assertEqual(self.post('/practice/submissions/'+str(sid)+'/review',{'score':80,'feedback':'Clear response'}).status_code,403)
            self.client.force_login(self.teacher);self.assertEqual(self.post('/practice/submissions/'+str(sid)+'/review',{'score':80,'feedback':'Clear response'}).status_code,200)
            self.client.force_login(self.student);self.assertEqual(self.get('/work/practice?module='+str(module)).json()[0]['score'],80)

    def test_each_exam_module_has_its_own_pack_and_scoring_rules(self):
        for module in [173,174,175,176,177]:
            quiz=Quiz.objects.create(course=self.course,title='Quiz '+str(module),correct_marks=4 if module in [174,175] else 1,wrong_marks=-1 if module in [174,175] else 0)
            Question.objects.create(quiz=quiz,prompt='Question',options=['A','B'],answer=0)
            self.create('exams',module=module,subject='Physics' if module==174 else 'General',quiz_id=quiz.id)
        self.client.force_login(self.student)
        for module in [173,174,175,176,177]:
            rows=self.get('/catalogue/exams?module='+str(module)).json()['items'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['module'],module)

    def test_marketplace_preview_is_idempotent_without_payment(self):
        self.assertEqual(self.post('/marketplace/listings',{'course_id':self.course.id,'price':'499.00'}).status_code,200)
        listing=MarketplaceListing.objects.get()
        self.client.force_login(self.other)
        for _ in range(2):self.assertEqual(self.post('/marketplace/'+str(listing.id)+'/enrol').status_code,200)
        self.assertEqual(MarketplacePurchase.objects.count(),1)
        self.assertEqual(Enrolment.objects.filter(user=self.other).count(),1)
        self.client.force_login(self.teacher)
        self.assertEqual(self.get('/marketplace/seller/dashboard').json()[0]['preview_earnings'],'499.00')

    @patch('lms.ai_service.generate',return_value='A variable refers to a value.')
    def test_tutor_policy_blocks_before_provider_and_flag_review(self,provider):
        self.client.force_login(self.admin)
        self.post('/tutor/policies',{'course_id':self.course.id,'allowed_topics':['variable'],'blocked_topics':['secret'],'tone':'Supportive'})
        self.client.force_login(self.student)
        self.assertEqual(self.post('/tutor/chat',{'course_id':self.course.id,'question':'Tell me a secret'}).status_code,400);provider.assert_not_called()
        self.assertEqual(self.post('/tutor/chat',{'course_id':self.course.id,'question':'What is a variable?'}).status_code,200)
        flag=self.post('/tutor/flags',{'course_id':self.course.id,'excerpt':'An answer','reason':'Needs review'}).json()
        self.client.force_login(self.teacher)
        self.assertEqual(self.post('/tutor/flags/'+str(flag['id'])+'/review',{'decision':'Reviewed with learner'}).json()['status'],'Reviewed')

    def test_credential_rules_manual_award_revocation_and_notifications(self):
        r=self.post('/credentials/rules',{'course_id':self.course.id,'title':'Quiz achiever','description':'Score 50%','trigger':'Quiz score','threshold':50})
        self.assertEqual(r.status_code,200)
        c=Credential.objects.get();self.assertEqual(self.post('/credentials/'+str(c.id)+'/award',{'user_id':self.student.id}).status_code,200)
        cert=Certificate.objects.get();self.assertEqual(self.post('/certificates/'+str(cert.id)+'/revoke').json()['status'],'Revoked')
        self.assertEqual(self.client.get('/api/lms/certificates/verify/'+str(cert.code)).json()['status'],'Revoked')
        self.assertEqual(self.post('/announcements',{'course_id':self.course.id,'title':'Update','body':'Study today'}).status_code,200)
        self.client.force_login(self.student);n=self.get('/notifications').json()[0]
        self.assertEqual(self.post('/notifications/'+str(n['id'])+'/read').json()['read'],True)

    def test_quiz_score_credential_trigger(self):
        c=Credential.objects.create(course=self.course,title='Quiz achiever',description='Score')
        CredentialRule.objects.create(credential=c,trigger='Quiz score',threshold=75)
        quiz=Quiz.objects.create(course=self.course,title='Test',correct_marks=4)
        Question.objects.create(quiz=quiz,prompt='Q',options=['A','B'],answer=0)
        Attempt.objects.create(quiz=quiz,user=self.student,score=4,submitted_at=timezone.now(),status='Submitted')
        evaluate_credentials(self.student,self.course);evaluate_credentials(self.student,self.course)
        self.assertEqual(CredentialAward.objects.count(),1);self.assertEqual(Certificate.objects.count(),1)

    def test_cross_tenant_and_unenrolled_catalogue_isolation(self):
        obj=self.create('skills',steps=['First'])
        for user in [self.foreign,self.other]:
            self.client.force_login(user)
            self.assertEqual(self.get('/catalogue/skills').json()['items'],[])
            self.assertEqual(self.post('/skills/'+str(obj['id'])+'/complete',{'step':0}).status_code,403 if user==self.foreign else 404)

    def test_private_files_require_course_access_and_owner_or_publication(self):
        with tempfile.TemporaryDirectory() as temp,override_settings(MEDIA_ROOT=temp):
            self.client.force_login(self.student)
            response=self.client.post('/api/lms/features/files',{'course_id':self.course.id,'file':SimpleUploadedFile('work.txt',b'Private response',content_type='text/plain')})
            self.assertEqual(response.status_code,200,response.content);fid=response.json()['id']
            result=self.get('/files/'+str(fid));self.assertEqual(result.status_code,200);result.close()
            self.client.force_login(self.other);self.assertEqual(self.get('/files/'+str(fid)).status_code,403)
            self.client.force_login(self.teacher);result=self.get('/files/'+str(fid));self.assertEqual(result.status_code,200);result.close()
            bad=self.client.post('/api/lms/features/files',{'course_id':self.course.id,'file':SimpleUploadedFile('bad.html',b'<script>alert(1)</script>')})
            self.assertEqual(bad.status_code,400)

    def test_lecture_upload_publish_and_progress(self):
        with tempfile.TemporaryDirectory() as temp,override_settings(MEDIA_ROOT=temp):
            response=self.client.post('/api/lms/features/files',{'course_id':self.course.id,'file':SimpleUploadedFile('lesson.mp4',b'video-test-payload',content_type='video/mp4')})
            fid=response.json()['id'];obj=self.create('lectures',attachment_id=fid,status='Draft')
            self.client.force_login(self.student);self.assertEqual(self.get('/catalogue/lectures').json()['total'],0)
            self.client.force_login(self.teacher);self.post('/catalogue/lectures/'+str(obj['id'])+'/status',{'status':'Published'})
            self.client.force_login(self.student);r=self.post('/lectures/'+str(obj['id'])+'/progress',{'position':25,'completed':True,'notes':'My note'})
            self.assertEqual(r.json()['position'],25);self.assertTrue(r.json()['completed'])
            self.assertEqual(self.get('/catalogue/lectures').json()['items'][0]['progress']['notes'],'My note')

    def test_question_bank_and_copy_guard_after_attempts(self):
        q1=Quiz.objects.create(course=self.course,title='Source');q2=Quiz.objects.create(course=self.course,title='Destination')
        r=self.post('/question-bank',{'quiz_id':q1.id,'prompt':'Q','options':['A','B'],'answer':0,'explanation':'Because A'})
        self.assertEqual(r.status_code,200);qid=r.json()['id']
        self.assertEqual(self.post('/question-bank/'+str(qid)+'/copy',{'quiz_id':q2.id}).status_code,200)
        Attempt.objects.create(user=self.student,quiz=q2)
        self.assertEqual(self.post('/question-bank/'+str(qid)+'/copy',{'quiz_id':q2.id}).status_code,400)

    def test_qr_certificate_and_reevaluation_lifecycle(self):
        credential=Credential.objects.create(course=self.course,title='Award',description='Learn')
        award=CredentialAward.objects.create(credential=credential,user=self.student)
        cert=Certificate.objects.create(award=award)
        self.client.force_login(self.student)
        response=self.get('/certificates/'+str(cert.id)+'/qr')
        self.assertEqual(response.status_code,200);self.assertIn(b'<svg',response.content)
        task=Assignment.objects.create(course=self.course,title='Task',instructions='Explain',total_marks=10,due_at=timezone.now()+timedelta(days=1))
        sub=Submission.objects.create(assignment=task,user=self.student,body='Work',marks=5,feedback='Original feedback',status='Marked')
        self.assertEqual(self.post('/submissions/'+str(sub.id)+'/reevaluation',{'decision':'Please reconsider the example'}).status_code,200)
        self.client.force_login(self.teacher)
        r=self.client.post('/api/lms/submissions/'+str(sub.id)+'/mark',data={'marks':8,'feedback':'Example reconsidered','rubric':[{'criterion':'Example','marks':8}]},content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(Reevaluation.objects.get().status,'Reviewed');self.assertEqual(MarkingHistory.objects.count(),1)
        self.assertEqual(self.post('/submissions/'+str(sub.id)+'/resubmit').json()['status'],'Resubmit')

    def test_started_quiz_resumes_and_background_expiry_finalizes(self):
        from django.core.management import call_command
        quiz=Quiz.objects.create(course=self.course,title='Timed quiz',time_limit_min=1)
        attempt=Attempt.objects.create(user=self.student,quiz=quiz)
        self.client.force_login(self.student)
        self.assertEqual(self.get('/active-attempt').json()['id'],attempt.id)
        Attempt.objects.filter(pk=attempt.id).update(started_at=timezone.now()-timedelta(minutes=2))
        call_command('expire_attempts',verbosity=0)
        attempt.refresh_from_db();self.assertEqual(attempt.status,'Submitted')
        self.assertIsNone(self.get('/active-attempt').json())

    def test_seller_cannot_list_another_owners_course(self):
        seller=self.user('seller','Seller');self.client.force_login(seller)
        self.assertEqual(self.post('/marketplace/listings',{'course_id':self.course.id,'price':'100'}).status_code,404)
        mine=Course.objects.create(owner=seller,title='Seller course',description='My course',status='Published')
        self.assertEqual(self.post('/marketplace/listings',{'course_id':mine.id,'price':'100'}).status_code,200)
