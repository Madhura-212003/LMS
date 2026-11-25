"""Saved-preference policy and deterministic, record-based next steps."""
import re
from django.conf import settings
from django.utils import timezone
from .models import Preference,Lesson,Attempt,Activity
from .services import courses
from .permissions import roles,permits

UI_LANGUAGES={'en':'English','hi':'हिन्दी','kn':'ಕನ್ನಡ'}
PACES=('Gentle','Steady','Intensive')
PREFERENCE_FIELDS=('goals','pace','language','notifications','ui_language')


def preference_values(user):
    row=Preference.objects.filter(user=user).first()
    return {key:getattr(row,key) if row else Preference._meta.get_field(key).get_default() for key in PREFERENCE_FIELDS}


def workflow(user):
    actor=roles(user);learner='Learner' in actor
    insights=bool(actor&{'Admin','Teacher','Coordinator'}) and permits(user,'teaching_read')
    settings_allowed=bool(actor&{'Learner','Admin'})
    return {'module_id':162,'screens':[
        {'tab':'Learner what next','label':'Learner What Next','role':'Learner','accessible':learner},
        {'tab':'Teacher class insights','label':'Teacher Class Insights','role':'Teacher / Coordinator','accessible':insights},
        {'tab':'Personalisation settings','label':'Personalisation Settings','role':'Learner / Admin','accessible':settings_allowed}],
        'can_recommend':learner,'can_inspect':insights,'can_edit_settings':settings_allowed,
        'pace_options':[{'value':pace,'limit':settings.PERSONALISATION_PACE_LIMITS[pace]} for pace in PACES],
        'ui_languages':[{'value':key,'label':label} for key,label in UI_LANGUAGES.items()],
        'review_below_percent':settings.PERSONALISATION_REVIEW_BELOW_PERCENT}


def next_steps(user):
    from .assessment import maximum
    preferences=preference_values(user)
    limit=settings.PERSONALISATION_PACE_LIMITS.get(preferences['pace'],settings.PERSONALISATION_PACE_LIMITS['Steady'])
    terms={term for term in re.findall(r'\w+',preferences['goals'].casefold()) if len(term)>=3}
    allowed=courses(user);rows=[]
    def add(row,text):
        matches=sorted(term for term in terms if term in text.casefold())
        row['goal_matches']=matches
        rows.append(row)
    for course in allowed.order_by('title','id'):
        lesson=Lesson.objects.filter(course=course,status='Published').exclude(lessoncompletion__user=user).order_by('position','id').first()
        if lesson:add({'kind':'lesson','id':lesson.id,'course_id':course.id,'course_title':course.title,'title':lesson.title,'reason':'Next uncompleted lesson in '+course.title},lesson.title+' '+course.title+' '+course.description)
    seen=set()
    for attempt in Attempt.objects.filter(user=user,quiz__course__in=allowed,quiz__status='Published',submitted_at__isnull=False).select_related('quiz__course').order_by('-submitted_at','-id'):
        if attempt.quiz_id in seen:continue
        seen.add(attempt.quiz_id);total=maximum(attempt.quiz)
        if attempt.score is None or not total:continue
        attempts=Attempt.objects.filter(user=user,quiz=attempt.quiz)
        if attempts.count()>=attempt.quiz.max_attempts and not attempts.filter(submitted_at__isnull=True).exists():continue
        if 100*attempt.score/total<settings.PERSONALISATION_REVIEW_BELOW_PERCENT:
            add({'kind':'quiz','id':attempt.quiz_id,'course_id':attempt.quiz.course_id,'course_title':attempt.quiz.course.title,'title':attempt.quiz.title,'reason':f'Review this assessment: latest score {round(100*attempt.score/total)}%'},attempt.quiz.title+' '+attempt.quiz.course.title)
    activities=Activity.objects.filter(course__in=allowed,status='Published',due_at__gt=timezone.now()).exclude(activitypost__user=user).select_related('course').order_by('due_at','id')[:limit]
    for activity in activities:
        add({'kind':'activity','id':activity.id,'course_id':activity.course_id,'course_title':activity.course.title,'title':activity.title,'reason':'Upcoming discussion: contribute before '+timezone.localtime(activity.due_at).strftime('%d %b %H:%M')},activity.title+' '+activity.course.title+' '+activity.description)
    rows.sort(key=lambda row:-len(row['goal_matches']))
    return {'items':rows[:limit],'preferences':preferences,'limit':limit}
