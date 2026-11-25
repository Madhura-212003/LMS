import os
import secrets
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from lms.models import *


class Command(BaseCommand):
    help = 'Create local sample records. Password is supplied with LMS_DEMO_PASSWORD or generated.'

    @transaction.atomic
    def handle(self, *args, **options):
        from django.conf import settings
        from django.core.management.base import CommandError
        if settings.PRODUCTION:raise CommandError('Demo seeding is disabled in production')
        password = os.environ.get('LMS_DEMO_PASSWORD') or secrets.token_urlsafe(12)
        users = {}
        created = []
        for name, role in [('admin', 'Admin'), ('teacher', 'Teacher'), ('student', 'Learner'), ('librarian','Librarian'), ('coordinator','Coordinator'), ('translator','Translator'), ('seller','Seller')]:
            email = name + '@admiezo.demo'
            u, new = User.objects.get_or_create(username=email, defaults={'email': email, 'first_name': {'admin': 'Madhura', 'teacher': 'Dr. Asha Rao', 'student': 'Alex Morgan','librarian':'Library Manager','coordinator':'Course Coordinator','translator':'Language Reviewer','seller':'Course Seller'}[name]})
            if new:
                u.set_password(password)
                u.save()
                created.append(email)
            Profile.objects.get_or_create(user=u, defaults={'role': role})
            users[name] = u
        if Course.objects.exists():
            self.stdout.write('Existing courses preserved. No duplicate sample data added.')
        else:
            samples = [
                ('Python foundations', 'Technology', 'Build your first programs with clear, practical lessons.', ['Variables and expressions', 'Decisions and loops', 'Functions that work'], [
                    'A variable is a name that refers to a value. In Python, count = 3 assigns the integer 3 to count. Names should describe what a value represents. The print function displays a value. An expression combines values and operators to compute a result.',
                    'An if statement chooses a branch based on a condition. A for loop repeats an action for each item in a sequence. The range function can generate a sequence of integers. Indentation groups statements into a block.',
                    'A function groups reusable instructions. Define a function with def, followed by a name and parameters. A return statement sends a result back to the caller. Parameters are local names for arguments passed into the function.']),
                ('Data fluency with spreadsheets', 'Digital skills', 'Turn everyday data into useful decisions.', ['Organise your data', 'Formulas and references'], ['A spreadsheet contains cells arranged in rows and columns. Each cell has an address such as A1. Keep one record per row and use descriptive column headers.', 'A formula starts with an equals sign. SUM adds numeric values. Relative references change when a formula is copied; absolute references use dollar signs.']),
                ('Communication at work', 'Career', 'Write clearly and present your ideas with confidence.', ['Writing for your reader', 'A clear presentation'], ['Start a message with its purpose. Use short paragraphs and concrete verbs. State the action you need and when it is due.', 'A presentation has an opening, main points, and a close. Use examples to support your points and allow time for questions.'])]
            for title, subject, description, titles, bodies in samples:
                c = Course.objects.create(title=title, description=description, subject=subject, outcomes=['Apply the core concepts', 'Complete practical exercises'], modules=titles, status='Published', owner=users['teacher'])
                co = Cohort.objects.create(course=c, name='November learning cohort', teacher=users['teacher'], capacity=30, start_date=timezone.localdate(), end_date=timezone.localdate()+timedelta(days=90))
                if subject == 'Technology':
                    Enrolment.objects.create(cohort=co, user=users['student'])
                for i, (lt, body) in enumerate(zip(titles, bodies)):
                    Lesson.objects.create(course=c, title=lt, body=body, position=i+1, status='Published', author=users['teacher'])
                Credential.objects.create(course=c, title=title + ' · Completion', description='Complete all published lessons to earn this learning credential.')
                Assignment.objects.create(course=c, title='Apply what you learned', instructions='Explain one concept in your own words and include a practical example.', due_at=timezone.now()+timedelta(days=7), total_marks=100)
                q = Quiz.objects.create(course=c, title=title+' — Knowledge check', time_limit_min=10, max_attempts=3)
                Question.objects.create(quiz=q, prompt='Which approach best supports learning?', options=['Practise and review feedback', 'Skip all exercises', 'Memorise without understanding'], answer=0, explanation='Practice and feedback help you identify gaps and improve.')
        if created:
            self.stdout.write('Local demo accounts: '+', '.join(created))
            self.stdout.write('Initial password for these new accounts: '+password)
            self.stdout.write('Save this password locally. It is not stored in source code.')
