from datetime import timedelta
from urllib.parse import quote
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Profile,Course,Cohort,Enrolment,Lesson,LessonCompletion,Quiz,Question,ProgrammingLab,LearningPath,PathStep,PathProgress,AuditLog
from .permissions import permissions


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PathWorkflowTests(TestCase):
    def setUp(self):
        self.teacher=self.actor('teacher','Teacher');self.coordinator=self.actor('coordinator','Coordinator');self.student=self.actor('student','Learner');self.foreign=self.actor('foreign','Teacher','elsewhere')
        self.course=Course.objects.create(owner=self.teacher,title='Course',description='Learn',status='Published')
        self.cohort=Cohort.objects.create(course=self.course,teacher=self.teacher,name='Group',capacity=5,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=self.cohort,user=self.student)
        self.lesson=Lesson.objects.create(course=self.course,author=self.teacher,title='Read first',body='Data has rows.',status='Published')
        self.quiz=Quiz.objects.create(course=self.course,title='Recall',status='Published',time_limit_min=5)
        self.question=Question.objects.create(quiz=self.quiz,prompt='Choose',options=['A','B'],answer=0)
        self.lab=ProgrammingLab.objects.create(course=self.course,title='Experiment',description='Run',status='Published',steps=['Observe'],language='Python',starter='print(1)')
        self.steps=[{'kind':kind,'reference':obj.id,'title':obj.title} for kind,obj in [('lesson',self.lesson),('quiz',self.quiz),('lab',self.lab),('course',self.course)]]
        self.client.force_login(self.coordinator)

    def actor(self,name,role,campus='main'):
        user=User.objects.create_user(name,first_name=name);Profile.objects.create(user=user,role=role,campus=campus);return user

    def post(self,path,body=None):
        return self.client.post('/api/lms'+path,data=body or {},content_type='application/json')

    def get(self,path):
        response=self.client.get('/api/lms'+path);self.assertEqual(response.status_code,200,response.content);return response.json()

    def create(self,**overrides):
        payload={'course_id':self.course.id,'title':'Learning journey','description':'Ordered work','status':'Published','steps':self.steps,**overrides}
        response=self.post('/features/catalogue/paths',payload);self.assertEqual(response.status_code,200,response.content);return response.json(),payload

    def test_connected_lesson_quiz_lab_course_progress_and_teacher_report(self):
        path,_=self.create();pid=path['id'];self.client.force_login(self.student)
        steps=self.get(f'/features/paths/resources/{pid}')['steps']
        self.assertEqual(self.post(f"/features/paths/{pid}/steps/{steps[0]['id']}/open").status_code,400)
        self.assertEqual(self.post(f'/features/paths/{pid}/start').status_code,200)
        self.assertEqual(self.post(f"/features/paths/{pid}/steps/{steps[1]['id']}/open").status_code,403)
        opened=self.post(f"/features/paths/{pid}/steps/{steps[0]['id']}/open")
        self.assertEqual(opened.json()['reference'],self.lesson.id)
        self.assertEqual(self.post(f'/content/{self.lesson.id}/complete').status_code,200)
        self.assertEqual(self.post(f"/features/paths/{pid}/steps/{steps[1]['id']}/open").status_code,200)
        attempt=self.post(f'/quizzes/{self.quiz.id}/attempts').json()
        self.assertEqual(self.post(f"/attempts/{attempt['id']}/submit",{'answers':{str(self.question.id):0}}).status_code,200)
        target=self.post(f"/features/paths/{pid}/steps/{steps[2]['id']}/open").json()
        self.assertEqual((target['reference'],target['path_id']),(self.lab.id,pid))
        self.assertEqual(self.get(f'/features/labs/resources/{self.lab.id}')['id'],self.lab.id)
        response=self.post(f'/features/labs/{self.lab.id}/session',{'code':'print(1)','observations':{'0':'Observed 1'},'complete':True})
        self.assertEqual(response.status_code,200,response.content)
        completed=self.get(f'/features/paths/resources/{pid}')
        self.assertEqual(completed['completed_steps'],4);self.assertTrue(all(s['completed'] for s in completed['steps']))
        self.client.force_login(self.teacher)
        report=self.get(f'/lists/path_steps?path_id={pid}&cohort_id={self.cohort.id}')
        self.assertEqual(report['total'],4)
        self.assertTrue(all(row['status']=='Completed' and row['path_state']=='Started' for row in report['items']))

    def test_started_path_keeps_structure_and_allows_metadata_changes(self):
        path,payload=self.create();pid=path['id'];ids=list(PathStep.objects.filter(path_id=pid).order_by('position').values_list('id',flat=True))
        self.client.force_login(self.student)
        self.post(f'/features/paths/{pid}/start');self.post(f'/features/paths/{pid}/start')
        self.assertEqual(PathProgress.objects.filter(path_id=pid).count(),1)
        self.assertEqual(AuditLog.objects.filter(action='path.start',entity_id=str(PathProgress.objects.get(path_id=pid).id)).count(),1)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.post(f'/features/catalogue/paths/{pid}/edit',{**payload,'title':'Revised description'}).status_code,200)
        self.assertEqual(self.post(f'/features/catalogue/paths/{pid}/edit',{**payload,'title':'Should roll back','steps':list(reversed(self.steps))}).status_code,400)
        self.assertEqual(LearningPath.objects.get(pk=pid).title,'Revised description')
        self.assertEqual(list(PathStep.objects.filter(path_id=pid).order_by('position').values_list('id',flat=True)),ids)

    def test_publish_duplicate_and_unpublished_activity_validation(self):
        self.assertEqual(self.post('/features/catalogue/paths',{'course_id':self.course.id,'title':'Bad','steps':[self.steps[0],self.steps[0]]}).status_code,400)
        self.lesson.status='Draft';self.lesson.save()
        response=self.post('/features/catalogue/paths',{'course_id':self.course.id,'title':'Not ready','status':'Published','steps':self.steps})
        self.assertEqual(response.status_code,400)
        path,_=self.create(status='Draft')
        self.assertEqual(self.post(f"/features/catalogue/paths/{path['id']}/status",{'status':'Published'}).status_code,400)
        self.client.force_login(self.student)
        self.assertEqual(self.post(f"/features/paths/{path['id']}/start").status_code,403)

    def test_cross_course_activity_and_foreign_scope_denials(self):
        other=Course.objects.create(owner=self.teacher,title='Other course',description='Other',status='Published')
        lesson=Lesson.objects.create(course=other,author=self.teacher,title='Other lesson',body='Private',status='Published')
        path,_=self.create(steps=[{'kind':'lesson','reference':lesson.id,'title':lesson.title}]);pid=path['id']
        self.client.force_login(self.student);self.post(f'/features/paths/{pid}/start')
        step=self.get(f'/features/paths/resources/{pid}')['steps'][0]
        self.assertFalse(step['available'])
        self.assertEqual(self.post(f"/features/paths/{pid}/steps/{step['id']}/open").status_code,403)
        self.assertEqual(self.client.get('/api/lms/features/paths/options?kind=lesson&list_page=1').status_code,403)
        self.client.force_login(self.foreign)
        self.assertEqual(self.get('/features/paths/options?kind=lesson&list_page=1')['total'],0)
        self.assertEqual(self.client.get(f'/api/lms/features/paths/resources/{pid}').status_code,404)

    def test_manifest_coordinator_capability_and_activity_pagination(self):
        workflow=self.get('/path-workflow')
        self.assertEqual([(s['label'],s['role']) for s in workflow['screens']],[('Path Builder','Teacher / Coordinator / Admin'),('Teacher Path Progress','Teacher / Coordinator'),('Learner Path View','Learner'),('Path Catalogue / Search','Learner / Teacher')])
        self.assertIn('path_manage',permissions(self.coordinator));self.assertNotIn('assessment_write',permissions(self.coordinator))
        for i in range(23):Lesson.objects.create(course=self.course,author=self.teacher,title=f'Lesson {i:02}',body='Content',status='Published')
        first=self.get('/features/paths/options?kind=lesson&list_page=1')
        self.assertEqual(len(first['items']),20)
        second=self.get('/features/paths/options?kind=lesson&list_page=1&cursor='+quote(first['next_cursor']))
        self.assertEqual(len(first['items'])+len(second['items']),24)

    def test_course_step_requires_every_lesson_even_when_percentage_rounds_to_100(self):
        other=Course.objects.create(owner=self.teacher,title='Large course',description='Read all lessons',status='Published')
        cohort=Cohort.objects.create(course=other,teacher=self.teacher,name='Second group',capacity=5,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=30))
        Enrolment.objects.create(cohort=cohort,user=self.student)
        lessons=Lesson.objects.bulk_create([Lesson(course=other,author=self.teacher,title=f'Lesson {i}',body='Content',status='Published') for i in range(200)])
        LessonCompletion.objects.bulk_create([LessonCompletion(lesson=lesson,user=self.student) for lesson in lessons[:-1]])
        path,_=self.create(steps=[{'kind':'course','reference':other.id,'title':other.title}]);pid=path['id']
        self.client.force_login(self.student);self.post(f'/features/paths/{pid}/start')
        self.assertFalse(self.get(f'/features/paths/resources/{pid}')['steps'][0]['completed'])
        self.client.force_login(self.teacher)
        self.assertEqual(self.get(f'/lists/path_steps?path_id={pid}')['items'][0]['status'],'Pending')
