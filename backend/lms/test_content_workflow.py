from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Course, Cohort, Enrolment, Profile, CourseStaffAssignment, Lesson


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ContentWorkflowTests(TestCase):
    def setUp(self):
        self.teacher=self.actor('teacher','Teacher')
        self.author=self.actor('author','Author')
        self.reviewer=self.actor('reviewer','Reviewer')
        self.learner=self.actor('learner','Learner')
        self.stranger=self.actor('stranger','Reviewer')
        self.course=Course.objects.create(title='Data analysis',description='Interpret tables',owner=self.teacher,status='Published')
        for user in (self.author,self.reviewer):
            CourseStaffAssignment.objects.create(course=self.course,user=user,granted_by=self.teacher)
        cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Class',capacity=5,
                                    start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=cohort,user=self.learner)
        self.draft={'course_id':self.course.id,'title':'Interpreting a table','body':'Rows describe observations.','position':1}

    def actor(self,name,role):
        user=User.objects.create_user(name,first_name=name)
        Profile.objects.create(user=user,role=role)
        return user

    def post(self,path,body):
        return self.client.post('/api/lms'+path,data=body,content_type='application/json')

    def get(self,path):
        response=self.client.get('/api/lms'+path)
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def test_author_reviewer_learner_connected_lifecycle(self):
        self.client.force_login(self.author)
        created=self.post('/content',self.draft)
        self.assertEqual(created.status_code,200,created.content)
        lesson_id=created.json()['id']
        path=f'/content/{lesson_id}'
        self.assertEqual(self.post(path+'/review',{'decision':'Published'}).status_code,403)
        self.assertEqual(self.post(path+'/review',{'decision':'In Review'}).status_code,200)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.get('/content?list_page=1&status=In%20Review')['total'],1)
        self.assertEqual(self.post(path+'/review',{'decision':'Needs Changes','comment':'Add an example table.'}).status_code,200)
        self.assertEqual(self.post('/content',self.draft).status_code,403)
        self.client.force_login(self.author)
        history=self.get(path+'/reviews?list_page=1')['items']
        self.assertEqual(history[0]['comment'],'Add an example table.')
        self.assertEqual(history[0]['reviewer'],'reviewer')
        self.assertEqual(self.post(path+'/edit',{**self.draft,'body':'Rows describe observations. Example: one row per learner.'}).status_code,200)
        self.assertEqual(self.post(path+'/review',{'decision':'In Review'}).status_code,200)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post(path+'/review',{'decision':'Approved'}).status_code,200)
        self.client.force_login(self.learner)
        self.assertEqual(self.get('/content?list_page=1')['total'],0)
        self.assertEqual(self.get(f'/courses/{self.course.id}')['lessons'],[])
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post(path+'/review',{'decision':'Published'}).status_code,200)
        self.client.force_login(self.learner)
        self.assertEqual(self.get('/content?list_page=1')['items'][0]['id'],lesson_id)
        self.assertEqual(self.get(f'/courses/{self.course.id}')['lessons'][0]['id'],lesson_id)
        self.assertEqual(self.post(path+'/complete',{}).status_code,200)
        self.assertEqual(self.get('/courses?list_page=1')['items'][0]['progress'],100)

    def test_review_history_is_not_exposed_to_learners_or_unassigned_staff(self):
        lesson=Lesson.objects.create(course=self.course,author=self.author,title='Private draft',body='Draft notes')
        for user in (self.learner,self.stranger):
            self.client.force_login(user)
            for suffix in ('/reviews','/reviews?list_page=1'):
                self.assertEqual(self.client.get(f'/api/lms/content/{lesson.id}'+suffix).status_code,403)

    def test_workflow_order_roles_and_capabilities(self):
        self.client.force_login(self.learner)
        workflow=self.get('/content-workflow')
        self.assertEqual([(s['label'],s['role']) for s in workflow['screens']], [
            ('Content Editor','Author'),('Content Review','Reviewer'),
            ('Course Viewer','Learner'),('Content Catalogue','Author')])
        self.assertEqual([s['accessible'] for s in workflow['screens']],[False,False,True,True])
        self.client.force_login(self.author)
        self.assertEqual([s['accessible'] for s in self.get('/content-workflow')['screens']],[True,False,True,True])
        self.client.force_login(self.reviewer)
        self.assertEqual([s['accessible'] for s in self.get('/content-workflow')['screens']],[False,True,True,True])
        self.assertEqual(workflow['transitions']['Approved'],['Published'])
