from datetime import timedelta
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from lms.models import *


class Command(BaseCommand):
    help='Add original sample learning material for Section F without replacing existing records.'

    @transaction.atomic
    def handle(self,*args,**kwargs):
        from django.conf import settings
        from django.core.management.base import CommandError
        if settings.PRODUCTION:raise CommandError('Demo seeding is disabled in production')
        teacher=User.objects.filter(profile__role='Teacher').first()
        course=Course.objects.filter(owner=teacher,status='Published').first()
        if not course:raise ValueError('Run seed_demo first')
        cohort=Cohort.objects.filter(course=course).first()
        LibraryResource.objects.get_or_create(course=course,title='A practical guide to active learning',defaults={'subject':'Study skills','body':'Active learning means using knowledge rather than only rereading it. After a lesson, close your notes and explain the main idea. Try a short exercise. Compare your answer with feedback. Space your next review over several days.','description':'A short study guide with a practical review routine.','resource_type':'Article'})
        LiveClass.objects.get_or_create(course=course,title='Weekly questions and practice',defaults={'cohort':cohort,'teacher':teacher,'description':'Bring a question from this week’s lessons.','start_at':timezone.now()-timedelta(minutes=5),'end_at':timezone.now()+timedelta(hours=2),'meeting_url':'https://meet.jit.si/admiezo-'+str(course.id)+'-weekly-'+timezone.localdate().isoformat(),'status':'Scheduled'})
        path,new=LearningPath.objects.get_or_create(course=course,title='Your first Python learning path',defaults={'description':'Read the introductory lessons, then check your knowledge.'})
        if new:
            for i,l in enumerate(Lesson.objects.filter(course=course,status='Published').order_by('position')):PathStep.objects.create(path=path,kind='lesson',reference=l.id,title=l.title,position=i+1)
            quiz=Quiz.objects.filter(course=course,exam_type='Practice').first()
            if quiz:PathStep.objects.create(path=path,kind='quiz',reference=quiz.id,title=quiz.title,position=100)
        Activity.objects.get_or_create(course=course,title='Explain a concept to a beginner',defaults={'description':'Choose one concept from a lesson. Explain it in three sentences, then reply constructively to a classmate.','due_at':timezone.now()+timedelta(days=30),'groups':['Whole class']})
        CodingProblem.objects.get_or_create(course=course,title='Add two numbers',defaults={'description':'Read two integers, one per line. Print their sum.','topic':'Input and arithmetic','starter':'a = int(input())\nb = int(input())\nprint(a + b)','tests':[{'input':'2\n3','output':'5'},{'input':'-4\n7','output':'3'},{'input':'0\n0','output':'0'}]})
        CodingProblem.objects.get_or_create(course=course,title='Sum a sequence',defaults={'description':'Read a positive integer n. Print the sum of integers from 1 through n.','topic':'Loops','starter':'n = int(input())\ntotal = 0\nfor i in range(1, n + 1):\n    total += i\nprint(total)','tests':[{'input':'5','output':'15'},{'input':'1','output':'1'},{'input':'10','output':'55'}]})
        ProgrammingLab.objects.get_or_create(course=course,title='Investigate a loop',defaults={'subject':'Programming fundamentals','description':'Predict, run and explain a counting loop.','starter':'total = 0\nfor i in range(1, 6):\n    total += i\nprint(total)','steps':['Predict the output before running the code.','Run the loop and record the output.','Change the range to include 10 and explain the new output.']})
        DigitalSkill.objects.get_or_create(course=course,title='Spreadsheet essentials',defaults={'description':'Build a reliable small spreadsheet.','steps':['Create a sheet with clear column headers and one record per row.','Enter five numeric values and calculate their SUM.','Copy a formula and compare relative and absolute references.','Create a chart and write a one-sentence interpretation.']})
        DigitalSkill.objects.get_or_create(course=course,title='Safer use of AI tools',defaults={'description':'Practise responsible checking and privacy habits.','steps':['Remove personal and confidential data before creating a prompt.','Ask a focused question with the context needed to answer it.','Check every factual claim against a reliable source.','Record where AI helped and what you verified yourself.']})
        prompts=[(172,'A clear introduction','Speaking','Introduce yourself to a new team in 60 seconds. Include your role, one skill and one learning goal.'),(172,'Write a helpful email','Writing','Write an email requesting feedback on your draft. State the purpose, specific feedback needed and a reasonable deadline.'),(176,'Mains answer writing','Mains','Discuss how transparency can strengthen public trust. Structure a 150-word answer with an introduction, arguments and conclusion.'),(177,'Behavioural interview practice','Interview','Describe a time you solved a difficult problem. Use situation, task, action and result.'),(177,'Group discussion preparation','GD','Prepare an opening statement and two balanced arguments on responsible use of AI in education.'),(178,'Build your resume summary','Resume','Write a professional summary describing your skills, evidence and the role you seek.'),(178,'Portfolio project reflection','Portfolio','Describe one project: problem, your contribution, outcome and a link or evidence of the work.')]
        for mod,title,typ,desc in prompts:PracticePrompt.objects.get_or_create(course=course,title=title,module=mod,defaults={'practice_type':typ,'description':desc,'rubric':'Clarity (25), structure (25), evidence (25), relevance (25).'})
        packs=[(173,'Quantitative aptitude practice','Aptitude','Competitive',1,0,'What is 20% of 150?',['20','30','50'],1,'20/100 × 150 = 30.'),(174,'Physics foundations practice','Physics','NEET',4,-1,'A body moves 20 metres in 4 seconds at constant speed. Its speed is:',['5 m/s','16 m/s','80 m/s'],0,'Speed = distance / time = 20 / 4 = 5 m/s.'),(174,'Biology foundations practice','Botany','NEET',4,-1,'Which organelle is primarily responsible for photosynthesis?',['Mitochondrion','Chloroplast','Nucleus'],1,'Chloroplasts contain the photosynthetic machinery.'),(175,'Algebra foundations practice','Maths','JEE',4,-1,'If 2x + 3 = 11, what is x?',['3','4','7'],1,'Subtract 3 and divide by 2: x = 4.'),(176,'Prelims reasoning practice','GS','UPSC',2,-0.66,'Which practice supports transparent public decision-making?',['Publishing reasons and evidence','Withholding every decision record','Avoiding all consultation'],0,'Public reasons and evidence support scrutiny and accountability.'),(177,'Placement aptitude check','Aptitude','Placement',1,0,'A team completes 12 equal tasks in 3 hours. Its average rate is:',['3 tasks/hour','4 tasks/hour','9 tasks/hour'],1,'12 divided by 3 is 4 tasks per hour.')]
        for mod,title,subject,typ,correct,wrong,prompt,options,answer,explanation in packs:
            if ExamPack.objects.filter(course=course,module=mod,title=title).exists():continue
            quiz=Quiz.objects.create(course=course,title=title,time_limit_min=10,max_attempts=5,exam_type=typ,correct_marks=correct,wrong_marks=wrong)
            Question.objects.create(quiz=quiz,prompt=prompt,options=options,answer=answer,explanation=explanation)
            ExamPack.objects.create(course=course,title=title,module=mod,subject=subject,level='Main' if mod==175 else 'Practice',quiz=quiz,description='Original sample practice question. This is not an official previous-year paper or a syllabus-complete exam pack.')
        for c in Course.objects.filter(status='Published'):
            MarketplaceListing.objects.get_or_create(course=c,defaults={'seller':teacher,'price':0 if c.id==course.id else 499})
        GlossaryTerm.objects.get_or_create(term='Variable',language='English',defaults={'definition':'A name that refers to a value in a program.'})
        TutorPolicy.objects.get_or_create(course=course)
        self.stdout.write('Original sample material added. Existing content and learner progress preserved. Upload your own video and licensed previous papers through their management screens.')
