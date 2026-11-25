from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Profile,Course,Cohort,Enrolment,Lesson,LessonCompletion,Activity,Quiz,Question,Attempt,Preference,Notification


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],PERSONALISATION_REVIEW_BELOW_PERCENT=80,PERSONALISATION_PACE_LIMITS={'Gentle':2,'Steady':4,'Intensive':8})
class PersonalisationWorkflowTests(TestCase):
    def setUp(self):
        self.teacher=self.actor('teacher','Teacher');self.coordinator=self.actor('coordinator','Coordinator');self.admin=self.actor('admin','Admin');self.student=self.actor('student','Learner');self.other=self.actor('other','Learner');self.foreign=self.actor('foreign','Teacher','elsewhere')
        self.course,self.cohort=self.enrolled_course('Main course')
        self.lesson=Lesson.objects.create(course=self.course,author=self.teacher,title='First lesson',body='Read the table.',status='Published')
        self.client.force_login(self.student)

    def actor(self,name,role,campus='main'):
        user=User.objects.create_user(name,first_name=name);Profile.objects.create(user=user,role=role,campus=campus);return user

    def enrolled_course(self,title):
        course=Course.objects.create(owner=self.teacher,title=title,description='Study',status='Published')
        cohort=Cohort.objects.create(course=course,teacher=self.teacher,name=title+' group',capacity=10,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=cohort,user=self.student)
        return course,cohort

    def post(self,path,body):
        return self.client.post('/api/lms'+path,data=body,content_type='application/json')

    def get(self,path):
        response=self.client.get('/api/lms'+path);self.assertEqual(response.status_code,200,response.content);return response.json()

    def test_partial_settings_keep_other_values_and_are_self_scoped(self):
        full={'goals':'Understand data','pace':'Gentle','language':'Kannada','notifications':False,'ui_language':'en'}
        self.assertEqual(self.post('/features/preferences',full).status_code,200)
        self.assertEqual(self.post('/features/preferences',{'ui_language':'kn','user_id':self.other.id}).status_code,200)
        saved=self.get('/features/preferences')
        for key,value in full.items():self.assertEqual(saved[key],'kn' if key=='ui_language' else value)
        self.assertFalse(Preference.objects.filter(user=self.other).exists())
        self.assertEqual(self.post('/features/preferences',{'pace':None}).status_code,400)
        self.assertEqual(self.post('/features/preferences',{'pace':'Unknown'}).status_code,400)
        self.assertEqual(self.get('/features/preferences')['pace'],'Gentle')
        self.client.force_login(self.admin)
        self.post('/features/preferences',{'goals':'My admin settings'})
        self.assertEqual(Preference.objects.get(user=self.student).goals,'Understand data')

    def test_goal_ranking_pace_and_exact_discussion_target_follow_saved_records(self):
        for index in range(3):
            course,_=self.enrolled_course(f'Other course {index}')
            Lesson.objects.create(course=course,author=self.teacher,title=f'General lesson {index}',body='Study',status='Published')
        discussion=Activity.objects.create(course=self.course,title='Astronomy focus',description='Discuss astronomy',status='Published',due_at=timezone.now()+timedelta(days=1))
        self.post('/features/preferences',{'goals':'Astronomy','pace':'Gentle'})
        plan=self.get('/features/personalisation/next')
        self.assertEqual(plan['limit'],2);self.assertEqual(len(plan['items']),2)
        self.assertEqual((plan['items'][0]['kind'],plan['items'][0]['id']),('activity',discussion.id))
        self.assertIn('astronomy',plan['items'][0]['goal_matches'])
        self.assertEqual(self.get(f'/features/activities/resources/{discussion.id}')['description'],'Discuss astronomy')
        self.assertEqual(self.post(f'/features/activities/{discussion.id}/posts',{'body':'My contribution'}).status_code,200)
        self.assertFalse(any(item['kind']=='activity' and item['id']==discussion.id for item in self.get('/features/personalisation/next')['items']))
        self.post('/features/preferences',{'pace':'Intensive'})
        self.assertEqual(self.get('/features/personalisation/next')['limit'],8)

    def test_latest_assessment_and_teacher_evidence_use_server_threshold(self):
        quiz=Quiz.objects.create(course=self.course,title='Review tables',status='Published',correct_marks=1,max_attempts=3)
        questions=[Question.objects.create(quiz=quiz,prompt=f'Question {i}',options=['A','B'],answer=0,topic='Tables') for i in range(4)]
        Attempt.objects.create(user=self.student,quiz=quiz,score=3,status='Submitted',submitted_at=timezone.now(),answers={str(q.id):0 if index<3 else 1 for index,q in enumerate(questions)})
        self.assertTrue(any(item['kind']=='quiz' for item in self.get('/features/personalisation/next')['items']))
        self.client.force_login(self.teacher)
        evidence=self.get('/final/class-topics?list_page=1')['items'][0]
        self.assertEqual(evidence['accuracy'],75);self.assertEqual(evidence['status'],'Needs practice')
        self.assertEqual(self.get('/final/class-topics')[0]['status'],'Needs practice')
        self.client.force_login(self.student)
        quiz.max_attempts=1;quiz.save()
        self.assertFalse(any(item['kind']=='quiz' for item in self.get('/features/personalisation/next')['items']))
        quiz.max_attempts=3;quiz.save()
        Attempt.objects.create(user=self.student,quiz=quiz,score=4,status='Submitted',submitted_at=timezone.now(),answers={str(q.id):0 for q in questions})
        self.assertFalse(any(item['kind']=='quiz' for item in self.get('/features/personalisation/next')['items']))

    def test_current_completion_insights_exclude_drafts_and_removed_enrolments(self):
        LessonCompletion.objects.create(lesson=self.lesson,user=self.student)
        draft=Lesson.objects.create(course=self.course,author=self.teacher,title='Withdrawn',body='Private',status='Draft')
        LessonCompletion.objects.create(lesson=draft,user=self.student)
        Enrolment.objects.create(cohort=self.cohort,user=self.other,status='Removed')
        LessonCompletion.objects.create(lesson=self.lesson,user=self.other)
        self.client.force_login(self.teacher)
        row=self.get('/lists/lesson_insights')['items'][0]
        self.assertEqual((row['learners'],row['lessons'],row['completed_lessons']),(1,1,1))
        legacy=self.get('/features/insights/lessons')[0]
        self.assertEqual(legacy['completed_lessons'],1)
        empty=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Empty cohort',capacity=10,start_date=self.cohort.start_date,end_date=self.cohort.end_date)
        scoped=self.get(f'/lists/lesson_insights?cohort_id={empty.id}')['items'][0]
        self.assertEqual((scoped['learners'],scoped['completed_lessons']),(0,0))
        self.client.force_login(self.foreign)
        self.assertEqual(self.get('/lists/lesson_insights')['total'],0)

    def test_new_announcements_respect_notification_opt_out(self):
        self.post('/features/preferences',{'notifications':False})
        self.client.force_login(self.teacher)
        announcement=self.post('/features/announcements',{'course_id':self.course.id,'title':'Update','body':'Course update'})
        self.assertEqual(announcement.status_code,200,announcement.content)
        self.assertFalse(Notification.objects.filter(user=self.student).exists())
        self.client.force_login(self.student);self.post('/features/preferences',{'notifications':True})
        self.client.force_login(self.teacher)
        self.post('/features/announcements',{'course_id':self.course.id,'title':'Next update','body':'New course update'})
        self.assertEqual(Notification.objects.filter(user=self.student).count(),1)

    def test_manifest_roles_and_private_recommendation_endpoint(self):
        learner=self.get('/personalisation-workflow')
        self.assertEqual([(screen['label'],screen['role']) for screen in learner['screens']],[('Learner What Next','Learner'),('Teacher Class Insights','Teacher / Coordinator'),('Personalisation Settings','Learner / Admin')])
        self.assertEqual([screen['accessible'] for screen in learner['screens']],[True,False,True])
        self.assertEqual(learner['review_below_percent'],80)
        self.assertEqual(self.client.get('/api/lms/final/class-topics?list_page=1').status_code,403)
        self.client.force_login(self.coordinator)
        self.assertEqual([screen['accessible'] for screen in self.get('/personalisation-workflow')['screens']],[False,True,False])
        self.assertEqual(self.client.get('/api/lms/features/personalisation/next').status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual([screen['accessible'] for screen in self.get('/personalisation-workflow')['screens']],[False,True,True])
