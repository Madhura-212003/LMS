from django.conf import settings
from django.db import models
from .models import Scoped


class CourseScoped(Scoped):
    course = models.ForeignKey('lms.Course', on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, default='Published')
    class Meta:
        abstract = True
        indexes=[models.Index(fields=['course','status','title','id'],name='%(class)s_list')]


class Attachment(Scoped):
    course = models.ForeignKey('lms.Course', on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='learning/%Y/%m/')
    mime = models.CharField(max_length=100)


class LibraryResource(CourseScoped):
    subject = models.CharField(max_length=100)
    language = models.CharField(max_length=50, default='English')
    resource_type = models.CharField(max_length=40, default='Article')
    body = models.TextField(blank=True)
    attachment = models.ForeignKey(Attachment, null=True, blank=True, on_delete=models.PROTECT)


class LibraryLoan(models.Model):
    resource = models.ForeignKey(LibraryResource, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, default='Saved')
    due_at = models.DateTimeField(null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['resource','user'], name='one_library_loan')]


class LiveClass(CourseScoped):
    cohort = models.ForeignKey('lms.Cohort', on_delete=models.PROTECT)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    meeting_url = models.URLField(blank=True)


class Attendance(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=20, default='Present')
    hand_raised = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['live_class','user'], name='one_attendance')]


class RoomMessage(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Lecture(CourseScoped):
    attachment = models.ForeignKey(Attachment, on_delete=models.PROTECT)
    captions = models.ForeignKey(Attachment, null=True, blank=True, on_delete=models.PROTECT, related_name='caption_lectures')
    topic = models.CharField(max_length=100, blank=True)


class LectureProgress(models.Model):
    lecture = models.ForeignKey(Lecture, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    position = models.FloatField(default=0)
    completed = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['lecture','user'], name='one_lecture_progress')]


class LearningPath(CourseScoped):
    pass


class PathStep(models.Model):
    path = models.ForeignKey(LearningPath, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    reference = models.PositiveBigIntegerField()
    position = models.PositiveIntegerField()
    title = models.CharField(max_length=200)


class PathProgress(models.Model):
    path = models.ForeignKey(LearningPath, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    started_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['path','user'], name='one_path_progress')]


class Preference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    goals = models.TextField(blank=True)
    pace = models.CharField(max_length=20, default='Steady')
    language = models.CharField(max_length=50, default='English')
    notifications = models.BooleanField(default=True)
    ui_language = models.CharField(max_length=10,default='en',db_default='en')


class FederatedIdentity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    directory_tenant = models.CharField(max_length=80)
    subject = models.CharField(max_length=128)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['directory_tenant','subject'],name='unique_federated_subject')]


class Translation(Scoped):
    lesson = models.ForeignKey('lms.Lesson', on_delete=models.PROTECT)
    language = models.CharField(max_length=50)
    body = models.TextField()
    status = models.CharField(max_length=24, default='In translation')
    translator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['lesson','language'], name='one_translation')]


class GlossaryTerm(Scoped):
    term = models.CharField(max_length=200)
    definition = models.TextField()
    language = models.CharField(max_length=50)


class TutorPolicy(Scoped):
    course = models.OneToOneField('lms.Course', on_delete=models.PROTECT)
    allowed_topics = models.JSONField(default=list)
    blocked_topics = models.JSONField(default=list)
    tone = models.CharField(max_length=100, default='Supportive')
    escalation = models.CharField(max_length=200, default='Ask your teacher for help.')


class TutorFlag(Scoped):
    course = models.ForeignKey('lms.Course', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    excerpt = models.TextField()
    reason = models.TextField()
    status = models.CharField(max_length=24, default='Flagged')
    decision = models.TextField(blank=True)


class Activity(CourseScoped):
    due_at = models.DateTimeField()
    groups = models.JSONField(default=list)


class ActivityGroup(models.Model):
    activity = models.ForeignKey(Activity,on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL,related_name='learning_groups')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['activity','name'],name='unique_activity_group')]


class ActivityPost(models.Model):
    activity = models.ForeignKey(Activity, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reactions = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='activity_reactions', blank=True)
    group = models.ForeignKey(ActivityGroup,null=True,blank=True,on_delete=models.PROTECT)


class CodingProblem(CourseScoped):
    topic = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=30, default='Beginner')
    language = models.CharField(max_length=30, default='Python subset')
    starter = models.TextField(blank=True)
    tests = models.JSONField(default=list)


class CodingAttempt(models.Model):
    problem = models.ForeignKey(CodingProblem, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    code = models.TextField()
    result = models.JSONField(default=dict)
    score = models.FloatField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)


