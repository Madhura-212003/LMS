from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Course, Cohort, Enrolment, Profile, Lesson, LessonCompletion


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CourseEnrolmentWorkflowTests(TestCase):
    def setUp(self):
        self.teacher = self.actor('teacher', 'Teacher')
        self.coordinator = self.actor('coordinator', 'Coordinator')
        self.student = self.actor('student', 'Learner')
        self.waiting = self.actor('waiting', 'Learner')
        self.foreign = self.actor('foreign', 'Coordinator', campus='elsewhere')
        self.other_teacher = self.actor('other-teacher', 'Teacher')
        self.today = timezone.localdate()
        self.payload = {'title': 'Spreadsheet analysis', 'description': 'Analyze data',
                        'subject': 'Data', 'level': 'Foundation', 'outcomes': ['Interpret a table'],
                        'modules': ['Tables'], 'status': 'Draft', 'duration_minutes': 75}
        self.client.force_login(self.teacher)

    def actor(self, name, role, campus='main'):
        user = User.objects.create_user(name, first_name=name, email=name+'@example.test')
        Profile.objects.create(user=user, role=role, campus=campus)
        return user

    def post(self, path, body):
        return self.client.post('/api/lms'+path, data=body, content_type='application/json')

    def get(self, path):
        response = self.client.get('/api/lms'+path)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def course(self):
        response = self.post('/courses', self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        return Course.objects.get(pk=response.json()['id'])

    def cohort(self, course, name='Morning', capacity=1, **overrides):
        return Cohort.objects.create(course=course, teacher=self.teacher, name=name, capacity=capacity,
                                     start_date=self.today, end_date=self.today+timedelta(days=30), **overrides)

    def test_connected_workflow_with_waitlist_promotion_and_progress(self):
        course = self.course()
        self.client.force_login(self.student)
        self.assertEqual(self.get('/courses?catalogue=true&list_page=1')['total'], 0)
        self.client.force_login(self.teacher)
        body = {**self.payload, 'status': 'Published'}
        self.assertEqual(self.post(f'/features/courses/{course.id}/edit', body).status_code, 200)
        dates = {'start_date': str(self.today), 'end_date': str(self.today+timedelta(days=30))}
        response = self.post('/cohorts', {'course_id': course.id, 'name': 'Morning', 'capacity': 1, **dates})
        self.assertEqual(response.status_code, 200, response.content)
        morning = Cohort.objects.get(pk=response.json()['id'])
        evening = self.cohort(course, 'Evening')
        lesson = Lesson.objects.create(course=course, author=self.teacher, title='Tables', body='Learn tables', status='Published')
        self.client.force_login(self.student)
        item = self.get('/courses?catalogue=true&list_page=1')['items'][0]
        self.assertEqual({c['id'] for c in item['cohorts']}, {morning.id, evening.id})
        self.assertEqual(self.post(f'/cohorts/{evening.id}/enrolments', {}).json()['status'], 'Enrolled')
        self.assertFalse(Enrolment.objects.filter(cohort=morning, user=self.student).exists())
        self.client.force_login(self.waiting)
        self.assertEqual(self.post(f'/cohorts/{evening.id}/enrolments', {}).json()['status'], 'Waitlisted')
        waiting_row = self.get('/courses?mine=true&list_page=1')['items'][0]
        self.assertEqual(waiting_row['enrolment_status'], 'Waitlisted')
        self.assertFalse(waiting_row['enrolled'])
        self.assertEqual(self.client.get(f'/api/lms/courses/{course.id}').status_code, 403)
        self.client.force_login(self.coordinator)
        self.assertEqual(self.post(f'/features/cohorts/{evening.id}/enrolments', {'user_id': self.student.id, 'status': 'Removed'}).status_code, 200)
        roster = self.get(f'/lists/roster?cohort_id={evening.id}')['items']
        self.assertEqual(next(x for x in roster if x['user_id']==self.waiting.id)['status'], 'Enrolled')
        self.client.force_login(self.waiting)
        enrolled = self.get('/courses?mine=true&list_page=1')['items'][0]
        self.assertTrue(enrolled['enrolled'])
        self.assertEqual(self.post(f'/content/{lesson.id}/complete', {}).status_code, 200)
        self.assertEqual(self.get('/courses?mine=true&list_page=1')['items'][0]['progress'], 100)
        self.client.force_login(self.teacher)
        metrics = self.get('/final/teaching-courses?list_page=1')['items'][0]['metrics']
        self.assertEqual(metrics, {'cohorts': 2, 'learners': 1, 'waitlisted': 0, 'published_lessons': 1, 'average_progress': 100})
        self.assertEqual(LessonCompletion.objects.filter(user=self.waiting).count(), 1)

    def test_roster_repeat_preserves_completed_and_waiting_order(self):
        course = self.course()
        cohort = self.cohort(course)
        done = Enrolment.objects.create(cohort=cohort, user=self.student, status='Completed')
        waiting = Enrolment.objects.create(cohort=cohort, user=self.waiting, status='Waitlisted')
        before = waiting.enrolled_at
        for user in (self.student, self.waiting):
            response = self.post(f'/features/cohorts/{cohort.id}/enrolments', {'user_id': user.id, 'status': 'Enrolled'})
            self.assertEqual(response.status_code, 200, response.content)
        done.refresh_from_db(); waiting.refresh_from_db()
        self.assertEqual(done.status, 'Completed')
        self.assertEqual(waiting.status, 'Waitlisted')
        self.assertEqual(waiting.enrolled_at, before)

    def test_ended_cohort_blank_content_and_scope_are_rejected(self):
        response = self.post('/courses', {**self.payload, 'description': ' '})
        self.assertEqual(response.status_code, 400)
        course = self.course(); course.status = 'Published'; course.save()
        cohort = self.cohort(course)
        cohort.end_date = self.today-timedelta(days=1); cohort.save()
        self.client.force_login(self.student)
        item = self.get('/courses?catalogue=true&list_page=1')['items'][0]
        self.assertFalse(item['cohorts'][0]['can_join'])
        self.assertEqual(self.post(f'/cohorts/{cohort.id}/enrolments', {}).status_code, 400)
        self.assertEqual(self.post('/courses', self.payload).status_code, 403)
        self.client.force_login(self.foreign)
        self.assertEqual(self.get('/courses?list_page=1')['total'], 0)
        self.assertEqual(self.post(f'/features/cohorts/{cohort.id}/enrolments', {'user_id': self.student.id}).status_code, 404)
        self.client.force_login(self.other_teacher)
        self.assertEqual(self.get('/final/teaching-courses?list_page=1')['total'], 0)
        self.assertEqual(self.post(f'/features/courses/{course.id}/edit', self.payload).status_code, 403)

    def test_metadata_and_default_cohort_teacher_come_from_server(self):
        config = self.get('/course-workflow')
        self.assertEqual(config['default_course_status'], Course._meta.get_field('status').default)
        self.assertIn('course_manage', config['permissions'])
        course = self.course()
        self.client.force_login(self.coordinator)
        response = self.post('/cohorts', {'course_id': course.id, 'name': 'Group', 'capacity': 7,
                                         'start_date': str(self.today), 'end_date': str(self.today+timedelta(days=1))})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Cohort.objects.get(pk=response.json()['id']).teacher_id, self.teacher.id)

    def test_six_screen_manifest_keeps_roles_visible_without_granting_access(self):
        self.client.force_login(self.student)
        screens = self.get('/course-workflow')['screens']
        self.assertEqual([(s['label'], s['role']) for s in screens], [
            ('Course Catalogue', 'Learner'), ('Course Editor', 'Teacher'),
            ('Cohort Setup', 'Teacher'), ('Enrolment Roster', 'Coordinator'),
            ('My Courses', 'Learner'), ('Teaching Dashboard', 'Teacher')])
        self.assertEqual([s['label'] for s in screens if s['accessible']], ['Course Catalogue', 'My Courses'])
        self.assertEqual(self.post('/courses', self.payload).status_code, 403)
        self.client.force_login(self.teacher)
        self.assertTrue(all(s['accessible'] for s in self.get('/course-workflow')['screens']))
