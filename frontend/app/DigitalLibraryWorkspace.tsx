'use client';

import {useEffect} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {Button,Chip} from '@mui/material';
import {FeatureProps,Row,useData,useList,useAction,useCatalogue,Feedback,Empty,Header,ItemEditor,ItemMeta,PublishActions,fileURL,ServerTable} from './feature-shared';

const destination=(tab:string)=>'/lms/158/'+encodeURIComponent(tab);

export default function DigitalLibraryWorkspace(p:FeatureProps){
 const router=useRouter(),pathname=usePathname();
 const readerPage=p.tab==='Resource reader',minePage=p.tab==='My library',management=p.tab==='Resource management',dashboard=p.tab==='Librarian dashboard';
 const rawId=pathname.split('/').filter(Boolean)[3]||'';
 const resourceId=readerPage&&/^\d+$/.test(rawId)?Number(rawId):0;
 const canManage=!!p.permissions?.includes('library_manage');
 const workflow=useData<Row>('/library-workflow',p.api);
 const catalogue=useCatalogue('library',p.api);
 const mine=useList(minePage?'/features/library/mine':'',p.api);
 const detail=useData<Row>(resourceId?'/features/library/resources/'+resourceId:'',p.api);
 const stats=useData<Row>(dashboard?'/features/library/insights?summary=1':'',p.api);
 const resource=detail.data?.id===resourceId?detail.data:null;
 const refresh=()=>{catalogue.reload();mine.reload();detail.reload();stats.reload();};
 const action=useAction(refresh);
 useEffect(()=>{const reload=()=>{catalogue.reload();mine.reload();detail.reload();stats.reload();};window.addEventListener('focus',reload);return()=>window.removeEventListener('focus',reload);},[catalogue.reload,mine.reload,detail.reload,stats.reload]);
 const open=(id:number)=>router.push(destination('Resource reader')+'/'+id);
 const loan=(item:Row,status:string)=>void action.act(()=>p.api('/features/library/'+item.id+'/loan',{action:status}),status==='Saved'?'Resource saved to My Library.':status==='Borrowed'?'Loan recorded. Its due date is shown on the resource.':'Resource returned. My Library and loan counts have been updated.');
 const descriptions:Record<string,string>={
  'Library catalogue':'Discover published learning resources and open them in Resource Reader.',
  'Resource management':'Create and edit course resources, attach documents and manage publication.',
  'My library':'Your saved resources and active loans, including their current due dates.',
  'Resource reader':'Choose a resource to read its text or document, save it, borrow it or return an active loan.',
  'Librarian dashboard':'Institution library inventory, saved resources, active loans and overdue records.'};
 const loanBadge=(item:Row)=>item.loan&&item.loan.status!=='Returned'?<Chip size="small" label={item.loan.status+(item.loan.due_at?' · Due '+new Date(item.loan.due_at).toLocaleDateString():'')}/>:null;
 return <><Header module={158} title={workflow.data?.screens?.find((screen:Row)=>screen.tab===p.tab)?.label||p.tab} description={descriptions[p.tab]}>
  <div className="actions"><Button onClick={refresh}>Refresh library</Button>{management&&canManage&&<ItemEditor kind="library" api={p.api} onSaved={refresh} button="Add resource"/>}</div>
 </Header>
 <Feedback error={workflow.error||catalogue.error||mine.error||detail.error||stats.error||action.error} notice={action.notice} loading={workflow.loading||(dashboard?stats.loading:resourceId?detail.loading:minePage?mine.loading:catalogue.loading)}/>
 {dashboard?<><div className="library-metrics">{Object.entries(workflow.data?.metric_labels||{}).map(([key,label])=><section className="panel" key={key}><strong>{stats.data?stats.data[key]:'—'}</strong><p>{String(label)}</p></section>)}</div>
  <h2>Resource usage</h2><ServerTable url="/lists/library_usage" api={p.api} fields={[{key:'title',label:'Resource'},{key:'usage',label:'Recorded users'}]}/>
 </>:readerPage&&resourceId?<>
  <div className="actions"><Button onClick={()=>router.push(destination('Library catalogue'))}>Back to Library Catalogue</Button><Button onClick={()=>router.push(destination('My library'))}>My Library</Button></div>
  {resource&&<article className="panel"><span className="eyebrow">{resource.course_title}</span><h2 data-no-translate>{resource.title}</h2><p>{resource.subject} · {resource.language} · {resource.resource_type}</p>{loanBadge(resource)}
   <div className="reader-body" data-no-translate>{resource.body}</div>
   {resource.attachment&&<><iframe className="document-reader" title={resource.title} src={fileURL(resource.attachment)}/><p><a href={fileURL(resource.attachment)} target="_blank" rel="noreferrer">Open resource document</a></p></>}
   <div className="actions"><Button disabled={action.busy||['Saved','Borrowed'].includes(resource.loan?.status)} onClick={()=>loan(resource,'Saved')}>Save to My Library</Button><Button variant="contained" disabled={action.busy||resource.loan?.status==='Borrowed'} onClick={()=>loan(resource,'Borrowed')}>Borrow resource</Button>{resource.loan?.status==='Borrowed'&&<Button disabled={action.busy} onClick={()=>loan(resource,'Returned')}>Return resource</Button>}</div>
   {workflow.data&&<p className="muted">New loans use the library policy of {workflow.data.loan_days} days. Reopening or saving an active loan preserves its due date.</p>}
  </article>}
 </>:readerPage?<section className="panel reader-start"><div className="resource-symbol" aria-hidden="true">▥</div><h2>Open a resource to start reading</h2><p>Choose a published resource from Library Catalogue, or reopen a saved resource from My Library. Its text or document will open here.</p><div className="actions"><Button variant="contained" onClick={()=>router.push(destination('Library catalogue'))}>Browse Library Catalogue</Button><Button variant="outlined" onClick={()=>router.push(destination('My library'))}>Open My Library</Button></div></section>:<>
  {readerPage&&<p className="muted">Select a resource below to open its reader. You can also open resources from Library Catalogue or My Library.</p>}
  {minePage?mine.controls:catalogue.toolbar}
  <div className="course-grid">{(minePage?mine.data||[]:catalogue.items).map(item=><article className="panel resource-card" key={item.id}>
   <div className="resource-symbol" aria-hidden="true">▥</div><ItemMeta item={item}/><h2 data-no-translate>{item.title}</h2><p data-no-translate>{item.description}</p><p className="muted">{item.subject} · {item.language} · {item.resource_type}</p>{loanBadge(item)}
   <div className="actions"><Button variant="outlined" disabled={item.readable===false} onClick={()=>open(item.id)}>Open Resource Reader</Button>{minePage&&item.loan?.status==='Borrowed'&&<Button disabled={action.busy} onClick={()=>loan(item,'Returned')}>Return resource</Button>}</div>
   {management&&canManage&&<PublishActions kind="library" item={item} api={p.api} reload={refresh}/>}
  </article>)}</div>
  {!(minePage?mine.loading:catalogue.loading)&&!(minePage?mine.data||[]:catalogue.items).length&&<Empty>{minePage?'No saved resources or active loans match this view. Save or borrow a resource in Resource Reader.':'No resources match this view. Adjust the filters or ask your librarian to publish course resources.'}</Empty>}
  {!minePage&&catalogue.pagination}
 </>}
 </>;
}
