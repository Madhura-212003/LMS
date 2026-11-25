"""Server-side Piston execution adapter; production never falls back to the subset interpreter."""
import json
import os
import urllib.request
import urllib.error
from django.conf import settings
from ninja.errors import HttpError
from .teaching_runner import run as teaching_run,RunnerError

LANGUAGES={'Python':'python','Python subset':'python','JavaScript':'javascript','Java':'java','C++':'c++'}


def execute(code,inputs='',language='Python'):
    base=os.environ.get('EXECUTION_SERVICE_URL','').rstrip('/')
    if not base:
        if settings.PRODUCTION:raise HttpError(503,'The execution service is unavailable. Contact IT.')
        if language not in ('Python','Python subset'):raise HttpError(503,'Configure the execution service to use '+language)
        return teaching_run(code,inputs)
    if language not in LANGUAGES:raise HttpError(400,'Choose a supported language')
    names={'Python':'main.py','Python subset':'main.py','JavaScript':'main.js','Java':'Main.java','C++':'main.cpp'}
    payload={'language':LANGUAGES[language],'version':'*','files':[{'name':names[language],'content':code}],'stdin':inputs,'args':[],'compile_timeout':10000,'run_timeout':3000,'compile_memory_limit':268435456,'run_memory_limit':134217728}
    req=urllib.request.Request(base+'/api/v2/execute',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ.get('EXECUTION_SERVICE_TOKEN','')})
    try:
        with urllib.request.urlopen(req,timeout=20) as response:result=json.loads(response.read(1024*1024))
    except (urllib.error.URLError,TimeoutError,ValueError):raise HttpError(503,'The isolated execution service did not respond. Your work is preserved; retry.')
    compile_result=result.get('compile',{})
    if compile_result.get('code',0)!=0:raise RunnerError(str(compile_result.get('stderr','Compilation failed'))[:20000])
    execution=result.get('run',{})
    if execution.get('code')!=0 or execution.get('signal'):raise RunnerError(str(execution.get('stderr') or execution.get('signal') or 'Program failed or exceeded resource limits')[:20000])
    output=execution.get('stdout','')
    if not isinstance(output,str) or len(output)>20000:raise RunnerError('Program output exceeded 20,000 characters')
    return output
