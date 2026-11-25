"""Tutor navigation and shared authorization for flagged-answer lists."""
from .permissions import roles,permits,require
from .models import TutorPolicy,TutorFlag
from .services import courses


def workflow(user):
    learner='Learner' in roles(user)
    review=permits(user,'tutor_review');policy=permits(user,'tutor_policy')
    return {'module_id':163,'screens':[
        {'tab':'AI tutor chat','label':'AI Tutor Chat','role':'Learner','accessible':learner},
        {'tab':'Teacher tutor review','label':'Teacher Tutor Review','role':'Teacher / Coordinator','accessible':review},
        {'tab':'Tutor policy / Settings','label':'Tutor Policy / Settings','role':'Coordinator / Admin','accessible':policy}],
        'can_chat':learner,'can_review':review,'can_manage_policy':policy,
        'policy_defaults':{key:TutorPolicy._meta.get_field(key).get_default() for key in ('allowed_topics','blocked_topics','tone','escalation')}}


def flags_for(user):
    qs=TutorFlag.objects.filter(course__in=courses(user)).select_related('course','user')
    if 'Learner' in roles(user):return qs.filter(user=user)
    require(user,'tutor_review')
    return qs
