"""Learning-content navigation and the shared publication state machine."""
from .permissions import permits

CONTENT_TRANSITIONS = {
    'Draft': ['In Review'], 'Needs Changes': ['In Review'],
    'In Review': ['Approved', 'Needs Changes'], 'Approved': ['Published'],
    'Published': [],
}

CONTENT_SCREENS = (
    ('Content editor', 'Content Editor', 'Author', 'content_write'),
    ('Content review', 'Content Review', 'Reviewer', 'content_review'),
    ('Course viewer', 'Course Viewer', 'Learner', None),
    ('Content catalogue', 'Content Catalogue', 'Author', None),
)


def workflow(user):
    return {'module_id':157, 'screens': [{'tab': tab, 'label': label, 'role': role,
                         'accessible': capability is None or permits(user, capability)}
                        for tab, label, role, capability in CONTENT_SCREENS],
            'statuses': list(CONTENT_TRANSITIONS), 'transitions': CONTENT_TRANSITIONS}
