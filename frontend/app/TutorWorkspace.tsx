'use client';

import {useEffect,useState} from 'react';
import {Alert,Button,Chip,TextField} from '@mui/material';
import {Api,FeatureProps,Row,useData,useList,useAction,Header,Feedback,Empty} from './feature-shared';

export default function TutorWorkspace(p:FeatureProps){
 const policy=useData<Row>('/tutor-workflow',p.api),chat=p.tab==='AI tutor chat',review=p.tab==='Teacher tutor review';
 const allowed=chat?policy.data?.can_chat:review?policy.data?.can_review:policy.data?.can_manage_policy;
 const courses=useList(!review&&allowed?'/courses':'',p.api);
 const [course,setCourse]=useState<Row|null>(null),[version,setVersion]=useState(0);
 const refresh=()=>{courses.reload();setVersion(v=>v+1);};
 useEffect(()=>{const focus=()=>{courses.reload();setVersion(v=>v+1);};window.addEventListener('focus',focus);return()=>window.removeEventListener('focus',focus);},[courses.reload]);
 return <><Header module={163} title={policy.data?.screens?.find((s:Row)=>s.tab===p.tab)?.label||p.tab} description={chat?'Ask about published course lessons and flag an answer for staff guidance.':review?'Review learner-submitted answer excerpts from courses you can access.':'Manage course topic phrases, response tone and escalation guidance.'}><Button onClick={refresh}>Refresh tutor</Button></Header>
  <Feedback error={policy.error||courses.error} loading={policy.loading||(!review&&courses.loading)}/>
  {policy.data&&!allowed&&<Alert severity="info">This destination requires the role shown in the workflow navigation.</Alert>}
  {allowed&&review&&<TutorFlags api={p.api} version={version} review/>}
  {allowed&&!review&&<><section className="panel"><h2>Course scope</h2>{courses.controls}<label className="field-label" htmlFor="tutor-course">Course</label><select id="tutor-course" className="full-select" value={course?.id||''} onChange={e=>setCourse(courses.data?.find(c=>String(c.id)===e.target.value)||null)}><option value="">Choose a course</option>{course&&!courses.data?.some(c=>c.id===course.id)&&<option value={course.id}>{course.title}</option>}{courses.data?.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></section>
   {course?(chat?<TutorChat key={course.id} course={course} api={p.api} onFlag={()=>setVersion(v=>v+1)}/>:<TutorPolicy key={course.id} course={course} api={p.api} version={version}/>):<Empty>Choose an accessible course to continue.</Empty>}
   {chat&&<><h2>My flagged answers and staff guidance</h2><TutorFlags api={p.api} version={version}/></>}
  </>}
 </>;
}

function TutorChat({course,api,onFlag}:{course:Row;api:Api;onFlag:()=>void}){
 const [question,setQuestion]=useState(''),[answer,setAnswer]=useState<Row|null>(null),[reason,setReason]=useState(''),[flagged,setFlagged]=useState(false);
 const action=useAction(()=>{});
 return <section className="panel settings-panel"><h2 data-no-translate>{course.title}</h2><p className="muted">Each question is independent and uses published course lessons. Unflagged questions and answers are not saved as chat history.</p><form onSubmit={e=>{e.preventDefault();void action.act(async()=>{setAnswer(null);setFlagged(false);setReason('');const response=await api<Row>('/features/tutor/chat',{course_id:course.id,question});setAnswer({...response,question});},'Tutor response received.');}}><TextField required fullWidth multiline minRows={4} label="Ask about this course" value={question} disabled={action.busy} onChange={e=>setQuestion(e.target.value)} slotProps={{htmlInput:{maxLength:2000}}}/><Button type="submit" variant="contained" disabled={action.busy||!question.trim()}>{action.busy?'Working…':'Ask tutor'}</Button></form><Feedback error={action.error} notice={action.notice} loading={action.busy}/>
  {answer&&<div className="ai-result"><Chip label={answer.disclosure} size="small"/><h3 data-no-translate>{answer.question}</h3><p className="reader-body" data-no-translate>{answer.text}</p><TextField fullWidth multiline margin="normal" label="Reason for staff review" value={reason} disabled={flagged||action.busy} onChange={e=>setReason(e.target.value)} slotProps={{htmlInput:{maxLength:2000}}}/><p className="muted">Flagging saves your answer excerpt (up to 10,000 characters) and reason for course staff. You can read their guidance below.</p><Button disabled={action.busy||flagged||!reason.trim()} onClick={()=>void action.act(async()=>{await api('/features/tutor/flags',{course_id:course.id,excerpt:answer.text.slice(0,10000),reason});setFlagged(true);onFlag();},'Answer flagged for staff review.')}>{flagged?'Flag submitted':'Flag answer for review'}</Button></div>}
 </section>;
}

function TutorPolicy({course,api,version}:{course:Row;api:Api;version:number}){
 const saved=useData<Row>('/features/tutor/policies/'+course.id,api),[form,setForm]=useState<Row|null>(null),[dirty,setDirty]=useState(false);
 const action=useAction(()=>{});
 useEffect(()=>saved.reload(),[version,saved.reload]);
 useEffect(()=>{if(saved.data&&!dirty)setForm({...saved.data,allowed_text:saved.data.allowed_topics.join(', '),blocked_text:saved.data.blocked_topics.join(', ')});},[saved.data,dirty]);
 const change=(key:string,value:string)=>{setDirty(true);setForm(f=>({...f,[key]:value}));};
 return <section className="panel settings-panel"><h2 data-no-translate>{course.title}</h2><Feedback error={saved.error||action.error} notice={action.notice} loading={saved.loading}/>{form&&<form onSubmit={e=>{e.preventDefault();void action.act(async()=>{const result=await api<Row>('/features/tutor/policies',{course_id:course.id,allowed_topics:form.allowed_text.split(',').map((x:string)=>x.trim()).filter(Boolean),blocked_topics:form.blocked_text.split(',').map((x:string)=>x.trim()).filter(Boolean),tone:form.tone,escalation:form.escalation});saved.setData({...result,saved:true});setDirty(false);},'Course tutor policy saved. It applies to the next question.');}}><p className="muted">{saved.data?.saved?'Editing saved course policy.':'No saved policy yet. Defaults below come from the server.'} Topic rules match phrases, ignoring letter case. A blank allowed list permits all course topics; blocked phrases take priority.</p><TextField fullWidth margin="normal" label="Allowed topic phrases (comma separated)" disabled={action.busy} value={form.allowed_text} onChange={e=>change('allowed_text',e.target.value)}/><TextField fullWidth margin="normal" label="Blocked topic phrases (comma separated)" disabled={action.busy} value={form.blocked_text} onChange={e=>change('blocked_text',e.target.value)}/><TextField required fullWidth margin="normal" label="Response tone" disabled={action.busy} value={form.tone} onChange={e=>change('tone',e.target.value)} slotProps={{htmlInput:{maxLength:100}}}/><TextField required fullWidth margin="normal" label="Escalation guidance" disabled={action.busy} value={form.escalation} onChange={e=>change('escalation',e.target.value)} slotProps={{htmlInput:{maxLength:200}}}/><Button variant="contained" type="submit" disabled={action.busy||!dirty||!form.tone.trim()||!form.escalation.trim()}>Save course policy</Button>{dirty&&<Button disabled={action.busy} onClick={()=>setDirty(false)}>Discard unsaved changes</Button>}</form>}</section>;
}

function TutorFlags({api,version,review=false}:{api:Api;version:number;review?:boolean}){
 const flags=useList('/features/tutor/flags',api),[decisions,setDecisions]=useState<Record<number,string>>({}),action=useAction(flags.reload);
 useEffect(()=>flags.reload(),[version,flags.reload]);
 return <>{flags.controls}<Feedback error={flags.error||action.error} notice={action.notice} loading={flags.loading}/>{flags.data?.map(flag=><section className="panel" key={flag.id}><div className="row"><h2 data-no-translate>{flag.course_title}</h2><Chip label={flag.status}/></div>{review&&<p className="muted">Flagged by {flag.learner}</p>}<blockquote className="reader-body" data-no-translate>{flag.excerpt}</blockquote><p data-no-translate><b>Reason:</b> {flag.reason}</p>{flag.decision&&<Alert severity="info"><span data-no-translate>{flag.decision}</span></Alert>}{review&&<><TextField fullWidth multiline minRows={3} label="Review decision and learner guidance" value={decisions[flag.id]??flag.decision} onChange={e=>setDecisions(d=>({...d,[flag.id]:e.target.value}))} slotProps={{htmlInput:{maxLength:4000}}}/><Button disabled={action.busy||!(decisions[flag.id]??'').trim()} onClick={()=>void action.act(async()=>{await api('/features/tutor/flags/'+flag.id+'/review',{decision:decisions[flag.id]});setDecisions(d=>{const copy={...d};delete copy[flag.id];return copy;});},'Guidance saved and available to the learner.')}>Save review guidance</Button></>}</section>)}{!flags.data?.length&&!flags.loading&&<Empty>No flagged answers match this view.</Empty>}</>;
}
