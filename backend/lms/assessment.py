import math
from ninja.errors import HttpError


def validate_question(q):
    if not q.prompt.strip() or any(not x.strip() for x in q.options):raise HttpError(400,'Question and answer options cannot be blank')
    if any(v is not None and not math.isfinite(v) for v in (q.correct_marks,q.wrong_marks,q.numeric_answer,q.tolerance)):raise HttpError(400,'Assessment scores and answers must be finite numbers')
    if q.kind not in ('Single choice','Multiple choice','Numerical'):raise HttpError(400,'Choose a supported question type')
    if q.kind!='Numerical' and len(q.options)<2:raise HttpError(400,'Choice questions need at least two options')
    if q.kind=='Single choice' and not 0<=q.answer<len(q.options):raise HttpError(400,'Correct option must refer to an answer option')
    if q.kind=='Multiple choice' and (not q.answer_set or len(set(q.answer_set))!=len(q.answer_set) or any(type(i) is not int or not 0<=i<len(q.options) for i in q.answer_set)):raise HttpError(400,'Select valid, unique correct options')
    if q.kind=='Numerical' and (q.numeric_answer is None or not math.isfinite(q.numeric_answer) or not math.isfinite(q.tolerance) or q.tolerance<0):raise HttpError(400,'Numerical questions require a finite answer and non-negative tolerance')


def validate_answer(q,value):
    if value is None or value=='':return
    if q.kind=='Multiple choice':
        if not isinstance(value,list) or len(value)>len(q.options) or any(type(x) is not int or x<0 or x>=len(q.options) for x in value) or len(set(value))!=len(value):raise HttpError(400,'Select valid unique answer options')
    elif q.kind=='Numerical':
        try:
            if type(value) not in (int,float,str) or len(str(value))>50 or not math.isfinite(float(value)):raise ValueError()
        except (TypeError,ValueError,OverflowError):raise HttpError(400,'Enter a finite numerical answer')
    elif type(value) is not int or not 0<=value<len(q.options):raise HttpError(400,'Invalid question or answer option')


def answered(value):return value is not None and value!='' and value!=[]


def correct(q,value):
    if q.kind=='Multiple choice':return isinstance(value,list) and set(value)==set(q.answer_set)
    if q.kind=='Numerical':
        try:return math.isclose(float(value),q.numeric_answer,rel_tol=0,abs_tol=q.tolerance)
        except (TypeError,ValueError,OverflowError):return False
    return value==q.answer


def maximum(quiz):return sum(q.correct_marks if q.correct_marks is not None else quiz.correct_marks for q in quiz.question_set.all())
