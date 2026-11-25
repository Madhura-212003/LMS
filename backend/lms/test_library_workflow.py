from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Profile, Course, Cohort, Enrolment, LibraryLoan


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],LIBRARY_LOAN_DAYS=7)
class LibraryWorkflowTests(TestCase):
    def setUp(self):
        self.librarian=self.actor('librarian','Librarian')
        self.teacher=self.actor('teacher','Teacher')
        self.learner=self.actor('learner','Learner')
        self.outsider=self.actor('outsider','Learner')
        self.foreign=self.actor('foreign','Librarian','elsewhere')
        course=Course.objects.create(title='Reading course',description='Learn',status='Published',owner=self.teacher)
        cohort=Cohort.objects.create(course=course,name='Class',teacher=self.teacher,capacity=5,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=cohort,user=self.learner)
        self.client.force_login(self.librarian)
        response=self.post('/features/catalogue/library',{'course_id':course.id,'title':'Reading tables','subject':'Data','body':'Rows represent observations.','status':'Draft'})
        self.assertEqual(response.status_code,200,response.content)
        self.resource_id=response.json()['id']
        self.resource=f'/features/library/resources/{self.resource_id}'
        self.loan=f'/features/library/{self.resource_id}/loan'
        self.publication=f'/features/catalogue/library/{self.resource_id}/status'

    def actor(self,name,role,campus='main'):
        user=User.objects.create_user(name,first_name=name)
        Profile.objects.create(user=user,role=role,campus=campus)
        return user

    def post(self,path,body):
        return self.client.post('/api/lms'+path,data=body,content_type='application/json')

    def get(self,path):
        response=self.client.get('/api/lms'+path)
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def publish(self):
        self.client.force_login(self.librarian)
        self.assertEqual(self.post(self.publication,{'status':'Published'}).status_code,200)

    def test_management_publish_read_save_borrow_return_and_dashboard(self):
        self.publish()
        self.client.force_login(self.learner)
        row=self.get('/features/catalogue/library?list_page=1')['items'][0]
        self.assertEqual(row['id'],self.resource_id)
        self.assertEqual(self.get(self.resource)['body'],'Rows represent observations.')
        self.assertEqual(self.post(self.loan,{'action':'Saved'}).json()['status'],'Saved')
        self.assertEqual(self.get('/features/library/mine?list_page=1')['items'][0]['loan']['status'],'Saved')
        before=timezone.now()
        self.assertEqual(self.post(self.loan,{'action':'Borrowed'}).json()['status'],'Borrowed')
        loan=LibraryLoan.objects.get(resource_id=self.resource_id,user=self.learner)
        self.assertLess(abs((loan.due_at-before-timedelta(days=7)).total_seconds()),3)
        self.client.force_login(self.librarian)
        self.assertEqual(self.get('/features/library/insights?summary=1'),{'resources':1,'published':1,'saved':0,'borrowed':1,'overdue':0})
        self.client.force_login(self.learner)
        self.assertEqual(self.post(self.loan,{'action':'Returned'}).json()['status'],'Returned')
        self.assertEqual(self.get('/features/library/mine?list_page=1')['total'],0)
        self.client.force_login(self.librarian)
        self.assertEqual(self.get('/features/library/insights?summary=1')['borrowed'],0)

    def test_repeated_save_and_borrow_preserve_active_loan_and_due_date(self):
        self.publish();self.client.force_login(self.learner)
        self.post(self.loan,{'action':'Borrowed'})
        before=LibraryLoan.objects.get(resource_id=self.resource_id,user=self.learner).due_at
        for action in ('Borrowed','Saved','Borrowed'):
            row=self.post(self.loan,{'action':action})
            self.assertEqual(row.status_code,200,row.content)
            self.assertEqual(row.json()['status'],'Borrowed')
        loan=LibraryLoan.objects.get(resource_id=self.resource_id,user=self.learner)
        self.assertEqual(loan.due_at,before)
        self.assertEqual(LibraryLoan.objects.count(),1)

    def test_withdrawn_borrowed_resource_can_be_returned_without_exposing_body(self):
        self.publish();self.client.force_login(self.learner)
        self.post(self.loan,{'action':'Borrowed'})
        self.client.force_login(self.librarian)
        self.post(self.publication,{'status':'Draft'})
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get('/api/lms'+self.resource).status_code,403)
        for path in ('/features/library/mine?list_page=1','/features/library/mine'):
            data=self.get(path);row=data['items'][0] if isinstance(data,dict) else data[0]
            self.assertFalse(row['readable']);self.assertEqual(row['body'],'');self.assertIsNone(row['attachment'])
            self.assertEqual(row['loan']['status'],'Borrowed')
        self.assertEqual(self.post(self.loan,{'action':'Returned'}).status_code,200)
        self.assertEqual(self.get('/features/library/mine?list_page=1')['total'],0)

    def test_manifest_and_reader_management_scope(self):
        self.client.force_login(self.learner)
        workflow=self.get('/library-workflow')
        self.assertEqual([(s['label'],s['role']) for s in workflow['screens']],[
            ('Library Catalogue','Learner'),('Resource Management','Librarian'),('My Library','Learner'),
            ('Resource Reader','Learner'),('Librarian Dashboard','Librarian')])
        self.assertEqual([s['accessible'] for s in workflow['screens']],[True,False,True,True,False])
        self.assertEqual(workflow['loan_days'],7)
        self.assertEqual(self.client.get('/api/lms'+self.resource).status_code,403)
        self.assertEqual(self.client.get('/api/lms/features/library/insights?summary=1').status_code,403)
        self.assertEqual(self.post(self.publication,{'status':'Published'}).status_code,403)
        self.publish()
        for user in (self.outsider,self.foreign):
            self.client.force_login(user)
            self.assertEqual(self.client.get('/api/lms'+self.resource).status_code,404)
