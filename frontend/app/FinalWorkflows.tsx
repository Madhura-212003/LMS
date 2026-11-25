'use client';
import {useState} from 'react';
import {Alert,Button,Chip,Dialog,DialogActions,DialogContent,DialogTitle,TextField} from '@mui/material';
import {Api,Row,useData,useList,useAction,Feedback,WorkTable,Empty} from './feature-shared';

export function DashboardSummary({api,staff,navigate}:{api:Api;staff:boolean;navigate:(module:number,tab?:string)=>void}){
 const s=useData<Row>('/final/dashboard',api);
 return <section className="panel"><h2>{staff?'Teaching & coordination':'Your learning updates'}</h2><Feedback error={s.error} loading={s.loading}/>{staff&&s.data&&<p>{s.data.insights.cohorts} cohorts · {s.data.insights.learners} learners · {s.data.insights.pending_marking} awaiting marking</p>}<h3>Upcoming classes</h3>{s.data?.upcoming.map((x:Row)=><p key={x.id}><b>{x.title}</b> · {new Date(x.start_at).toLocaleString()} · {x.teacher__first_name} <Button onClick={()=>navigate(159)}>Open schedule</Button></p>)}{s.data&&!s.data.upcoming.length&&<p>No upcoming classes.</p>}<h3>Outstanding assignments</h3>{s.data?.due.map((x:Row)=><p key={x.id}>{x.title} · {new Date(x.due_at).toLocaleString()} <Button onClick={()=>navigate(165)}>View assignment</Button></p>)}{s.data&&!s.data.due.length&&<p>No upcoming assignment deadlines.</p>}<h3>Unread notifications</h3>{s.data?.notifications.map((x:Row)=><p key={x.id}>{x.announcement__title} <Button onClick={()=>navigate(156,'Notifications')}>Read notification</Button></p>)}{s.data&&!s.data.notifications.length&&<p>No unread notifications.</p>}</section>;
}

export function LifecycleEditor({kind,item,api,reload}:{kind:'assignments'|'quizzes';item:Row;api:Api;reload:()=>void}){
 const [open,setOpen]=useState(false),[form,setForm]=useState<Row>({}),a=useAction(reload);
 const field=(key:string,label:string,type='text')=><TextField fullWidth required margin="normal" type={type} multiline={key==='instructions'} minRows={key==='instructions'?4:undefined} label={label} value={form[key]??''} onChange={e=>setForm({...form,[key]:e.target.value})} slotProps={type==='datetime-local'?{inputLabel:{shrink:true}}:type==='number'?{htmlInput:{step:'any'}}:undefined}/>;
 return <><Button onClick={()=>{const d=item.due_at?new Date(item.due_at):null;setForm({...item,due_at:d?new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16):undefined});setOpen(true);}}>Manage {kind==='quizzes'?'quiz':'assignment'}</Button><Dialog open={open} onClose={()=>!a.busy&&setOpen(false)} fullWidth maxWidth="sm"><form onSubmit={e=>{e.preventDefault();void a.act(async()=>{const body={...form};for(const k of ['total_marks','time_limit_min','max_attempts','correct_marks','wrong_marks'])if(k in body)body[k]=Number(body[k]);if(body.due_at)body.due_at=new Date(body.due_at).toISOString();await api('/final/'+kind+'/'+item.id+'/edit',body);setOpen(false);},'Assessment updated');}}><DialogTitle>Manage assessment</DialogTitle><DialogContent><Feedback error={a.error} notice={a.notice}/><Alert severity="info">Existing learner work is preserved. Used assessments keep their original marking scale.</Alert>{field('title','Title')}{kind==='assignments'?<>{field('instructions','Instructions')}{field('due_at','Due date','datetime-local')}{field('total_marks','Total marks','number')}</>:<>{field('time_limit_min','Time limit in minutes','number')}{field('max_attempts','Maximum attempts','number')}{field('correct_marks','Correct marks','number')}{field('wrong_marks','Incorrect marks','number')}</>}<label className="field-label">Assessment status</label><select aria-label="Assessment status" className="full-select" value={form.status||'Published'} onChange={e=>setForm({...form,status:e.target.value})}>{['Draft','Published','Archived'].map(x=><option key={x}>{x}</option>)}</select></DialogContent><DialogActions><Button disabled={a.busy} onClick={()=>setOpen(false)}>Cancel</Button><Button disabled={a.busy} type="submit">Save assessment</Button></DialogActions></form></Dialog><Feedback notice={a.notice}/></>;
}

export function TopicInsights({api}:{api:Api}){
 const s=useList('/final/class-topics',api);
 return <section className="panel"><h2>Topic strengths & gaps</h2><Feedback error={s.error} loading={s.loading}/>{s.controls}<WorkTable rows={s.data||[]} fields={[{key:'course',label:'Course'},{key:'topic',label:'Topic'},{key:'responses',label:'Responses'},{key:'accuracy',label:'Correct %'},{key:'status',label:'Evidence'}]}/></section>;
}

