from datetime import timedelta
from django.db import transaction
from django.db.models import Exists,OuterRef
from django.utils import timezone
from ninja.errors import HttpError
from .models import *
from .assessment import correct,answered,validate_answer,maximum


def scope(user):
    p = user.profile
    return {'tenant': p.tenant, 'campus': p.campus}


def audit(user, action, obj, details=None):
    AuditLog.objects.create(user=user, action=action, entity_type=type(obj).__name__, entity_id=str(obj.pk), details=details or {}, **scope(user))


def require_role(user, *roles):
    if not __import__('lms.permissions',fromlist=['roles']).roles(user).intersection(roles):
        raise HttpError(403, 'Your role cannot perform this action')


def courses(user, catalogue=False):
    qs = Course.objects.filter(**scope(user), is_deleted=False)
    role = user.profile.role
    actor_roles=__import__('lms.permissions',fromlist=['roles']).roles(user)
    if catalogue:
        return qs.filter(status='Published')
    if actor_roles.intersection({'Admin','Coordinator'}) or actor_roles=={'Librarian'}:
        return qs
    if 'Seller' in actor_roles and not actor_roles.intersection({'Teacher','Author','Reviewer','TA','Translator'}):
        return qs.filter(owner=user)
    if actor_roles.intersection({'Teacher','Author','Reviewer','TA','Translator'}):
        return qs.annotate(_cohort_grant=Exists(Cohort.objects.filter(course_id=OuterRef('pk'),teacher=user)),_staff_grant=Exists(CourseStaffAssignment.objects.filter(course_id=OuterRef('pk'),user=user,is_active=True))).filter(models.Q(owner=user)|models.Q(_cohort_grant=True)|models.Q(_staff_grant=True))
    return qs.filter(Exists(Enrolment.objects.filter(cohort__course_id=OuterRef('pk'),user=user,status__in=['Enrolled','Completed'])))


def course_access(user, course_id, write=False):
    if __import__('lms.permissions',fromlist=['roles']).roles(user)=={'Librarian'}:raise HttpError(403,'This action is outside your library or translation role')
    if write:
        require_role(user, 'Admin', 'Teacher', 'Coordinator', 'Seller','Author','Reviewer','TA')
    try:
        return courses(user).get(pk=course_id)
    except Course.DoesNotExist:
        raise HttpError(403, 'You do not have access to this lesson or course')


def learner_course_access(user,course_id):
    require_role(user,'Learner')
    course=Course.objects.filter(pk=course_id,is_deleted=False,**scope(user)).filter(Exists(Enrolment.objects.filter(cohort__course_id=OuterRef('pk'),user=user,status__in=['Enrolled','Completed']))).first()
    if not course:raise HttpError(403,'You must be enrolled in this course to submit learner work')
    return course


@transaction.atomic
def enrol(user, cohort_id):
    require_role(user, 'Learner')
    try:
        cohort = Cohort.objects.select_for_update().get(pk=cohort_id, **scope(user), course__status='Published', course__is_deleted=False)
    except Cohort.DoesNotExist:
        raise HttpError(404, 'Cohort not available')
    existing = Enrolment.objects.filter(cohort=cohort, user=user).first()
    if existing and existing.status != 'Removed':
        return existing
    if not user.is_active:raise HttpError(400, 'Inactive learners cannot enrol')
    if cohort.end_date < timezone.localdate():raise HttpError(400, 'This cohort has ended')
    count = Enrolment.objects.filter(cohort=cohort, status__in=['Enrolled','Completed']).count()
    row, _ = Enrolment.objects.update_or_create(cohort=cohort, user=user, defaults={'status': 'Waitlisted' if count >= cohort.capacity else 'Enrolled', 'enrolled_at': timezone.now()})
    audit(user, 'enrol', row, {'status': row.status})
    return row


