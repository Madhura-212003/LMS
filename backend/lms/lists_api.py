from ninja import Router
from .listing import paginate
from .list_queries import query_for

router=Router()

@router.get('/{list_name}')
def records(request,list_name:str,module:int=0,cohort_id:int=0,q:str='',status:str='',sort:str='',cursor:str=''):
    return paginate(request,query_for(list_name,request,{'module':module,'cohort_id':cohort_id}))
