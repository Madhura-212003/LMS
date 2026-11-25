"""SQL QuerySet search/filter/order and signed keyset pagination (20 rows)."""
from dataclasses import dataclass,field
from functools import wraps
import inspect
from decimal import Decimal
from datetime import date,datetime
import hashlib,json
from django.core import signing
from django.db.models import Q,F
from ninja.errors import HttpError

@dataclass
class ListQuery:
    queryset:object
    row:object
    search:tuple=()
    sorts:dict=field(default_factory=lambda:{'id':'pk'})
    default:str='id'
    status:str|None=None
    filters:dict=field(default_factory=dict)
    key:str='pk'
    facets:tuple=()
    status_label:str='Status'


def value(row,name):
    if isinstance(row,dict):return row[name]
    result=row
    for part in name.split('__'):result=getattr(result,part)
    return result


def encoded(v):
    if isinstance(v,(date,datetime)):return v.isoformat()
    if isinstance(v,Decimal):return str(v)
    return v


def boundary(field,key,v,pk,descending,before):
    comparator=('gt' if descending else 'lt') if before else ('lt' if descending else 'gt')
    if field==key:return Q(**{key+'__'+comparator:pk})
    tie=Q(**{field:v,key+'__'+comparator:pk})
    if v is None:return Q(**{field+'__isnull':False})|tie if before else tie
    result=Q(**{field+'__'+comparator:v})|tie
    return result if before else result|Q(**{field+'__isnull':True})


def paginate(request,plan):
    from .permissions import roles
    query=request.GET
    text=(query.get('_search') or query.get('q') or '').strip()
    if len(text)>500:raise HttpError(400,'Search is limited to 500 characters')
    qs=plan.queryset
    if text and plan.search:
        condition=Q()
        for path in plan.search:condition|=Q(**{path+'__icontains':text})
        qs=qs.filter(condition)
    status=query.get('_status') or query.get('status','')
    if status:
        if not plan.status:raise HttpError(400,'This list has no status filter')
        qs=qs.filter(**{plan.status:status})
    for param,path in plan.filters.items():
        if query.get(param):qs=qs.filter(**{path:query[param]})
    sort=query.get('_sort') or query.get('sort') or plan.default
    if sort.lstrip('-') not in plan.sorts:raise HttpError(400,'Choose a supported list sort order')
    order_field=plan.sorts[sort.lstrip('-')];descending=sort.startswith('-')
    binding={'path':request.path,'user':request.user.pk,'scope':[request.user.profile.tenant,request.user.profile.campus,sorted(roles(request.user))],
             'query':sorted((k,v) for k,v in query.items() if k not in ('cursor','page')),'sort':sort,'v':2}
    fingerprint=hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()
    cursor=None
    if query.get('cursor'):
        try:
            cursor=signing.loads(query['cursor'],salt='lms-keyset-v2',max_age=3600)
            if cursor['binding']!=fingerprint or cursor['direction'] not in ('after','before') or not isinstance(cursor['key'],(int,str)):raise ValueError()
        except (signing.BadSignature,KeyError,ValueError,TypeError):raise HttpError(400,'The list cursor expired or its filters changed. Return to the first page.')
    before=bool(cursor and cursor['direction']=='before');selected=qs
    if cursor:
        try:selected=selected.filter(boundary(order_field,plan.key,cursor['value'],cursor['key'],descending,before))
        except (TypeError,ValueError):raise HttpError(400,'Invalid list cursor. Return to the first page.')
    reverse=descending^before
    ordering=F(order_field).desc(nulls_first=True) if before and reverse else F(order_field).asc(nulls_first=True) if before else F(order_field).desc(nulls_last=True) if reverse else F(order_field).asc(nulls_last=True)
    fields=[ordering]
    if order_field!=plan.key:fields.append(F(plan.key).desc() if reverse else F(plan.key).asc())
    rows=list(selected.order_by(*fields)[:20])
    if before:rows.reverse()
    def token(row,direction):return signing.dumps({'binding':fingerprint,'value':encoded(value(row,order_field)),'key':encoded(value(row,plan.key)),'direction':direction},salt='lms-keyset-v2',compress=True)
    previous=next_cursor=None
    if rows:
        first,last=rows[0],rows[-1]
        if qs.filter(boundary(order_field,plan.key,value(first,order_field),value(first,plan.key),descending,True)).exists():previous=token(first,'before')
        if qs.filter(boundary(order_field,plan.key,value(last,order_field),value(last,plan.key),descending,False)).exists():next_cursor=token(last,'after')
    facets={path:list(plan.queryset.order_by(path).values_list(path,flat=True).distinct()) for path in plan.facets}
    statuses=list(plan.queryset.order_by(plan.status).values_list(plan.status,flat=True).distinct()) if plan.status else []
    return {'items':[plan.row(row) for row in rows],'total':qs.count(),'next_cursor':next_cursor,'previous_cursor':previous,
            'sort_fields':list(plan.sorts),'statuses':[str(s) for s in statuses if s is not None],'status_label':plan.status_label,'facets':facets,'page_size':20}


def list_page(fn):
    original=set(inspect.signature(fn).parameters)
    @wraps(fn)
    def wrapped(request,*args,**kwargs):
        kwargs={k:v for k,v in kwargs.items() if k in original}
        if request.GET.get('list_page','').lower() in ('1','true'):
            from .list_queries import query_for
            return paginate(request,query_for(fn.__name__,request,kwargs))
        return fn(request,*args,**kwargs)
    signature=inspect.signature(fn)
    parameters=list(signature.parameters.values())
    for key,annotation,default in [('list_page',bool,False),('cursor',str,''),('q',str,''),('status',str,''),('sort',str,'')]:
        if key not in original:parameters.append(inspect.Parameter(key,inspect.Parameter.KEYWORD_ONLY,default=default,annotation=annotation))
    wrapped.__signature__=signature.replace(parameters=parameters)
    return wrapped
