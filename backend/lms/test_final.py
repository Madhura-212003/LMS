from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.utils import timezone
from .models import *
from . import test_features
from .services import enrol


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FinalConformanceTests(TestCase):
    setUp=test_features.FeatureWorkflowTests.setUp
    user=test_features.FeatureWorkflowTests.user
    post=test_features.FeatureWorkflowTests.post
    get=test_features.FeatureWorkflowTests.get
    create=test_features.FeatureWorkflowTests.create

    def final(self,path,data=None):
        return self.client.post('/api/lms/final'+path,data or {},content_type='application/json')

    def test_learner_sees_only_their_cohort_and_its_classes(self):
        other=Cohort.objects.create(course=self.course,name='Private cohort',teacher=self.teacher,capacity=3,start_date=self.cohort.start_date,end_date=self.cohort.end_date)
        for co in (self.cohort,other):LiveClass.objects.create(course=self.course,cohort=co,teacher=self.teacher,title=co.name,status='Scheduled',start_at=timezone.now(),end_at=timezone.now()+timedelta(hours=1))
        self.client.force_login(self.student)
        rows=self.client.get('/api/lms/cohorts').json()
        self.assertEqual([x['id'] for x in rows],[self.cohort.id])
        self.assertEqual(self.get('/catalogue/live').json()['total'],1)
        self.assertEqual(len(self.client.get('/api/lms/final/dashboard').json()['upcoming']),1)

    def test_waitlist_removal_does_not_overfill_and_reenrol_is_possible(self):
        self.cohort.capacity=1;self.cohort.save()
        Enrolment.objects.create(cohort=self.cohort,user=self.other,status='Waitlisted')
        third=self.user('third','Learner')
        Enrolment.objects.create(cohort=self.cohort,user=third,status='Waitlisted')
        self.post(f'/cohorts/{self.cohort.id}/enrolments',{'user_id':self.other.id,'status':'Removed'})
        self.assertEqual(self.cohort.enrolment_set.filter(status='Enrolled').count(),1)
        self.assertEqual(enrol(self.other,self.cohort.id).status,'Waitlisted')
        self.post(f'/cohorts/{self.cohort.id}/enrolments',{'user_id':self.student.id,'status':'Removed'})
        self.assertEqual(self.cohort.enrolment_set.filter(status='Enrolled').count(),1)

    def test_filters_apply_before_pagination_for_all_catalogue_dimensions(self):
        for i in range(23):CodingProblem.objects.create(course=self.course,title=f'A{i:02}',language='Python',topic='Arrays',difficulty='Beginner')
        target=CodingProblem.objects.create(course=self.course,title='Z target',language='Java',topic='Graphs',difficulty='Advanced')
        result=self.get('/catalogue/coding?language=Java&topic=Graphs&difficulty=Advanced').json()
        self.assertEqual(result['total'],1)
        self.assertEqual(result['items'][0]['id'],target.id)
        self.assertIn('Java',result['facets']['language'])

    def test_participation_includes_zero_contributors(self):
        activity=Activity.objects.create(course=self.course,title='Discussion',description='Discuss',due_at=timezone.now()+timedelta(days=1))
        rows=self.get('/activities/participation/all').json()
        self.assertEqual(rows,[{'activity__title':activity.title,'user__first_name':self.student.first_name,'posts':0,'replies':0,'reactions':0}])

    def test_live_class_uses_cohort_teacher_not_creator(self):
        self.client.force_login(self.admin)
        row=self.create('live',cohort_id=self.cohort.id,start_at=timezone.now().isoformat(),end_at=(timezone.now()+timedelta(hours=1)).isoformat())
        self.assertEqual(row['teacher'],self.teacher.id)

    def test_draft_assignment_cannot_be_read_or_submitted(self):
        a=Assignment.objects.create(course=self.course,title='Draft',instructions='Do it',due_at=timezone.now(),status='Draft')
        self.client.force_login(self.student)
        self.assertEqual(self.client.get('/api/lms/assignments').json(),[])
        response=self.client.post(f'/api/lms/assignments/{a.id}/submit',{'body':'Response'},content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertFalse(a.submission_set.exists())

    def test_assignment_edit_keeps_original_marking_scale(self):
        a=Assignment.objects.create(course=self.course,title='Assignment',instructions='Instructions',due_at=timezone.now(),total_marks=100)
        Submission.objects.create(assignment=a,user=self.student,body='Submitted')
        body={'title':'Revised title','instructions':'Updated instructions','due_at':(timezone.now()+timedelta(days=1)).isoformat(),'total_marks':50,'status':'Published'}
        self.assertEqual(self.final(f'/assignments/{a.id}/edit',body).status_code,400)
        a.refresh_from_db();self.assertEqual(a.title,'Assignment')
        body['total_marks']=100
        self.assertEqual(self.final(f'/assignments/{a.id}/edit',body).status_code,200)

    def test_quiz_review_is_own_and_closed_exam_marking_is_immutable(self):
        q=Quiz.objects.create(course=self.course,title='Quiz')
        question=Question.objects.create(quiz=q,prompt='Choose',options=['Yes','No'],answer=0)
        a=Attempt.objects.create(quiz=q,user=self.student,answers={str(question.id):1},score=0,submitted_at=timezone.now(),status='Submitted')
        self.client.force_login(self.student)
        response=self.client.get(f'/api/lms/final/attempts/{a.id}')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['questions'][0]['answer'],0)
        Enrolment.objects.create(cohort=self.cohort,user=self.other)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/api/lms/final/attempts/{a.id}').status_code,403)
        self.client.force_login(self.teacher)
        self.assertEqual(self.final(f'/quizzes/{q.id}/edit',{'title':'Changed','time_limit_min':15,'max_attempts':3,'correct_marks':2,'wrong_marks':0,'status':'Published'}).status_code,400)

    def test_completed_lab_retains_inputs_and_cannot_regress_and_can_be_marked(self):
        lab=ProgrammingLab.objects.create(course=self.course,title='Lab',subject='Programming',steps=['Run and observe'])
        self.client.force_login(self.student)
        with patch('lms.feature_api.execute',return_value='5'):
            row=self.post(f'/labs/{lab.id}/session',{'code':'print(input())','inputs':'5','observations':{'0':'Output is 5'},'complete':True}).json()
        self.assertEqual(row['inputs'],'5')
        self.assertEqual(self.post(f'/labs/{lab.id}/session',{'code':'print(0)','complete':False}).status_code,400)
        self.client.force_login(self.teacher)
        self.assertEqual(self.final(f'/labs/{row["id"]}/review',{'score':90,'feedback':'Clear observations'}).status_code,200)
        session=LabSession.objects.get(pk=row['id']);self.assertEqual(session.score,90);self.assertEqual(session.status,'Completed')

    def test_topic_insights_and_recommendation_use_positive_low_scores(self):
        q=Quiz.objects.create(course=self.course,title='Math',correct_marks=4)
        question=Question.objects.create(quiz=q,prompt='One',options=['Yes','No'],answer=0,topic='Arithmetic')
        Attempt.objects.create(quiz=q,user=self.student,answers={str(question.id):1},score=1,submitted_at=timezone.now(),status='Submitted')
        rows=self.client.get('/api/lms/final/class-topics').json()
        self.assertEqual(rows[0]['topic'],'Arithmetic');self.assertEqual(rows[0]['accuracy'],0)
        self.client.force_login(self.student)
        self.assertTrue(any(r['kind']=='quiz' for r in self.get('/recommendations').json()))

    def test_marketplace_reviews_require_enrolment_and_are_public_metadata(self):
        listing=MarketplaceListing.objects.create(course=self.course,seller=self.teacher,price=0)
        self.client.force_login(self.other)
        self.assertEqual(self.final(f'/courses/{self.course.id}/review',{'rating':5,'body':'Good'}).status_code,403)
        self.client.force_login(self.student)
        self.assertEqual(self.final(f'/courses/{self.course.id}/review',{'rating':5,'body':'Helpful'}).status_code,200)
        self.assertEqual(self.final(f'/courses/{self.course.id}/review',{'rating':4,'body':'Updated review'}).status_code,200)
        row=self.get('/marketplace').json()[0]
        self.assertEqual(row['rating'],4);self.assertEqual(len(row['reviews']),1)
        self.assertNotIn('email',str(row['reviews']))

    def test_lesson_quiz_links_reject_other_course(self):
        foreign=Course.objects.create(owner=self.teacher,title='Other')
        q=Quiz.objects.create(course=foreign,title='Foreign quiz')
        response=self.client.post('/api/lms/content',{'course_id':self.course.id,'title':'Lesson','body':'Content','quiz_links':[q.id]},content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_blank_course_updates_are_rejected(self):
        self.assertEqual(self.post(f'/courses/{self.course.id}/edit',{'title':' ','description':'Test','outcomes':[' '],'modules':['First'],'status':'Published'}).status_code,400)

    def test_empty_quiz_cannot_start_and_revoked_enrolment_cannot_save(self):
        q=Quiz.objects.create(course=self.course,title='Empty')
        self.client.force_login(self.student)
        self.assertEqual(self.client.post(f'/api/lms/quizzes/{q.id}/attempts').status_code,400)
        Question.objects.create(quiz=q,prompt='Choose',options=['A','B'],answer=0)
        a=Attempt.objects.create(quiz=q,user=self.student)
        self.student.enrolment_set.update(status='Removed')
        self.assertEqual(self.client.post(f'/api/lms/attempts/{a.id}/save',{'answers':{}},content_type='application/json').status_code,403)

    def test_supporting_lists_search_sort_signed_cursor_and_scope(self):
        for i in range(24):Assignment.objects.create(course=self.course,title=f'Task {i:02}',instructions='Work',due_at=timezone.now())
        response=self.client.get('/api/lms/assignments?list_page=1&_search=Task&_sort=-title').json()
        self.assertEqual(len(response['items']),20);self.assertEqual(response['total'],24)
        self.assertEqual(response['items'][0]['title'],'Task 23')
        cursor=response['next_cursor']
        second=self.client.get('/api/lms/assignments',{'list_page':'1','_search':'Task','_sort':'-title','cursor':cursor}).json()
        self.assertEqual(len(second['items']),4)
        self.assertEqual(self.client.get('/api/lms/assignments',{'list_page':'1','cursor':cursor+'bad'}).status_code,400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/api/lms/assignments?list_page=1').json()['total'],0)

    def test_question_edit_preserves_attempt_solutions(self):
        q=Quiz.objects.create(course=self.course,title='Quiz')
        question=Question.objects.create(quiz=q,prompt='Original',options=['A','B'],answer=0)
        body={'quiz_id':q.id,'prompt':'Revised','options':['A','B'],'answer':1}
        self.assertEqual(self.final(f'/question-bank/{question.id}/edit',body).status_code,200)
        Attempt.objects.create(quiz=q,user=self.student)
        body['prompt']='Changed after attempt'
        self.assertEqual(self.final(f'/question-bank/{question.id}/edit',body).status_code,400)
        question.refresh_from_db();self.assertEqual(question.prompt,'Revised')

    def test_translation_coverage_is_per_course_not_current_page(self):
        for i in range(22):Lesson.objects.create(course=self.course,author=self.teacher,title=f'Lesson {i}',body='Source',status='Published')
        Translation.objects.create(lesson=self.lesson,language='Hindi',body='Translated',translator=self.teacher,status='Translated')
        rows=self.client.get('/api/lms/final/translation-coverage?language=Hindi').json()
        self.assertEqual(rows[0]['total'],23);self.assertEqual(rows[0]['translated'],1)

    def test_attendance_correction_is_scoped_and_audited(self):
        live=LiveClass.objects.create(course=self.course,cohort=self.cohort,teacher=self.teacher,title='Live class',start_at=timezone.now()-timedelta(minutes=1),end_at=timezone.now()+timedelta(hours=1),status='Scheduled')
        self.assertEqual(self.get('/catalogue/live?status=Live').json()['total'],1)
        self.assertEqual(self.final(f'/live/{live.id}/attendance/{self.student.id}',{'status':'Absent'}).status_code,200)
        self.assertTrue(AuditLog.objects.filter(action='attendance.correct').exists())
        self.assertEqual(self.final(f'/live/{live.id}/attendance/{self.other.id}',{'status':'Present'}).status_code,404)
        self.client.force_login(self.student)
        self.assertEqual(self.final(f'/live/{live.id}/attendance/{self.student.id}',{'status':'Present'}).status_code,403)

    def test_exam_solution_reports_weak_topics_and_skills_include_not_started(self):
        q=Quiz.objects.create(course=self.course,title='Practice')
        question=Question.objects.create(quiz=q,prompt='Choose',options=['A','B'],answer=0,topic='Biology')
        a=Attempt.objects.create(quiz=q,user=self.student,answers={str(question.id):1},submitted_at=timezone.now(),score=0,status='Submitted')
        self.client.force_login(self.student)
        response=self.client.get(f'/api/lms/final/attempts/{a.id}')
        self.assertEqual(response.json()['weak_topics'],{'Biology':1})
        DigitalSkill.objects.create(course=self.course,title='Typing',steps=['First'])
        self.client.force_login(self.teacher)
        row=self.client.get('/api/lms/final/skill-progress').json()[0]
        self.assertEqual(row['learner'],self.student.first_name)
        self.assertEqual(row['status'],'Not started')

    def test_library_and_translation_roles_do_not_read_private_student_work(self):
        from django.core.files.base import ContentFile
        import tempfile
        a=Assignment.objects.create(course=self.course,title='Private task',instructions='Private',due_at=timezone.now())
        Submission.objects.create(assignment=a,user=self.student,body='Private response')
        with tempfile.TemporaryDirectory() as folder,self.settings(MEDIA_ROOT=folder):
            file=Attachment.objects.create(course=self.course,owner=self.student,name='private.txt',mime='text/plain')
            file.file.save('private.txt',ContentFile(b'Private response'))
            for role in ('Librarian','Translator'):
                user=self.user(role.lower(),role)
                self.client.force_login(user)
                self.assertEqual(self.client.get('/api/lms/assignments').json(),[])
                self.assertEqual(self.client.get('/api/lms/results').json(),[])
                self.assertEqual(self.get('/work/coding').json(),[])
                self.assertEqual(self.get(f'/files/{file.id}').status_code,403)
                self.assertTrue(all(not x['enrolments'] for x in self.client.get('/api/lms/cohorts').json()))

    def test_published_course_cover_is_available_to_catalogue_browsers(self):
        from django.core.files.base import ContentFile
        import tempfile
        with tempfile.TemporaryDirectory() as folder,self.settings(MEDIA_ROOT=folder):
            image=Attachment.objects.create(course=self.course,owner=self.teacher,name='cover.png',mime='image/png')
            image.file.save('cover.png',ContentFile(b'PNG fixture'))
            response=self.post(f'/courses/{self.course.id}/edit',{'title':self.course.title,'description':'Description','outcomes':['Outcome'],'modules':['Module'],'status':'Published','cover_id':image.id})
            self.assertEqual(response.status_code,200)
            self.client.force_login(self.other)
            response=self.get(f'/files/{image.id}')
            self.assertEqual(response.status_code,200);response.close()
            self.course.status='Draft';self.course.save()
            self.assertEqual(self.get(f'/files/{image.id}').status_code,403)
