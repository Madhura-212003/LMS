"""Live-class navigation and server-derived availability."""
from django.conf import settings
from django.utils import timezone
from .permissions import roles, permits
from .models import Enrolment


def can_schedule(user):
    return bool(roles(user)&{'Admin','Teacher','Coordinator'})


def workflow(user):
    learner='Learner' in roles(user)
    return {'module_id':159, 'screens':[
        {'tab':'Class schedule / Manage','label':'Class Schedule / Manage','role':'Teacher / Coordinator / Admin','accessible':can_schedule(user)},
        {'tab':'Live class room','label':'Live Class Room','role':'Learner / Teacher / TA','accessible':learner or permits(user,'classroom_manage')},
        {'tab':'Attendance summary','label':'Attendance Summary','role':'Teacher / Coordinator / Learner','accessible':learner or permits(user,'teaching_read')},
        {'tab':'Learner class schedule','label':'Learner Class Schedule','role':'Learner','accessible':learner or permits(user,'classroom_manage')}],
        'can_schedule':can_schedule(user), 'can_correct_attendance':permits(user,'classroom_manage'),
        'poll_ms':settings.LIVE_ROOM_POLL_SECONDS*1000, 'late_after_minutes':settings.LIVE_LATE_AFTER_MINUTES}


def availability(user,live):
    now=timezone.now()
    state=live.status
    if state=='Scheduled':state='Ended' if now>=live.end_at else 'Live' if now>=live.start_at else 'Scheduled'
    if not roles(user)&{'Admin','Coordinator','Teacher','TA','Learner'}:reason='Your account cannot join classrooms.'
    elif 'Learner' in roles(user) and not Enrolment.objects.filter(cohort=live.cohort,user=user,status__in=['Enrolled','Completed']).exists():reason='You must be enrolled in this class cohort.'
    elif state=='Cancelled':reason='This class is cancelled.'
    elif state=='Ended':reason='This class has ended.'
    elif now<live.start_at:reason='This class has not started yet.'
    else:reason=''
    return {'status':state,'can_join':not reason,'join_reason':reason,'cohort_name':live.cohort.name}
