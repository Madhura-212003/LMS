from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Profile,Course,Cohort,Enrolment,Lesson,TutorPolicy,TutorFlag
from .permissions import permits


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class TutorWorkflowTests(TestCase):
    def setUp(self):
        self.teacher=self.actor('teacher','Teacher');self.coordinator=self.actor('coordinator','Coordinator');self.admin=self.actor('admin','Admin');self.student=self.actor('student','Learner');self.other=self.actor('other','Learner');self.foreign=self.actor('foreign','Coordinator','foreign');self.unassigned=self.actor('unassigned','Teacher')
        self.course=Course.objects.create(owner=self.teacher,title='Tutor course',status='Published')
        self.cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Learners',capacity=10,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=self.cohort,user=self.student);Enrolment.objects.create(cohort=self.cohort,user=self.other)
        Lesson.objects.create(course=self.course,author=self.teacher,title='Published',body='Variables hold values.',status='Published')
        Lesson.objects.create(course=self.course,author=self.teacher,title='Draft',body='PRIVATE DRAFT',status='Draft')
        self.client.force_login(self.student)

    def actor(self,name,role,tenant='demo'):
        user=User.objects.create_user(name,first_name=name);Profile.objects.create(user=user,role=role,tenant=tenant);return user

    def post(self,path,data):return self.client.post('/api/lms/features/tutor'+path,data,content_type='application/json')
    def get(self,path):return self.client.get('/api/lms/features/tutor'+path)

    def test_manifest_audiences_and_capabilities_do_not_grant_assessment_authoring(self):
        for actor,expected in [(self.student,[True,False,False]),(self.teacher,[False,True,False]),(self.coordinator,[False,True,True]),(self.admin,[False,True,True])]:
            self.client.force_login(actor);response=self.client.get('/api/lms/tutor-workflow')
            self.assertEqual(response.status_code,200);data=response.json()
            self.assertEqual([s['label'] for s in data['screens']],['AI Tutor Chat','Teacher Tutor Review','Tutor Policy / Settings'])
            self.assertEqual([s['accessible'] for s in data['screens']],expected)
        self.assertTrue(permits(self.coordinator,'tutor_review'));self.assertTrue(permits(self.coordinator,'tutor_policy'));self.assertFalse(permits(self.coordinator,'assessment_write'))

    def test_coordinator_policy_normalizes_and_is_enforced_before_and_after_provider(self):
        self.client.force_login(self.coordinator)
        saved=self.post('/policies',{'course_id':self.course.id,'allowed_topics':[' variable ','','variable'],'blocked_topics':[' secret '],'tone':' Supportive ','escalation':' Contact staff '})
        self.assertEqual(saved.status_code,200,saved.content);self.assertEqual(saved.json()['allowed_topics'],['variable'])
        self.assertEqual(saved.json()['tone'],'Supportive')
        self.assertEqual(self.post('/policies',{'course_id':self.course.id,'tone':' '}).status_code,400)
        self.assertEqual(TutorPolicy.objects.get(course=self.course).blocked_topics,['secret'])
        self.client.force_login(self.student)
        with patch('lms.ai_service.generate',return_value='A variable holds a value.') as generate:
            for question in ['a SECRET','unrelated topic','   ']:self.assertEqual(self.post('/chat',{'course_id':self.course.id,'question':question}).status_code,400)
            generate.assert_not_called()
            reply=self.post('/chat',{'course_id':self.course.id,'question':'What is a variable?'})
            self.assertEqual(reply.status_code,200,reply.content)
            self.assertEqual(generate.call_args.args[1],'Variables hold values.')
        with patch('lms.ai_service.generate',return_value='A SECRET value'):
            reply=self.post('/chat',{'course_id':self.course.id,'question':'variable'})
            self.assertIn('withheld',reply.json()['text']);self.assertIn('Contact staff',reply.json()['text'])

    def test_flag_review_returns_to_only_its_learner_for_legacy_and_paginated_lists(self):
        flag=self.post('/flags',{'course_id':self.course.id,'excerpt':'Please check this answer','reason':'Unclear'}).json()
        TutorFlag.objects.create(course=self.course,user=self.other,excerpt='OTHER PRIVATE ANSWER',reason='Other')
        for suffix in ['', '?list_page=1']:
            response=self.get('/flags'+suffix);self.assertEqual(response.status_code,200);self.assertNotIn('OTHER PRIVATE ANSWER',response.content.decode())
        self.client.force_login(self.coordinator)
        self.assertEqual(self.get('/flags?list_page=1').json()['total'],2)
        self.assertEqual(self.post(f"/flags/{flag['id']}/review",{'decision':'  '}).status_code,400)
        reviewed=self.post(f"/flags/{flag['id']}/review",{'decision':' Read the example together. '})
        self.assertEqual(reviewed.status_code,200,reviewed.content);self.assertEqual(reviewed.json()['status'],'Reviewed')
        self.client.force_login(self.student)
        result=self.get('/flags?list_page=1').json()['items'][0]
        self.assertEqual(result['decision'],'Read the example together.')
        self.assertEqual(self.post(f"/flags/{flag['id']}/review",{'decision':'Overwrite'}).status_code,403)

    def test_roles_course_scope_and_publication_block_unauthorized_work(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.post('/policies',{'course_id':self.course.id}).status_code,403)
        self.assertEqual(self.post('/chat',{'course_id':self.course.id,'question':'variable'}).status_code,403)
        self.assertEqual(self.post('/flags',{'course_id':self.course.id,'excerpt':'answer','reason':'reason'}).status_code,403)
        self.client.force_login(self.student)
        flag=self.post('/flags',{'course_id':self.course.id,'excerpt':'answer','reason':'reason'}).json()
        for actor in (self.foreign,self.unassigned):
            self.client.force_login(actor)
            for suffix in ['', '?list_page=1']:
                self.assertEqual(self.get('/flags'+suffix).json()['items'] if suffix else self.get('/flags'+suffix).json(),[])
            self.assertEqual(self.post(f"/flags/{flag['id']}/review",{'decision':'Forbidden'}).status_code,404)
            self.assertEqual(self.get(f'/policies/{self.course.id}').status_code,403)
        self.client.force_login(self.foreign)
        self.assertEqual(self.post('/policies',{'course_id':self.course.id}).status_code,403)
        self.client.force_login(self.student)
        self.course.status='Draft';self.course.save()
        with patch('lms.ai_service.generate') as generate:
            self.assertEqual(self.post('/chat',{'course_id':self.course.id,'question':'variable'}).status_code,403);generate.assert_not_called()
        self.course.status='Published';self.course.save()
        Enrolment.objects.filter(user=self.student).update(status='Waitlisted')
        self.assertEqual(self.post('/chat',{'course_id':self.course.id,'question':'variable'}).status_code,403)

    def test_defaults_and_provider_failure_do_not_create_fake_answers(self):
        detail=self.get(f'/policies/{self.course.id}').json()
        self.assertFalse(detail['saved']);self.assertEqual(detail['tone'],TutorPolicy._meta.get_field('tone').get_default())
        self.assertFalse(TutorPolicy.objects.exists())
        from ninja.errors import HttpError
        with patch('lms.ai_service.generate',side_effect=HttpError(503,'AI configuration is missing')):
            response=self.post('/chat',{'course_id':self.course.id,'question':'variable'})
            self.assertEqual(response.status_code,503);self.assertIn('configuration',response.json()['detail'])
        self.assertFalse(TutorFlag.objects.exists())
