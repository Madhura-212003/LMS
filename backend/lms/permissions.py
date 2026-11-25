"""SRS actor permissions; an app role and a course assignment are separate grants."""
ROLES=('Admin','Coordinator','Teacher','Reviewer','Author','TA','Librarian','Translator','Seller','Learner')
CAPABILITIES={
 'course_manage':{'Admin','Coordinator','Teacher','Seller'},
 'roster_manage':{'Admin','Coordinator','Teacher'},
 'content_write':{'Admin','Teacher','Author'},
 'content_review':{'Admin','Teacher','Reviewer'},
 'classroom_manage':{'Admin','Teacher','Coordinator','TA'},
 'lecture_manage':{'Admin','Teacher','Coordinator','TA'},
 'path_manage':{'Admin','Teacher','Coordinator'},
 'tutor_review':{'Admin','Teacher','Coordinator'},
 'tutor_policy':{'Admin','Coordinator'},
 'assessment_write':{'Admin','Teacher'},
 'mark':{'Admin','Teacher','TA'},
 'teaching_read':{'Admin','Teacher','Coordinator','TA'},
 'translate':{'Admin','Teacher','Translator','Coordinator'},
 'translation_review':{'Admin','Teacher','Reviewer','Coordinator'},
 'glossary_manage':{'Admin','Coordinator'},
 'library_manage':{'Admin','Librarian'},
 'staff_assign':{'Admin','Coordinator'},
}


def roles(user):
    assigned=set(user.profile.roles or [user.profile.role]) & set(ROLES)
    # SRS uses separate learner and staff logins. Reject an ambiguous actor context.
    if 'Learner' in assigned and len(assigned)>1:return set()
    return assigned


def permits(user,capability):
    return bool(roles(user)&CAPABILITIES[capability])


def require(user,capability):
    from ninja.errors import HttpError
    if not permits(user,capability):raise HttpError(403,'Your assigned role cannot perform this action')


def permissions(user):return sorted(k for k in CAPABILITIES if permits(user,k))
