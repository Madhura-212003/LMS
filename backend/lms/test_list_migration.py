from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class EvidenceMigrationTests(TransactionTestCase):
    def test_backfill_preserves_existing_answers_scores_and_relationships(self):
        executor=MigrationExecutor(connection)
        executor.migrate([('lms','0011_scoped_staff_roles')])
        try:
            old=executor.loader.project_state([('lms','0011_scoped_staff_roles')]).apps
            user=old.get_model('auth','User').objects.create(username='existing-learner')
            course=old.get_model('lms','Course').objects.create(owner_id=user.id,title='Existing course',description='Content')
            quiz=old.get_model('lms','Quiz').objects.create(course_id=course.id,title='Existing exam')
            question=old.get_model('lms','Question').objects.create(quiz_id=quiz.id,prompt='Pick',options=['A','B'],answer=0,topic='Topic')
            attempt=old.get_model('lms','Attempt').objects.create(quiz_id=quiz.id,user_id=user.id,answers={str(question.id):0},score=4,status='Submitted',submitted_at=timezone.now())
            executor=MigrationExecutor(connection);executor.migrate([('lms','0013_backfill_question_evidence')])
            state=executor.loader.project_state([('lms','0013_backfill_question_evidence')]).apps
            restored=state.get_model('lms','Attempt').objects.get(pk=attempt.id)
            self.assertEqual(restored.answers,{str(question.id):0});self.assertEqual(restored.score,4)
            self.assertEqual(restored.user_id,user.id);self.assertEqual(restored.quiz_id,quiz.id)
            evidence=state.get_model('lms','QuestionEvidence').objects.get(attempt_id=attempt.id)
            self.assertTrue(evidence.is_correct);self.assertTrue(evidence.was_answered)
        finally:
            executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
