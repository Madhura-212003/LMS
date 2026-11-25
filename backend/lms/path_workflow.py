"""Learning-path navigation and reference validation."""
from ninja.errors import HttpError
from .models import Course,Lesson,Quiz,ProgrammingLab
from .permissions import permits,roles
from .services import course_access

STEP_MODELS={'lesson':Lesson,'quiz':Quiz,'lab':ProgrammingLab,'course':Course}


def workflow(user):
    from .feature_api import ItemIn
    learner='Learner' in roles(user)
    return {'module_id':161,'screens':[
        {'tab':'Path builder','label':'Path Builder','role':'Teacher / Coordinator / Admin','accessible':permits(user,'path_manage')},
        {'tab':'Teacher path progress','label':'Teacher Path Progress','role':'Teacher / Coordinator','accessible':permits(user,'teaching_read')},
        {'tab':'Learner path view','label':'Learner Path View','role':'Learner','accessible':learner or permits(user,'path_manage')},
        {'tab':'Path catalogue / Search','label':'Path Catalogue / Search','role':'Learner / Teacher','accessible':learner or permits(user,'path_manage')}],
        'max_steps':next(limit.max_length for limit in ItemIn.model_fields['steps'].metadata if hasattr(limit,'max_length')),
        'can_manage':permits(user,'path_manage'),'can_start':learner,'default_status':'Draft',
        'publication_statuses':['Draft','Published'],
        'step_kinds':[{'value':kind,'label':label} for kind,label in [('lesson','Lesson'),('quiz','Quiz'),('lab','Programming lab'),('course','Course')]]}


def validate_steps(user,steps,published=False):
    if not steps:raise HttpError(400,'Add at least one path step')
    seen=set()
    for step in steps:
        if not isinstance(step,dict) or step.get('kind') not in STEP_MODELS:raise HttpError(400,'Choose a lesson, quiz, lab or course')
        reference=step.get('reference')
        if not isinstance(reference,int) or isinstance(reference,bool) or reference<=0:raise HttpError(400,'Choose a valid saved activity')
        key=(step['kind'],reference)
        if key in seen:raise HttpError(400,'A path cannot contain the same activity twice')
        seen.add(key)
        model=STEP_MODELS[step['kind']]
        target=model.objects.filter(pk=reference).first()
        if not target:raise HttpError(400,'A linked activity no longer exists')
        course=course_access(user,target.pk if model is Course else target.course_id)
        if published and (target.status!='Published' or course.status!='Published'):raise HttpError(400,'Publish every linked activity and its course before publishing this path')
        title=step.get('title',target.title)
        if not isinstance(title,str) or not title.strip() or len(title)>200:raise HttpError(400,'Step titles must contain 1–200 characters')