class ProgrammingLab(CourseScoped):
    subject = models.CharField(max_length=100)
    difficulty = models.CharField(max_length=30, default='Beginner')
    steps = models.JSONField(default=list)
    starter = models.TextField(blank=True)
    language = models.CharField(max_length=30,default='Python',db_default='Python')


class LabSession(models.Model):
    inputs = models.TextField(blank=True,default='',db_default='')
    score = models.FloatField(null=True)
    feedback = models.TextField(blank=True,default='',db_default='')
    lab = models.ForeignKey(ProgrammingLab, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    observations = models.JSONField(default=dict)
    code = models.TextField(blank=True)
    output = models.TextField(blank=True)
    status = models.CharField(max_length=24, default='In progress')
    completed_at = models.DateTimeField(null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['lab','user'], name='one_lab_session')]


class DigitalSkill(CourseScoped):
    steps = models.JSONField(default=list)


class DigitalSkillProgress(models.Model):
    skill = models.ForeignKey(DigitalSkill, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    completed_steps = models.JSONField(default=list)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['skill','user'], name='one_skill_progress')]


class PracticePrompt(CourseScoped):
    module = models.PositiveIntegerField()
    practice_type = models.CharField(max_length=40, default='Writing')
    rubric = models.TextField(blank=True)


class PracticeSubmission(models.Model):
    prompt = models.ForeignKey(PracticePrompt, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField(blank=True)
    attachment = models.ForeignKey(Attachment, null=True, blank=True, on_delete=models.PROTECT)
    score = models.FloatField(null=True)
    feedback = models.TextField(blank=True)
    status = models.CharField(max_length=24, default='Submitted')
    submitted_at = models.DateTimeField(auto_now_add=True)


class ExamPack(CourseScoped):
    module = models.PositiveIntegerField()
    subject = models.CharField(max_length=100)
    level = models.CharField(max_length=50, default='Practice')
    quiz = models.OneToOneField('lms.Quiz', on_delete=models.PROTECT)


class PreviousPaper(Scoped):
    module = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    year = models.PositiveIntegerField()
    attachment = models.ForeignKey(Attachment, on_delete=models.PROTECT)
    solutions = models.ForeignKey(Attachment, null=True, on_delete=models.PROTECT, related_name='paper_solutions')


class MarketplaceListing(Scoped):
    course = models.OneToOneField('lms.Course', on_delete=models.PROTECT)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=24, default='Published')


class MarketplacePurchase(models.Model):
    listing = models.ForeignKey(MarketplaceListing, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['listing','user'], name='one_preview_purchase')]


class Reevaluation(models.Model):
    submission = models.ForeignKey('lms.Submission', on_delete=models.PROTECT)
    reason = models.TextField()
    status = models.CharField(max_length=24, default='Requested')
    created_at = models.DateTimeField(auto_now_add=True)


class MarkingHistory(models.Model):
    submission = models.ForeignKey('lms.Submission', on_delete=models.PROTECT)
    marker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    marks = models.FloatField()
    feedback = models.TextField()
    rubric = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class CredentialRule(models.Model):
    credential = models.OneToOneField('lms.Credential', on_delete=models.PROTECT)
    trigger = models.CharField(max_length=30, default='Course completion')
    threshold = models.FloatField(default=100)


class Announcement(Scoped):
    course = models.ForeignKey('lms.Course', on_delete=models.PROTECT)
    title = models.CharField(max_length=200)
    body = models.TextField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class Notification(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    read_at = models.DateTimeField(null=True)


class CourseReview(Scoped):
    course = models.ForeignKey('lms.Course',on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    rating = models.PositiveSmallIntegerField()
    body = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['course','user'],name='one_course_review'),models.CheckConstraint(condition=models.Q(rating__gte=1,rating__lte=5),name='course_rating_range')]


class CourseStaffAssignment(models.Model):
    course = models.ForeignKey('lms.Course',on_delete=models.PROTECT,related_name='staff_assignments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='course_assignments')
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='staff_grants')
    is_active = models.BooleanField(default=True,db_default=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['course','user'],name='unique_course_staff')]
        indexes=[models.Index(fields=['user','is_active','course'],name='staff_user_active_course')]


class QuestionEvidence(models.Model):
    attempt = models.ForeignKey('lms.Attempt',on_delete=models.PROTECT)
    question = models.ForeignKey('lms.Question',on_delete=models.PROTECT)
    topic = models.CharField(max_length=100)
    is_correct = models.BooleanField()
    was_answered = models.BooleanField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['attempt','question'],name='unique_question_evidence')]
        indexes = [models.Index(fields=['topic','is_correct'],name='evidence_topic_correct')]
