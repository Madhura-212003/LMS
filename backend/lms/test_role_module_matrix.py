"""All ten actors cross all 25 module read seams, plus capability write denials.

These are isolated HTTP integration checks, not live provider/browser certification.
"""
from datetime import timedelta
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import *
from .permissions import ROLES


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class EveryRoleModuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actors={}
        for role in ROLES:
            user=User.objects.create_user(role,password='test',first_name=role)
            Profile.objects.create(user=user,role=role)
            cls.actors[role]=user
        teacher=cls.actors['Teacher'];learner=cls.actors['Learner'];now=timezone.now()
        cls.course=Course.objects.create(owner=teacher,title='Visible course',description='Course',status='Published')
        cls.cohort=Cohort.objects.create(course=cls.course,teacher=teacher,name='Cohort',capacity=30,start_date=now.date(),end_date=now.date()+timedelta(days=30))
        Enrolment.objects.create(user=learner,cohort=cls.cohort)
        for role in ('Author','Reviewer','TA','Translator'):
            CourseStaffAssignment.objects.create(course=cls.course,user=cls.actors[role],granted_by=cls.actors['Admin'])
        cls.lesson=Lesson.objects.create(course=cls.course,author=teacher,title='Lesson',body='Published source',status='Published')
        cls.assignment=Assignment.objects.create(course=cls.course,title='Assignment',instructions='Write',due_at=now+timedelta(days=1))
        Submission.objects.create(assignment=cls.assignment,user=learner,body='PRIVATE LEARNER RESPONSE')
        cls.quiz=Quiz.objects.create(course=cls.course,title='Quiz')
        question=Question.objects.create(quiz=cls.quiz,prompt='Choose',options=['A','B'],answer=0)
        Attempt.objects.create(quiz=cls.quiz,user=learner,answers={str(question.pk):0},score=1,status='Submitted',submitted_at=now)
        LibraryResource.objects.create(course=cls.course,title='Library',body='Resource')
        LiveClass.objects.create(course=cls.course,cohort=cls.cohort,teacher=teacher,title='Live',start_at=now,end_at=now+timedelta(hours=1),status='Scheduled')
        file=Attachment.objects.create(course=cls.course,owner=teacher,file='fixture.mp4',name='video.mp4',mime='video/mp4')
        Lecture.objects.create(course=cls.course,title='Lecture',attachment=file)
        path=LearningPath.objects.create(course=cls.course,title='Path')
        PathStep.objects.create(path=path,title='Read',position=1,kind='lesson',reference=cls.lesson.pk)
        Activity.objects.create(course=cls.course,title='Activity',description='Discuss',due_at=now+timedelta(days=1))
        CodingProblem.objects.create(course=cls.course,title='Coding',tests=[{'input':'','output':'5'}])
        ProgrammingLab.objects.create(course=cls.course,title='Lab',steps=['Observe'])
        DigitalSkill.objects.create(course=cls.course,title='Skill',steps=['Practice'])
        for module in (172,176,177,178):PracticePrompt.objects.create(course=cls.course,title=f'Practice {module}',module=module)
        for module in range(173,178):
            quiz=Quiz.objects.create(course=cls.course,title=f'Quiz {module}')
            Question.objects.create(quiz=quiz,prompt='Choose',options=['A','B'],answer=0)
            ExamPack.objects.create(course=cls.course,title=f'Exam {module}',module=module,quiz=quiz)
        Credential.objects.create(course=cls.course,title='Credential',description='Complete')
        MarketplaceListing.objects.create(course=cls.course,seller=teacher,price=0)
        foreign=Course.objects.create(owner=teacher,title='FOREIGN SECRET',tenant='foreign',status='Published')
        Lesson.objects.create(course=foreign,author=teacher,title='FOREIGN SECRET',body='FOREIGN SECRET',tenant='foreign',status='Published')

    def test_all_250_role_module_read_combinations(self):
        paths={156:'/courses?list_page=1',157:'/content?list_page=1',158:'/features/catalogue/library?list_page=1',159:'/features/catalogue/live?list_page=1',160:'/features/catalogue/lectures?list_page=1',161:'/features/catalogue/paths?list_page=1',162:'/features/preferences',163:'/features/tutor/policies',164:'/features/translations?list_page=1',165:'/assignments?list_page=1',166:'/lists/submissions',167:'/features/catalogue/activities?list_page=1',168:'/quizzes?list_page=1',169:'/features/catalogue/coding?list_page=1',170:'/features/catalogue/labs?list_page=1',171:'/features/catalogue/skills?list_page=1',172:'/features/catalogue/practice?list_page=1&module=172',173:'/features/catalogue/exams?list_page=1&module=173',174:'/features/catalogue/exams?list_page=1&module=174',175:'/features/catalogue/exams?list_page=1&module=175',176:'/features/catalogue/exams?list_page=1&module=176',177:'/features/catalogue/exams?list_page=1&module=177',178:'/features/catalogue/practice?list_page=1&module=178',179:'/credentials?list_page=1',180:'/features/marketplace?list_page=1'}
        for role,user in self.actors.items():
            self.client.force_login(user)
            for module,path in paths.items():
                with self.subTest(role=role,module=module):
                    response=self.client.get('/api/lms'+path)
                    self.assertEqual(response.status_code,200,response.content)
                    self.assertNotIn('FOREIGN SECRET',response.content.decode())
                    if module==166 and role not in ('Admin','Coordinator','Teacher','TA','Learner'):
                        self.assertEqual(response.json()['items'],[])
                    if role=='Learner' and module not in (162,163,166):
                        self.assertGreater(response.json()['total'],0,(module,response.content))

    def test_every_role_write_and_privileged_list_denials(self):
        actions=[('/content',{'course_id':self.course.pk,'title':'Draft','body':'Source'},{'Admin','Teacher','Author'}),('/assignments',{'course_id':self.course.pk,'title':'New assignment','instructions':'Write','total_marks':100,'due_at':(timezone.now()+timedelta(days=1)).isoformat()},{'Admin','Teacher'}),('/features/glossary',{'term':'Term','definition':'Definition','language':'Hindi'},{'Admin','Coordinator'}),('/features/marketplace/listings',{'course_id':self.course.pk,'price':'0'},{'Admin','Teacher','Seller'}),('/staff/courses/'+str(self.course.pk),{'user_id':self.actors['Author'].pk},{'Admin','Coordinator'})]
        reads=[('/staff/directory',{'Admin','Coordinator'}),('/features/question-bank?list_page=1',{'Admin','Teacher'}),('/features/marketplace/seller/dashboard?list_page=1',{'Admin','Teacher','Seller'})]
        for role,user in self.actors.items():
            self.client.force_login(user)
            for path,body,allowed in actions:
                if role in allowed:continue
                with self.subTest(role=role,action=path):
                    self.assertEqual(self.client.post('/api/lms'+path,body,content_type='application/json').status_code,403)
            for path,allowed in reads:
                with self.subTest(role=role,read=path):
                    self.assertEqual(self.client.get('/api/lms'+path).status_code,200 if role in allowed else 403)

    def test_all_staff_roles_rejected_for_learner_submissions(self):
        for role,user in self.actors.items():
            if role=='Learner':continue
            self.client.force_login(user)
            for path,body in [(f'/content/{self.lesson.pk}/complete',{}),(f'/quizzes/{self.quiz.pk}/attempts',{}),(f'/assignments/{self.assignment.pk}/submit',{'body':'Staff must not submit'})]:
                with self.subTest(role=role,path=path):
                    self.assertEqual(self.client.post('/api/lms'+path,body,content_type='application/json').status_code,403)

    def test_every_role_has_a_working_authorized_action(self):
        submission=Submission.objects.get(assignment=self.assignment)
        self.lesson.status='In Review';self.lesson.save()
        seller_course=Course.objects.create(owner=self.actors['Seller'],title='Seller course',status='Published')
        actions={
            'Admin':(f'/staff/courses/{self.course.pk}',{'user_id':self.actors['Author'].pk}),
            'Coordinator':(f'/staff/courses/{self.course.pk}',{'user_id':self.actors['TA'].pk}),
            'Teacher':('/assignments',{'course_id':self.course.pk,'title':'Teacher task','instructions':'Explain','total_marks':100,'due_at':(timezone.now()+timedelta(days=1)).isoformat()}),
            'Author':('/content',{'course_id':self.course.pk,'title':'Author draft','body':'Source lesson'}),
            'Reviewer':(f'/content/{self.lesson.pk}/review',{'decision':'Approved'}),
            'TA':(f'/submissions/{submission.pk}/mark',{'marks':75,'feedback':'Evidence reviewed'}),
            'Librarian':('/features/catalogue/library',{'course_id':self.course.pk,'title':'Librarian resource','description':'Instructions','body':'Study resource'}),
            'Translator':('/features/translations',{'lesson_id':self.lesson.pk,'language':'Hindi','body':'Translated source'}),
            'Seller':('/features/marketplace/listings',{'course_id':seller_course.pk,'price':'50'}),
            'Learner':(f'/assignments/{self.assignment.pk}/submit',{'body':'Learner response'}),
        }
        for role,(path,body) in actions.items():
            with self.subTest(role=role,path=path):
                if role=='Learner':
                    self.client.force_login(self.actors['TA'])
                    self.assertEqual(self.client.post(f'/api/lms/features/submissions/{submission.pk}/resubmit',{},content_type='application/json').status_code,200)
                self.client.force_login(self.actors[role])
                response=self.client.post('/api/lms'+path,body,content_type='application/json')
                self.assertEqual(response.status_code,200,response.content)
