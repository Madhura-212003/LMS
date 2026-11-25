from datetime import timedelta
from urllib.parse import quote
from django.contrib.auth.models import User
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import Profile,Course,Cohort,Enrolment,Lesson,Translation,CourseStaffAssignment,Preference


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class LanguageWorkflowTests(TestCase):
    def setUp(self):
        self.actors={}
        for role in ('Teacher','Learner','Translator','Reviewer','Coordinator','Admin'):
            user=User.objects.create_user(role,first_name=role);Profile.objects.create(user=user,role=role);self.actors[role]=user
        self.course=Course.objects.create(owner=self.actors['Teacher'],title='Course',status='Published')
        co=Cohort.objects.create(course=self.course,teacher=self.actors['Teacher'],name='Cohort',capacity=20,start_date=timezone.localdate(),end_date=timezone.localdate()+timedelta(days=20))
        Enrolment.objects.create(cohort=co,user=self.actors['Learner'])
        for role in ('Translator','Reviewer'):CourseStaffAssignment.objects.create(course=self.course,user=self.actors[role],granted_by=self.actors['Admin'])
        self.lesson=Lesson.objects.create(course=self.course,author=self.actors['Teacher'],title='Lesson',body='Source',status='Published')

    def login(self,role):self.client.force_login(self.actors[role])
    def post(self,path,data=None):return self.client.post('/api/lms'+path,data or {},content_type='application/json')
    def get(self,path):
        r=self.client.get('/api/lms'+path);self.assertEqual(r.status_code,200,r.content);return r.json()

    def test_manifest_roles_and_saved_language_without_fixed_catalogue(self):
        self.login('Learner');self.post('/features/preferences',{'goals':'Keep my goal','language':'Konkani'})
        data=self.get('/language-workflow')
        self.assertEqual([s['label'] for s in data['screens']],['Language Preference','Translated Content View','Translation Queue / Editor','Glossary and Coverage'])
        self.assertEqual([s['accessible'] for s in data['screens']],[True,True,False,False]);self.assertIn('Konkani',data['languages'])
        self.post('/features/preferences',{'language':'Hindi'})
        self.assertEqual(Preference.objects.get(user=self.actors['Learner']).goals,'Keep my goal')
        for role,expected in [('Translator',[False,False,True,False]),('Reviewer',[False,False,True,False]),('Coordinator',[False,False,True,True]),('Admin',[False,False,True,True])]:
            self.login(role);self.assertEqual([s['accessible'] for s in self.get('/language-workflow')['screens']],expected)

    def test_translation_review_resubmission_and_learner_fallback(self):
        self.login('Translator');r=self.post('/features/translations',{'lesson_id':self.lesson.id,'language':' Hindi ','body':'Translated','source_updated_at':self.lesson.updated_at.isoformat()})
        self.assertEqual(r.status_code,200,r.content);t=r.json()
        self.assertEqual(self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Stale draft','translation_updated_at':'old'}).status_code,400)
        self.login('Learner');self.post('/features/preferences',{'language':'Hindi'})
        for suffix in ('','?list_page=1'):
            rows=self.get('/features/translations'+suffix);row=(rows['items'] if suffix else rows)[0];self.assertIsNone(row['translation']);self.assertEqual(row['original'],'Source')
        self.login('Translator');self.assertEqual(self.post(f"/features/translations/{t['id']}/approve").status_code,403)
        self.login('Reviewer');self.assertEqual(self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Overwrite'}).status_code,403)
        self.assertEqual(self.post(f"/features/translations/{t['id']}/approve?updated_at=old").status_code,400)
        self.assertEqual(self.post(f"/features/translations/{t['id']}/approve?updated_at="+quote(t['updated_at'],safe='')).status_code,200)
        self.login('Learner');self.assertEqual(self.get('/features/translations?list_page=1')['items'][0]['translation']['body'],'Translated')
        self.login('Coordinator');self.assertEqual(self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Revised'}).status_code,200)
        self.login('Learner');self.assertIsNone(self.get('/features/translations?list_page=1')['items'][0]['translation'])

    def test_source_edit_invalidates_approval_and_old_source_draft(self):
        self.login('Coordinator');t=self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Translation'}).json();self.post(f"/features/translations/{t['id']}/approve")
        old=self.lesson.updated_at.isoformat();self.lesson.status='Draft';self.lesson.save()
        self.login('Teacher');r=self.post(f'/content/{self.lesson.id}/edit',{'course_id':self.course.id,'title':'Lesson','body':'Changed source','position':1})
        self.assertEqual(r.status_code,200,r.content);self.assertEqual(Translation.objects.get(pk=t['id']).status,'In translation')
        self.login('Coordinator');self.assertEqual(self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Old draft','source_updated_at':old}).status_code,400)

    def test_glossary_scope_filters_and_published_coverage(self):
        self.login('Coordinator')
        for language in ('Hindi','Kannada'):self.assertEqual(self.post('/features/glossary',{'term':'Term','definition':'Meaning','language':language}).status_code,200)
        for suffix in ('?language=Hindi','?language=Hindi&list_page=1'):
            rows=self.get('/features/glossary'+suffix);self.assertEqual(len(rows['items'] if 'list_page' in suffix else rows),1)
        self.assertEqual(self.post('/features/glossary',{'term':' ','definition':'Meaning','language':'Hindi'}).status_code,400)
        Lesson.objects.create(course=self.course,author=self.actors['Teacher'],title='Draft',body='Draft',status='Draft')
        t=self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Translation'}).json();self.post(f"/features/translations/{t['id']}/approve")
        row=self.get('/lists/translation_coverage?language=Hindi')['items'][0];self.assertEqual((row['total'],row['translated']),(1,1))
        for role in ('Learner','Translator','Reviewer','Teacher'):
            self.login(role);self.assertEqual(self.post('/features/glossary',{'term':'Term','definition':'Definition','language':'Hindi'}).status_code,403)
        Profile.objects.filter(user=self.actors['Translator']).update(campus='foreign')
        self.login('Translator');self.assertEqual(self.get('/features/translations?list_page=1')['items'],[])
        self.assertEqual(self.post('/features/translations',{'lesson_id':self.lesson.id,'language':'Hindi','body':'Foreign'}).status_code,403)