export function LabReview({item,api,reload,staff}:{item:Row;api:Api;reload:()=>void;staff:boolean}){
 const [score,setScore]=useState(String(item.score??'')),[feedback,setFeedback]=useState(item.feedback||''),a=useAction(reload);
 return <><p>Inputs: <code>{item.inputs||'None'}</code></p>{item.score!==null&&<Alert severity="success">{item.score}/100 · {item.feedback}</Alert>}{staff&&item.status==='Completed'&&<form onSubmit={e=>{e.preventDefault();void a.act(()=>api('/final/labs/'+item.id+'/review',{score:Number(score),feedback}),'Lab feedback saved');}}><TextField required margin="normal" type="number" label="Lab score (0–100)" value={score} onChange={e=>setScore(e.target.value)} slotProps={{htmlInput:{min:0,max:100,step:'any'}}}/><TextField required fullWidth multiline minRows={3} label="Lab feedback" value={feedback} onChange={e=>setFeedback(e.target.value)}/><Button disabled={a.busy} type="submit">Save lab feedback</Button></form>}<Feedback error={a.error} notice={a.notice}/></>;
}

export function AttemptReview({id,api}:{id:number;api:Api}){
 const [open,setOpen]=useState(false),s=useData<Row>(open?'/final/attempts/'+id:'',api);
 return <><Button onClick={()=>setOpen(true)}>Review answers & solutions</Button><Dialog open={open} onClose={()=>setOpen(false)} fullWidth maxWidth="md"><DialogTitle>Submitted answers & solutions</DialogTitle><DialogContent><Feedback error={s.error} loading={s.loading}/>{s.data&&<><p>{s.data.quiz} · Score {s.data.score}</p>{s.data.questions.map((q:Row)=><section className="panel" key={q.id}><h3>{q.prompt}</h3><p>Your saved answer: {Array.isArray(s.data!.answers[q.id])?s.data!.answers[q.id].map((i:number)=>q.options[i]).join(', '):q.kind==='Numerical'?s.data!.answers[q.id]??'Unanswered':q.options[s.data!.answers[q.id]]??'Unanswered'}</p><p>Correct: {q.kind==='Numerical'?q.numeric_answer+' ± '+q.tolerance:q.kind==='Multiple choice'?q.answer_set.map((i:number)=>q.options[i]).join(', '):q.options[q.answer]}</p><p>{q.explanation}</p></section>)}</>}</DialogContent><DialogActions><Button onClick={()=>setOpen(false)}>Close review</Button></DialogActions></Dialog></>;
}

export function LessonMedia({id,api}:{id:number;api:Api}){
 const s=useData<Row>('/final/files/'+id+'/metadata',api),url='/api/lms/features/files/'+id;
 return <section className="lesson-media"><Feedback error={s.error}/>{s.data&&<><h3>{s.data.name}</h3>{s.data.mime.startsWith('video/')?<video controls preload="metadata" src={url} style={{width:'100%'}}/>:s.data.mime.startsWith('audio/')?<audio controls preload="metadata" src={url}/>:s.data.mime.startsWith('image/')?<img src={url} alt={s.data.name} style={{maxWidth:'100%'}}/>:['application/pdf','text/plain'].includes(s.data.mime)?<iframe title={s.data.name} src={url} className="document-reader"/>:<a href={url}>Download {s.data.name}</a>}</>}</section>;
}

export function CourseReviewForm({course,api,onSaved}:{course:number;api:Api;onSaved:()=>void}){
 const [rating,setRating]=useState('5'),[body,setBody]=useState(''),a=useAction(onSaved);
 return <form onSubmit={e=>{e.preventDefault();void a.act(()=>api('/final/courses/'+course+'/review',{rating:Number(rating),body}),'Course review saved');}}><h3>Your course review</h3><select aria-label="Course rating" value={rating} onChange={e=>setRating(e.target.value)}>{[5,4,3,2,1].map(x=><option key={x} value={x}>{x} / 5</option>)}</select><TextField fullWidth multiline minRows={3} margin="normal" label="Your review" value={body} onChange={e=>setBody(e.target.value)}/><Button disabled={a.busy} type="submit">Save review</Button><Feedback error={a.error} notice={a.notice}/></form>;
}

export function AttendanceSummary({api,staff}:{api:Api;staff:boolean}){
 const s=useList('/features/live/attendance/all',api),a=useAction(s.reload);
 return <section className="panel"><Feedback error={s.error||a.error} notice={a.notice} loading={s.loading}/>{s.controls}<WorkTable rows={s.data||[]} fields={[{key:'class_title',label:'Class'},{key:'cohort',label:'Cohort'},{key:'learner',label:'Learner'},{key:'status',label:'Attendance'},{key:'joined_at',label:'Joined'}]}/>{staff&&<><h2>Correct attendance</h2>{s.data?.filter(x=>x.status!=='Cancelled').map(x=><div className="result-row" key={x.class_id+'-'+x.user_id}><span>{x.class_title} · {x.learner}</span><select aria-label={'Attendance for '+x.learner+' in '+x.class_title} disabled={a.busy} value={['Present','Absent','Late'].includes(x.status)?x.status:''} onChange={e=>void a.act(()=>api('/final/live/'+x.class_id+'/attendance/'+x.user_id,{status:e.target.value}),'Attendance corrected and audited')}><option value="" disabled>Not joined</option>{['Present','Absent','Late'].map(s=><option key={s}>{s}</option>)}</select></div>)}</>}</section>;
}

export function LearnerSkillProgress({api}:{api:Api}){
 const s=useList('/final/skill-progress',api);
 return <section className="panel"><h2>Cohort skill progress</h2><Feedback error={s.error} loading={s.loading}/>{s.controls}<WorkTable rows={s.data||[]} fields={[{key:'skill',label:'Skill'},{key:'learner',label:'Learner'},{key:'cohort',label:'Cohort'},{key:'completed',label:'Completed steps'},{key:'total',label:'Total steps'},{key:'status',label:'Status'}]}/></section>;
}
