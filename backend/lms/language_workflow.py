"""Navigation and saved language choices for multilingual learning."""
from .models import Translation,GlossaryTerm,Preference
from .permissions import roles,permits
from .services import courses,scope
from .personalisation_workflow import preference_values


def workflow(user):
    learner='Learner' in roles(user)
    languages=set(Translation.objects.filter(lesson__course__in=courses(user)).values_list('language',flat=True))
    languages.update(GlossaryTerm.objects.filter(**scope(user)).values_list('language',flat=True))
    languages.add(preference_values(user)['language'])
    return {'module_id':164,'screens':[
        {'tab':'Language preference','label':'Language Preference','role':'Learner','accessible':learner},
        {'tab':'Translated content view','label':'Translated Content View','role':'Learner','accessible':learner},
        {'tab':'Translation queue / Editor','label':'Translation Queue / Editor','role':'Translator / Reviewer / Coordinator','accessible':permits(user,'translate') or permits(user,'translation_review')},
        {'tab':'Glossary and coverage','label':'Glossary and Coverage','role':'Coordinator / Admin','accessible':permits(user,'glossary_manage')}],
        'can_read':learner,'can_translate':permits(user,'translate'),'can_review':permits(user,'translation_review'),'can_manage_glossary':permits(user,'glossary_manage'),
        'languages':sorted(language for language in languages if language.strip())}
