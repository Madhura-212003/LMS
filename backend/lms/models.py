import uuid
from django.conf import settings
from django.db import models


class Profile(models.Model):
    roles = models.JSONField(default=list,db_default=[])
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=24, default='Learner')
    tenant = models.CharField(max_length=80, default='demo')
    campus = models.CharField(max_length=80, default='main')
    class Meta:
        indexes=[models.Index(fields=['tenant','campus','role'],name='profile_scope_role')]


class LoginThrottle(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True)


class Scoped(models.Model):
    tenant = models.CharField(max_length=80, default='demo')
    campus = models.CharField(max_length=80, default='main')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Course(Scoped):
    cover = models.ForeignKey('lms.Attachment',null=True,blank=True,on_delete=models.PROTECT,related_name='course_covers')
    duration_minutes = models.PositiveIntegerField(default=0,db_default=0)
    title = models.CharField(max_length=200)
    description = models.TextField()
    outcomes = models.JSONField(default=list)
    modules = models.JSONField(default=list)
    subject = models.CharField(max_length=80, default='Technology')
    level = models.CharField(max_length=40, default='Beginner')
    status = models.CharField(max_length=24, default='Draft')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    is_deleted = models.BooleanField(default=False)
    class Meta:
        indexes=[models.Index(fields=['tenant', 'campus', 'status', 'title', 'id'],name='course_scope_status_title')]


class Cohort(Scoped):
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    capacity = models.PositiveIntegerField(default=30)
    start_date = models.DateField()
    end_date = models.DateField()
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Enrolment(models.Model):
    cohort = models.ForeignKey(Cohort, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, default='Enrolled')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['cohort', 'user'], name='unique_enrolment')]


class Lesson(Scoped):
    quiz_links = models.JSONField(default=list,db_default=[])
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    body = models.TextField()
    position = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=24, default='Draft')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    attachments = models.JSONField(default=list)
    class Meta:
        indexes=[models.Index(fields=['course', 'status', 'title', 'id'],name='lesson_course_status_title')]


class ContentReview(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=32)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LessonCompletion(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['lesson', 'user'], name='unique_completion')]


class Assignment(Scoped):
    status = models.CharField(max_length=24,default='Published',db_default='Published')
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    due_at = models.DateTimeField()
    total_marks = models.PositiveIntegerField(default=100)
    attachments = models.JSONField(default=list)
    class Meta:
        indexes=[models.Index(fields=['course', 'status', 'due_at', 'id'],name='assignment_course_status_due')]


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    status = models.CharField(max_length=24, default='Submitted')
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks = models.FloatField(null=True)
    feedback = models.TextField(blank=True)
    attachments = models.JSONField(default=list)
    marker = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='markings')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['assignment', 'user'], name='unique_submission')]


class Quiz(Scoped):
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    time_limit_min = models.PositiveIntegerField(default=15)
    max_attempts = models.PositiveIntegerField(default=3)
    exam_type = models.CharField(max_length=24, default='Practice')
    correct_marks = models.FloatField(default=1)
    wrong_marks = models.FloatField(default=0)
    status = models.CharField(max_length=24, default='Published')
    class Meta:
        indexes=[models.Index(fields=['course', 'status', 'title', 'id'],name='quiz_course_status_title')]


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT)
    prompt = models.TextField()
    options = models.JSONField(default=list)
    answer = models.PositiveIntegerField()
    explanation = models.TextField(blank=True)
    topic = models.CharField(max_length=100,default='General')
    difficulty = models.CharField(max_length=30,default='Beginner')
    kind = models.CharField(max_length=20,default='Single choice',db_default='Single choice')
    answer_set = models.JSONField(default=list,db_default=[])
    numeric_answer = models.FloatField(null=True)
    tolerance = models.FloatField(default=0,db_default=0)
    correct_marks = models.FloatField(null=True)
    wrong_marks = models.FloatField(null=True)


class Attempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True)
    answers = models.JSONField(default=dict)
    score = models.FloatField(null=True)
    status = models.CharField(max_length=24, default='In Progress')


class Credential(Scoped):
    title = models.CharField(max_length=200)
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    description = models.TextField()


class CredentialAward(models.Model):
    credential = models.ForeignKey(Credential, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    awarded_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['credential', 'user'], name='unique_award')]


class Certificate(models.Model):
    award = models.OneToOneField(CredentialAward, on_delete=models.PROTECT)
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=24, default='Valid')


class AuditLog(Scoped):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=80)
    entity_id = models.CharField(max_length=80)
    details = models.JSONField(default=dict)


from .domain_models import *  # Register the remaining Section F domain models.
