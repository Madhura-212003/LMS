import tempfile
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Profile,Course,Cohort,Enrolment,CourseStaffAssignment,LectureProgress
from .permissions import permissions


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],LECTURE_PROGRESS_SAVE_SECONDS=9)
class LectureWorkflowTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory();self.addCleanup(self.media.cleanup)
        media_settings=override_settings(MEDIA_ROOT=self.media.name);media_settings.enable();self.addCleanup(media_settings.disable)
        self.teacher=self.actor('teacher','Teacher');self.ta=self.actor('assistant','TA')
        self.coordinator=self.actor('coordinator','Coordinator');self.admin=self.actor('admin','Admin')
        self.student=self.actor('student','Learner');self.outsider=self.actor('outsider','Learner')
        self.course=Course.objects.create(owner=self.teacher,title='Recorded course',description='Learn',status='Published')
        CourseStaffAssignment.objects.create(course=self.course,user=self.ta,granted_by=self.admin)
        cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Group',capacity=10,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=cohort,user=self.student)
        self.client.force_login(self.teacher)
        self.video=self.upload('lesson.mp4',b'isolated API video fixture','video/mp4')
        self.captions=self.upload('lesson.vtt',b'WEBVTT\n\n00:00.000 --> 00:02.000\nCourse introduction.','text/vtt')

    def actor(self,name,role):
        user=User.objects.create_user(name,first_name=name);Profile.objects.create(user=user,role=role);return user

    def post(self,path,body):
        return self.client.post('/api/lms'+path,data=body,content_type='application/json')

    def get(self,path):
        response=self.client.get('/api/lms'+path);self.assertEqual(response.status_code,200,response.content);return response.json()

    def upload(self,name,data,mime):
        response=self.client.post('/api/lms/features/files',{'course_id':self.course.id,'file':SimpleUploadedFile(name,data,content_type=mime)})
        self.assertEqual(response.status_code,200,response.content);return response.json()['id']

    def create(self,**overrides):
        payload={'course_id':self.course.id,'title':'Data interpretation','description':'Explain tables','topic':'Tables','attachment_id':self.video,'captions_id':self.captions,'status':'Draft',**overrides}
        response=self.post('/features/catalogue/lectures',payload)
        self.assertEqual(response.status_code,200,response.content);return response.json(),payload

    def test_upload_publish_player_progress_notes_and_withdrawal(self):
        item,_=self.create();lecture_id=item['id']
        self.client.force_login(self.student)
        self.assertEqual(self.get('/features/catalogue/lectures?list_page=1')['total'],0)
        self.assertEqual(self.client.get(f'/api/lms/features/lectures/resources/{lecture_id}').status_code,403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.post(f'/features/catalogue/lectures/{lecture_id}/status',{'status':'Published'}).status_code,200)
        self.client.force_login(self.student)
        self.assertEqual(self.get(f'/features/lectures/resources/{lecture_id}')['captions'],self.captions)
        path=f'/features/lectures/{lecture_id}/progress'
        self.assertEqual(self.post(path,{'position':25,'notes':'My explanation'}).status_code,200)
        self.post(path,{'position':40})
        row=LectureProgress.objects.get(lecture_id=lecture_id,user=self.student)
        self.assertEqual(row.notes,'My explanation');self.assertEqual(row.position,40)
        self.post(path,{'position':50,'completed':True})
        self.post(path,{'position':20,'completed':False})
        reopened=self.get(f'/features/lectures/resources/{lecture_id}')['progress']
        self.assertTrue(reopened['completed']);self.assertEqual(reopened['notes'],'My explanation')
        self.assertEqual(LectureProgress.objects.count(),1)
        self.client.force_login(self.teacher)
        self.post(f'/features/catalogue/lectures/{lecture_id}/status',{'status':'Draft'})
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(f'/api/lms/features/lectures/resources/{lecture_id}').status_code,403)
        self.assertEqual(LectureProgress.objects.get(lecture_id=lecture_id,user=self.student).notes,'My explanation')

    def test_requested_staff_roles_manage_lectures_without_assessment_escalation(self):
        for actor in (self.teacher,self.ta,self.coordinator,self.admin):
            self.client.force_login(actor)
            self.assertIn('lecture_manage',permissions(actor))
            video=self.upload(actor.username+'.webm',b'isolated fixture','video/webm')
            item,_=self.create(attachment_id=video)
            self.assertEqual(self.post(f"/features/catalogue/lectures/{item['id']}/status",{'status':'Published'}).status_code,200)
            self.assertEqual(self.post(f"/features/lectures/{item['id']}/progress",{'position':1}).status_code,403)
        self.assertNotIn('assessment_write',permissions(self.ta));self.assertNotIn('assessment_write',permissions(self.coordinator))

    def test_scope_invalid_media_and_safe_video_replacement(self):
        item,payload=self.create(status='Published');lecture_id=item['id']
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(f'/api/lms/features/lectures/resources/{lecture_id}').status_code,404)
        self.client.force_login(self.student)
        self.assertEqual(self.post('/features/catalogue/lectures',payload).status_code,403)
        self.post(f'/features/lectures/{lecture_id}/progress',{'position':5,'notes':'Retained'})
        self.client.force_login(self.teacher)
        replacement=self.upload('new.mp4',b'isolated replacement','video/mp4')
        self.assertEqual(self.post(f'/features/catalogue/lectures/{lecture_id}/edit',{**payload,'attachment_id':replacement}).status_code,400)
        self.assertEqual(self.post(f'/features/catalogue/lectures/{lecture_id}/edit',{**payload,'topic':'Revised topic'}).status_code,200)
        text=self.upload('notes.txt',b'Not a video','text/plain')
        self.assertEqual(self.post('/features/catalogue/lectures',{**payload,'attachment_id':text}).status_code,400)

    def test_manifest_order_and_configured_player_policy(self):
        self.client.force_login(self.student);workflow=self.get('/lecture-workflow')
        self.assertEqual([(s['label'],s['role']) for s in workflow['screens']],[
            ('Lecture Upload / Edit / Publish','Teacher / TA / Coordinator / Admin'),
            ('Learner Lecture Player','Learner'),('Lecture Library / Search','Teacher / Coordinator / Learner')])
        self.assertEqual([s['accessible'] for s in workflow['screens']],[False,True,True])
        self.assertEqual(workflow['progress_save_seconds'],9);self.assertTrue(workflow['can_track_progress'])
        self.client.force_login(self.ta);workflow=self.get('/lecture-workflow')
        self.assertTrue(workflow['can_manage']);self.assertFalse(workflow['can_track_progress'])
