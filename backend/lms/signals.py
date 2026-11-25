from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Attempt,QuestionEvidence
from .assessment import correct,answered


@receiver(post_save,sender=Attempt)
def question_evidence(sender,instance,**kwargs):
    if instance.submitted_at is None:return
    rows=[]
    for q in instance.quiz.question_set.all():
        response=instance.answers.get(str(q.id))
        rows.append(QuestionEvidence(attempt=instance,question=q,topic=q.topic,is_correct=correct(q,response),was_answered=answered(response)))
    if rows:QuestionEvidence.objects.bulk_create(rows,update_conflicts=True,update_fields=['topic','is_correct','was_answered'],unique_fields=['attempt','question'])
