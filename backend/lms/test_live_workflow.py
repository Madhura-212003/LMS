from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import Profile,Course,Cohort,Enrolment,CourseStaffAssignment,LiveClass,Attendance,RoomMessage


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],LIVE_LATE_AFTER_MINUTES=5,LIVE_ROOM_POLL_SECONDS=3)
class LiveWorkflowTests(TestCase):
    def setUp(self):
        self.teacher=self.actor('teacher','Teacher');self.coordinator=self.actor('coordinator','Coordinator')
        self.learner=self.actor('learner','Learner');self.other=self.actor('other','Learner');self.ta=self.actor('assistant','TA')
        self.course=Course.objects.create(owner=self.teacher,title='Live course',description='Learn',status='Published')
        self.cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Cohort',capacity=10,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=self.cohort,user=self.learner)
        other_cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Other group',capacity=10,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=other_cohort,user=self.other)
        CourseStaffAssignment.objects.create(course=self.course,user=self.ta,granted_by=self.coordinator)
        now=timezone.now()
        self.payload={'course_id':self.course.id,'cohort_id':self.cohort.id,'title':'Working with data','description':'Class discussion','start_at':(now-timedelta(minutes=8)).isoformat(),'end_at':(now+timedelta(hours=1)).isoformat()}
        self.client.force_login(self.teacher)
        response=self.post('/features/catalogue/live',self.payload)
        self.assertEqual(response.status_code,200,response.content)
        self.live=LiveClass.objects.get(pk=response.json()['id'])

    def actor(self,name,role):
        user=User.objects.create_user(name,first_name=name);Profile.objects.create(user=user,role=role);return user

    def post(self,path,body=None):
        return self.client.post('/api/lms'+path,data=body or {},content_type='application/json')

    def get(self,path):
        response=self.client.get('/api/lms'+path);self.assertEqual(response.status_code,200,response.content);return response.json()

    def test_join_discussion_leave_resume_and_personal_attendance(self):
        self.client.force_login(self.learner)
        schedule=self.get('/features/catalogue/live?list_page=1&sort=start_at')
        self.assertEqual(schedule['total'],1);self.assertTrue(schedule['items'][0]['can_join'])
        detail=self.get(f'/features/live/classes/{self.live.id}')
        self.assertIsNone(detail['attendance']);self.assertEqual(Attendance.objects.count(),0)
        self.assertEqual(self.client.get(f'/api/lms/features/live/{self.live.id}/room').status_code,403)
        joined=self.post(f'/features/live/{self.live.id}/join')
        self.assertEqual(joined.status_code,200,joined.content)
        self.assertEqual(joined.json()['attendance']['status'],'Late')
        first=Attendance.objects.get(live_class=self.live,user=self.learner).joined_at
        self.assertEqual(self.post(f'/features/live/{self.live.id}/room',{'action':'chat','body':'Can you explain this?'}).status_code,200)
        self.post(f'/features/live/{self.live.id}/room',{'action':'hand'})
        room=self.get(f'/features/live/{self.live.id}/room')
        self.assertTrue(room['open']);self.assertTrue(room['participants'][0]['raised']);self.assertEqual(len(room['messages']),1)
        self.post(f'/features/live/{self.live.id}/room',{'action':'leave'})
        self.assertEqual(self.post(f'/features/live/{self.live.id}/room',{'action':'chat','body':'After leaving'}).status_code,403)
        self.post(f'/features/live/{self.live.id}/join')
        row=Attendance.objects.get(live_class=self.live,user=self.learner)
        self.assertEqual(row.joined_at,first);self.assertFalse(row.hand_raised);self.assertEqual(Attendance.objects.count(),1)
        attendance=self.get('/features/live/attendance/all?list_page=1')['items']
        self.assertEqual(len(attendance),1);self.assertEqual(attendance[0]['user_id'],self.learner.id)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.post(f'/final/live/{self.live.id}/attendance/{self.learner.id}',{'status':'Present'}).status_code,200)
        self.client.force_login(self.learner)
        self.assertEqual(self.get('/features/live/attendance/all?list_page=1')['items'][0]['status'],'Present')

    def test_ta_can_assist_but_not_schedule_edit_or_cancel(self):
        self.client.force_login(self.ta)
        self.assertEqual(self.post('/features/catalogue/live',self.payload).status_code,403)
        self.assertEqual(self.post(f'/features/catalogue/live/{self.live.id}/edit',self.payload).status_code,403)
        self.assertEqual(self.post(f'/features/catalogue/live/{self.live.id}/status',{'status':'Cancelled'}).status_code,403)
        self.assertEqual(self.post(f'/features/live/{self.live.id}/join').status_code,200)
        self.assertTrue(self.get(f'/features/live/{self.live.id}/room')['open'])
        workflow=self.get('/live-workflow')
        self.assertFalse(workflow['can_schedule']);self.assertEqual(workflow['poll_ms'],3000)
        self.assertEqual([s['label'] for s in workflow['screens']],['Class Schedule / Manage','Live Class Room','Attendance Summary','Learner Class Schedule'])

    def test_time_cohort_cancellation_and_absence_boundaries(self):
        self.client.force_login(self.other)
        self.assertEqual(self.get('/features/catalogue/live?list_page=1')['total'],0)
        self.assertEqual(self.client.get(f'/api/lms/features/live/classes/{self.live.id}').status_code,403)
        self.assertEqual(self.post(f'/features/live/{self.live.id}/join').status_code,403)
        self.client.force_login(self.learner)
        self.live.start_at=timezone.now()+timedelta(minutes=10);self.live.save()
        self.assertFalse(self.get(f'/features/live/classes/{self.live.id}')['can_join'])
        self.assertEqual(self.post(f'/features/live/{self.live.id}/join').status_code,400)
        self.client.force_login(self.teacher)
        self.post(f'/features/catalogue/live/{self.live.id}/status',{'status':'Cancelled'})
        self.live.refresh_from_db();self.live.end_at=timezone.now()-timedelta(minutes=1);self.live.save()
        self.client.force_login(self.learner)
        self.assertEqual(self.get('/features/live/attendance/all?list_page=1')['items'][0]['status'],'Cancelled')
        self.assertEqual(self.post(f'/features/live/{self.live.id}/join').status_code,400)
        self.assertEqual(RoomMessage.objects.count(),0)

    def test_closed_class_denies_chat_and_existing_attendance_prevents_cohort_move(self):
        self.client.force_login(self.learner);self.post(f'/features/live/{self.live.id}/join')
        self.client.force_login(self.teacher)
        cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Other cohort',capacity=10,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        self.assertEqual(self.post(f'/features/catalogue/live/{self.live.id}/edit',{**self.payload,'cohort_id':cohort.id}).status_code,400)
        self.live.end_at=timezone.now()-timedelta(seconds=1);self.live.save()
        self.client.force_login(self.learner)
        self.assertFalse(self.get(f'/features/live/{self.live.id}/room')['open'])
        self.assertEqual(self.post(f'/features/live/{self.live.id}/room',{'action':'chat','body':'Late message'}).status_code,400)
        self.assertEqual(self.post(f'/features/live/{self.live.id}/room',{'action':'leave'}).status_code,200)
