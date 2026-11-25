"""Recorded-lecture navigation and player/upload policy."""
from django.conf import settings
from .permissions import permits, roles


def workflow(user):
    manage=permits(user,'lecture_manage')
    learner='Learner' in roles(user)
    return {'module_id':160, 'screens':[
        {'tab':'Lecture upload / Edit / Publish','label':'Lecture Upload / Edit / Publish','role':'Teacher / TA / Coordinator / Admin','accessible':manage},
        {'tab':'Learner lecture player','label':'Learner Lecture Player','role':'Learner','accessible':learner or manage},
        {'tab':'Lecture library / Search','label':'Lecture Library / Search','role':'Teacher / Coordinator / Learner','accessible':learner or manage}],
        'can_manage':manage,'can_track_progress':learner,
        'default_status':'Draft','publication_statuses':['Draft','Published'],
        'video_accept':'video/mp4,video/webm','captions_accept':'.vtt',
        'progress_save_seconds':settings.LECTURE_PROGRESS_SAVE_SECONDS}
