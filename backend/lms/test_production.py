import io
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client,TestCase,override_settings
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
from config.production import validate_environment
from .models import *
from .execution import execute
from .identity import resolve_user
from .teaching_runner import RunnerError
from .scanning import scan_upload

TENANT='11111111-1111-1111-1111-111111111111'
OBJECT='22222222-2222-2222-2222-222222222222'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],ENTRA_TENANT_ID=TENANT,ENTRA_ISSUER='https://issuer.example/v2.0',ENTRA_API_AUDIENCE='lms-api',INSTITUTION_ID='institution',DEFAULT_CAMPUS='campus')
class ProductionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.teacher=User.objects.create_user('teacher',password='test')
        Profile.objects.create(user=self.teacher,role='Teacher',tenant='institution',campus='campus')
        self.student=User.objects.create_user('learner',password='test')
        Profile.objects.create(user=self.student,role='Learner',tenant='institution',campus='campus')
        self.course=Course.objects.create(owner=self.teacher,title='Course',description='Test',tenant='institution',campus='campus',status='Published')
        from datetime import timedelta
        from django.utils import timezone
        self.cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Cohort',capacity=30,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30),tenant='institution',campus='campus')
        Enrolment.objects.create(user=self.student,cohort=self.cohort)

    def claims(self,**overrides):return {'tid':TENANT,'oid':OBJECT,'roles':['Learner'],'preferred_username':'teacher@example.org','name':'Federated learner',**overrides}
    def post(self,path,body=None):return self.client.post('/api/lms'+path,data=body or {},content_type='application/json')

    def test_production_environment_fails_closed_without_printing_secret_values(self):
        errors=validate_environment({'DJANGO_SECRET_KEY':'secret-never-print'})
        self.assertTrue(any('POSTGRES_DB' in e for e in errors));self.assertNotIn('secret-never-print',' '.join(errors))
        env={k:'configured' for k in ['DJANGO_SECRET_KEY','DJANGO_ALLOWED_HOSTS','PUBLIC_APP_URL','POSTGRES_DB','POSTGRES_HOST','POSTGRES_USER','POSTGRES_PASSWORD','REDIS_URL','ENTRA_TENANT_ID','ENTRA_CLIENT_ID','ENTRA_CLIENT_SECRET','ENTRA_API_AUDIENCE','INSTITUTION_ID','AZURE_STORAGE_ACCOUNT_NAME','AZURE_STORAGE_CONTAINER','EXECUTION_SERVICE_URL','EXECUTION_SERVICE_TOKEN','AI_API_KEY','AI_MODEL','JITSI_BASE_URL','CLAMAV_HOST','JITSI_JWT_APP_ID','JITSI_JWT_SECRET']}
        env.update(DJANGO_SECRET_KEY='x'*64,PUBLIC_APP_URL='https://lms.example.org',EXECUTION_SERVICE_URL='https://runner.example.org',JITSI_BASE_URL='https://meet.example.org',AI_PROVIDER='gemini')
        self.assertEqual(validate_environment(env),[])
        env['JITSI_BASE_URL']='https://meet.jit.si';self.assertTrue(any('public test' in x for x in validate_environment(env)))

    def test_federation_does_not_link_by_mutable_email_and_is_idempotent(self):
        self.teacher.email='teacher@example.org';self.teacher.save()
        user=resolve_user(self.claims());self.assertNotEqual(user.id,self.teacher.id)
        self.assertFalse(user.has_usable_password());self.assertEqual(user.profile.tenant,'institution')
        self.assertEqual(resolve_user(self.claims()).id,user.id)
        self.assertEqual(FederatedIdentity.objects.count(),1)
        from ninja.errors import HttpError
        with self.assertRaises(HttpError):resolve_user(self.claims(roles=[]))
        with self.assertRaises(HttpError):resolve_user(self.claims(tid='other'))

    def test_signed_bearer_checks_issuer_audience_expiry_and_roles(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        base=self.claims(iss=settings.ENTRA_ISSUER,aud='lms-api',iat=int(time.time()),exp=int(time.time())+300)
        mock=MagicMock();mock.get_signing_key_from_jwt.return_value=SimpleNamespace(key=key.public_key())
        with patch('lms.identity.key_client',return_value=mock):
            client=Client()
            for claims,status in [(base,200),({**base,'aud':'wrong'},401),({**base,'exp':1},401),({**base,'roles':[]},401),({**base,'iss':'https://attacker.example'},401)]:
                token=jwt.encode(claims,key,algorithm='RS256')
                self.assertEqual(client.get('/api/lms/auth/me',HTTP_AUTHORIZATION='Bearer '+token).status_code,status)

    @override_settings(PRODUCTION=True)
    def test_production_disables_password_login_and_unbound_legacy_sessions(self):
        self.assertEqual(self.post('/auth/login',{'email':'teacher','password':'test'}).status_code,403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get('/api/lms/auth/me').status_code,401)
        FederatedIdentity.objects.create(user=self.teacher,directory_tenant=TENANT,subject=OBJECT)
        self.assertEqual(self.client.get('/api/lms/auth/me').status_code,200)

    @patch.dict(os.environ,{'EXECUTION_SERVICE_URL':'https://runner.example','EXECUTION_SERVICE_TOKEN':'private-token'})
    @patch('lms.execution.urllib.request.urlopen')
    def test_execution_uses_isolated_provider_for_full_programs(self,urlopen):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps({'run':{'code':0,'stdout':'5\n'}}).encode();urlopen.return_value=response
        result=execute('def add(a,b):\n    return a+b\nprint(add(2,3))',language='Python')
        self.assertEqual(result,'5\n');request=urlopen.call_args.args[0];data=json.loads(request.data)
        self.assertEqual(data['language'],'python');self.assertEqual(data['run_timeout'],3000)
        self.assertEqual(request.get_header('Authorization'),'Bearer private-token')

    @override_settings(PRODUCTION=True)
    @patch.dict(os.environ,{'EXECUTION_SERVICE_URL':''})
    def test_production_never_silently_uses_teaching_subset(self):
        from ninja.errors import HttpError
        with self.assertRaises(HttpError):execute('print(5)')

    @override_settings(PRODUCTION=True)
    @patch.dict(os.environ,{'CLAMAV_HOST':''})
    def test_production_upload_scanning_is_required(self):
        from ninja.errors import HttpError
        with self.assertRaises(HttpError):scan_upload(io.BytesIO(b'test'))

    def test_interface_locale_is_persisted_and_validated(self):
        self.client.force_login(self.student)
        self.assertEqual(self.post('/features/preferences',{'ui_language':'kn'}).status_code,200)
        self.assertEqual(self.client.get('/api/lms/features/preferences').json()['ui_language'],'kn')
        self.assertEqual(self.post('/features/preferences',{'ui_language':'invalid'}).status_code,400)

    def test_multiple_and_numerical_questions_hide_answers_and_score(self):
        self.client.force_login(self.teacher)
        response=self.post('/quizzes',{'course_id':self.course.id,'title':'Advanced','time_limit_min':10,'max_attempts':3,'correct_marks':4,'wrong_marks':-1,'questions':[{'prompt':'Choose primes','kind':'Multiple choice','options':['2','3','4'],'answer_set':[0,1]},{'prompt':'Find pi approximation','kind':'Numerical','numeric_answer':3.14,'tolerance':0.01,'correct_marks':3,'wrong_marks':0}]})
        self.assertEqual(response.status_code,200,response.content);qid=response.json()['id']
        self.client.force_login(self.student);started=self.post('/quizzes/'+str(qid)+'/attempts').json()
        self.assertNotIn('numeric_answer',started['questions'][1]);self.assertNotIn('answer_set',started['questions'][0])
        answers={str(started['questions'][0]['id']):[0,1],str(started['questions'][1]['id']):'3.145'}
        result=self.post('/attempts/'+str(started['id'])+'/submit',{'answers':answers})
        self.assertEqual(result.json()['score'],7)
        self.assertEqual(result.json()['questions'][0]['answer_set'],[0,1])

    def test_private_study_group_isolation(self):
        from django.utils import timezone
        from datetime import timedelta
        other=User.objects.create_user('other');Profile.objects.create(user=other,role='Learner',tenant='institution',campus='campus');Enrolment.objects.create(user=other,cohort=self.cohort)
        activity=Activity.objects.create(course=self.course,title='Group exercise',description='Discuss',due_at=timezone.now()+timedelta(days=1),tenant='institution',campus='campus')
        self.client.force_login(self.teacher)
        group=self.post('/features/activities/'+str(activity.id)+'/groups',{'name':'Team A','user_ids':[self.student.id]}).json()
        self.client.force_login(self.student)
        post=self.post('/features/activities/'+str(activity.id)+'/posts',{'body':'Private team response','group_id':group['id']});self.assertEqual(post.status_code,200)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/api/lms/features/activities/'+str(activity.id)+'/posts?group_id='+str(group['id'])).status_code,403)
        self.assertEqual(self.post('/features/activities/posts/'+str(post.json()['id'])+'/react').status_code,403)
        self.assertEqual(self.client.get('/api/lms/features/activities/'+str(activity.id)+'/posts').json(),[])

    def test_rubric_total_must_match_awarded_marks(self):
        from django.utils import timezone
        assignment=Assignment.objects.create(course=self.course,title='Task',instructions='Write',due_at=timezone.now(),total_marks=100)
        sub=Submission.objects.create(assignment=assignment,user=self.student,body='Work')
        self.client.force_login(self.teacher)
        bad=self.post('/submissions/'+str(sub.id)+'/mark',{'marks':80,'feedback':'Feedback','rubric':[{'criterion':'Clarity','marks':10,'max_marks':20}]})
        self.assertEqual(bad.status_code,400);self.assertEqual(MarkingHistory.objects.count(),0)
        good=self.post('/submissions/'+str(sub.id)+'/mark',{'marks':80,'feedback':'Feedback','rubric':[{'criterion':'Clarity','marks':40,'max_marks':50},{'criterion':'Evidence','marks':40,'max_marks':50}]})
        self.assertEqual(good.status_code,200);self.assertEqual(len(MarkingHistory.objects.get().rubric),2)

    @override_settings(PRODUCTION=True)
    @patch('django.core.files.storage.FileSystemStorage.url',return_value='https://private.blob.core.windows.net/learning/file.pdf?sig=unit-test')
    def test_private_blob_link_is_issued_only_after_course_access(self,url):
        obj=Attachment.objects.create(course=self.course,owner=self.teacher,name='file.pdf',file='learning/file.pdf',mime='application/pdf',tenant='institution',campus='campus')
        FederatedIdentity.objects.create(user=self.teacher,directory_tenant=TENANT,subject=OBJECT)
        self.client.force_login(self.teacher)
        response=self.client.get('/api/lms/features/files/'+str(obj.id))
        self.assertEqual(response.status_code,302);self.assertEqual(response['Cache-Control'],'private, no-store');url.assert_called_once()
        url.reset_mock();outsider=User.objects.create_user('outside');Profile.objects.create(user=outsider,role='Learner',tenant='institution',campus='campus');FederatedIdentity.objects.create(user=outsider,directory_tenant=TENANT,subject='other-object');self.client.force_login(outsider)
        self.assertEqual(self.client.get('/api/lms/features/files/'+str(obj.id)).status_code,403);url.assert_not_called()

    @patch.dict(os.environ,{'CLAMAV_HOST':'scanner.example'})
    @patch('lms.scanning.socket.create_connection')
    def test_malware_scanner_blocks_a_positive_signature(self,connect):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from ninja.errors import HttpError
        connection=MagicMock();connection.__enter__.return_value.recv.return_value=b'stream: Eicar-Signature FOUND\0';connect.return_value=connection
        file=SimpleUploadedFile('scan.txt',b'test signature')
        with self.assertRaises(HttpError) as error:scan_upload(file)
        self.assertEqual(error.exception.status_code,400);self.assertEqual(file.tell(),0)
