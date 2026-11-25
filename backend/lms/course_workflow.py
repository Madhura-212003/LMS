"""Persisted course/cohort projections shared by learner and staff workflows."""
from django.db.models import Count, Q
from django.utils import timezone
from .models import Cohort, Enrolment, Lesson, LessonCompletion


COURSE_SCREENS = (
    ('Course catalogue', 'Course Catalogue', 'Learner', None),
    ('Course editor', 'Course Editor', 'Teacher', 'course_manage'),
    ('Cohort setup', 'Cohort Setup', 'Teacher', 'roster_manage'),
    ('Enrolment roster', 'Enrolment Roster', 'Coordinator', 'roster_manage'),
    ('My courses', 'My Courses', 'Learner', None),
    ('Teaching dashboard', 'Teaching Dashboard', 'Teacher', 'course_manage'),
)


def workflow_screens(user):
    from .permissions import permits
    return [{'tab': tab, 'label': label, 'role': role,
             'accessible': capability is None or permits(user, capability)}
            for tab, label, role, capability in COURSE_SCREENS]


def cohort_row(cohort, user):
    counts = cohort.enrolment_set.aggregate(
        occupied=Count('pk', filter=Q(status__in=['Enrolled', 'Completed'])),
        waiting=Count('pk', filter=Q(status='Waitlisted')))
    own = cohort.enrolment_set.filter(user=user).first()
    ended = cohort.end_date < timezone.localdate()
    return {'id': cohort.id, 'course_id': cohort.course_id, 'course_title': cohort.course.title,
            'name': cohort.name, 'teacher_id': cohort.teacher_id,
            'teacher': cohort.teacher.first_name or cohort.teacher.username,
            'capacity': cohort.capacity, 'occupied': counts['occupied'], 'waitlisted': counts['waiting'],
            'available_seats': max(0, cohort.capacity - counts['occupied']),
            'start_date': str(cohort.start_date), 'end_date': str(cohort.end_date),
            'status': 'Ended' if ended else 'Upcoming' if cohort.start_date > timezone.localdate() else 'Active',
            'enrolment_status': own.status if own else None,
            'can_join': not ended and cohort.course.status == 'Published' and not cohort.course.is_deleted
                        and user.is_active and (not own or own.status == 'Removed')}


def course_cohorts(course, user):
    return [cohort_row(c, user) for c in Cohort.objects.filter(course=course).select_related('course', 'teacher').order_by('start_date', 'id')]


def teaching_metrics(course):
    enrolments = Enrolment.objects.filter(cohort__course=course)
    active = enrolments.filter(status__in=['Enrolled', 'Completed'])
    total = Lesson.objects.filter(course=course, status='Published').count()
    learners = active.values('user_id').distinct().count()
    completed = LessonCompletion.objects.filter(lesson__course=course, lesson__status='Published', user_id__in=active.values('user_id')).count()
    return {'cohorts': Cohort.objects.filter(course=course).count(), 'learners': learners,
            'waitlisted': enrolments.filter(status='Waitlisted').count(), 'published_lessons': total,
            'average_progress': round(100 * completed / (total * learners)) if total and learners else 0}