@transaction.atomic
def review(user, lesson, decision, comment):
    course_access(user, lesson.course_id, write=True)
    from .permissions import require
    require(user,'content_write' if decision=='In Review' else 'content_review')
    from .content_workflow import CONTENT_TRANSITIONS as transitions
    if decision not in transitions.get(lesson.status, []):
        raise HttpError(400, f'Cannot move {lesson.status} to {decision}')
    if decision == 'Needs Changes' and not comment.strip():
        raise HttpError(400, 'A review comment is required')
    previous = lesson.status
    lesson.status = decision
    lesson.save()
    ContentReview.objects.create(lesson=lesson, reviewer=user, decision=decision, comment=comment)
    audit(user, 'content.review', lesson, {'before': previous, 'after': decision, 'comment': comment})


def progress(user, course):
    total = Lesson.objects.filter(course=course, status='Published').count()
    done = LessonCompletion.objects.filter(user=user, lesson__course=course, lesson__status='Published').count()
    return round(done * 100 / total) if total else 0


@transaction.atomic
def complete(user, lesson):
    require_role(user, 'Learner')
    learner_course_access(user, lesson.course_id)
    if lesson.status != 'Published':
        raise HttpError(400, 'Only published lessons can be completed')
    row, created = LessonCompletion.objects.get_or_create(user=user, lesson=lesson)
    if created:
        audit(user, 'lesson.complete', row)
    evaluate_credentials(user,lesson.course)
    if progress(user, lesson.course) == 100:
        Enrolment.objects.filter(user=user, cohort__course=lesson.course, status='Enrolled').update(status='Completed')
    return progress(user, lesson.course)


def expired(attempt):
    return timezone.now() >= attempt.started_at + timedelta(minutes=attempt.quiz.time_limit_min)


@transaction.atomic
def finish_attempt(user, attempt_id, answers=None):
    a = Attempt.objects.select_for_update().select_related('quiz').get(pk=attempt_id, user=user)
    if a.submitted_at:
        return a
    # Never accept new answers after the server deadline. Score last saved answers.
    if answers is not None and not expired(a):
        validate_answers(a.quiz, answers)
        a.answers = answers
    score = 0
    for q in a.quiz.question_set.all():
        answer = a.answers.get(str(q.id))
        if answered(answer):
            score += (q.correct_marks if q.correct_marks is not None else a.quiz.correct_marks) if correct(q,answer) else (q.wrong_marks if q.wrong_marks is not None else a.quiz.wrong_marks)
    a.score = score
    a.submitted_at = timezone.now()
    a.status = 'Submitted'
    a.save()
    audit(user, 'quiz.submit', a, {'score': score})
    evaluate_credentials(user,a.quiz.course)
    return a


def evaluate_credentials(user,course):
    for credential in Credential.objects.filter(course=course):
        rule=CredentialRule.objects.filter(credential=credential).first()
        trigger,threshold=(rule.trigger,rule.threshold) if rule else ('Course completion',100)
        met=progress(user,course)>=threshold if trigger=='Course completion' else False
        if trigger=='Quiz score':
            for attempt in Attempt.objects.filter(user=user,quiz__course=course,submitted_at__isnull=False):
                max_score=maximum(attempt.quiz)
                if max_score and attempt.score*100/max_score>=threshold:met=True
        if trigger=='Assignment score':
            met=any(s.marks is not None and s.marks*100/s.assignment.total_marks>=threshold for s in Submission.objects.filter(user=user,assignment__course=course,status='Marked').select_related('assignment'))
        if met:
            award,new=CredentialAward.objects.get_or_create(credential=credential,user=user)
            if new:
                cert=Certificate.objects.create(award=award)
                audit(user,'credential.award',award)
                audit(user,'certificate.issue',cert)


def validate_answers(quiz, answers):
    questions = {str(q.id): q for q in quiz.question_set.all()}
    for key, value in answers.items():
        if key not in questions:
            raise HttpError(400, 'Invalid question or answer option')
        validate_answer(questions[key],value)
