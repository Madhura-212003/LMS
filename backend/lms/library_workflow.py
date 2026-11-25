"""Digital-library navigation and policy metadata."""
from django.conf import settings
from .permissions import permits

LIBRARY_SCREENS = (
    ('Library catalogue', 'Library Catalogue', 'Learner', None),
    ('Resource management', 'Resource Management', 'Librarian', 'library_manage'),
    ('My library', 'My Library', 'Learner', None),
    ('Resource reader', 'Resource Reader', 'Learner', None),
    ('Librarian dashboard', 'Librarian Dashboard', 'Librarian', 'library_manage'),
)


def workflow(user):
    return {'module_id':158, 'screens': [
        {'tab':tab,'label':label,'role':role,'accessible':cap is None or permits(user,cap)}
        for tab,label,role,cap in LIBRARY_SCREENS],
        'loan_days':settings.LIBRARY_LOAN_DAYS,
        'metric_labels':{'resources':'Library resources','published':'Published resources',
                         'saved':'Saved entries','borrowed':'Active loans','overdue':'Overdue loans'}}
