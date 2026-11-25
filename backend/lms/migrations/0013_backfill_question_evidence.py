from django.db import migrations
import math


def populate(apps,schema_editor):
    Attempt=apps.get_model('lms','Attempt');Question=apps.get_model('lms','Question');Evidence=apps.get_model('lms','QuestionEvidence')
    alias=schema_editor.connection.alias
    for attempt in Attempt.objects.using(alias).filter(submitted_at__isnull=False).iterator(chunk_size=100):
        for q in Question.objects.using(alias).filter(quiz_id=attempt.quiz_id):
            response=attempt.answers.get(str(q.id));right=False
            if q.kind=='Multiple choice':right=isinstance(response,list) and set(response)==set(q.answer_set)
            elif q.kind=='Numerical':
                try:right=math.isclose(float(response),q.numeric_answer,rel_tol=0,abs_tol=q.tolerance)
                except (TypeError,ValueError,OverflowError):pass
            else:right=response==q.answer
            Evidence.objects.using(alias).get_or_create(attempt_id=attempt.id,question_id=q.id,defaults={'topic':q.topic,'is_correct':right,'was_answered':response is not None and response!='' and response!=[]})


class Migration(migrations.Migration):
    dependencies=[('lms','0012_question_evidence')]
    operations=[migrations.RunPython(populate,migrations.RunPython.noop)]
