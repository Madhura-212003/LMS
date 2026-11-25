'use client';

import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {Alert,Button,Chip,TextField} from '@mui/material';
import {FeatureProps,Row,useData,useList,useAction,Header,Feedback,Empty,ServerTable} from './feature-shared';

export default function PersonalisedLearningWorkspace(p:FeatureProps){
 const router=useRouter(),whatNext=p.tab==='Learner what next',insights=p.tab==='Teacher class insights',settings=p.tab==='Personalisation settings';
 const policy=useData<Row>('/personalisation-workflow',p.api);
 const next=useData<Row>(whatNext&&policy.data?.can_recommend?'/features/personalisation/next':'',p.api);
 const preferences=useData<Row>(settings&&policy.data?.can_edit_settings?'/features/preferences':'',p.api);
 const cohorts=useList(insights&&policy.data?.can_inspect?'/cohorts':'',p.api);
 const [form,setForm]=useState<Row|null>(null),[changed,setChanged]=useState<string[]>([]),[cohortId,setCohortId]=useState(''),[reportVersion,setReportVersion]=useState(0);
 useEffect(()=>{if(preferences.data&&!changed.length)setForm(preferences.data);},[preferences.data,changed.length]);
 const refresh=()=>{next.reload();preferences.reload();cohorts.reload();setReportVersion(v=>v+1);};
 const action=useAction(refresh);
 useEffect(()=>{const reload=()=>{next.reload();preferences.reload();cohorts.reload();setReportVersion(v=>v+1);};window.addEventListener('focus',reload);return()=>window.removeEventListener('focus',reload);},[next.reload,preferences.reload,cohorts.reload]);
 const change=(key:string,value:unknown)=>{setForm(current=>current?{...current,[key]:value}:null);setChanged(keys=>keys.includes(key)?keys:[...keys,key]);};
 const open=(item:Row)=>void action.act(async()=>{if(item.kind==='lesson')await p.onLesson(item.course_id,item.id);else if(item.kind==='quiz')await p.onQuiz(item.id);else router.push('/lms/167/Activities/'+item.id+'/162');},'Recommended activity opened.');
 const descriptions:Record<string,string>={'Learner what next':'Next steps from your saved lesson progress, latest assessments, discussions, goals and pace.','Teacher class insights':'Course completion and topic evidence from records in your assigned courses and cohorts.','Personalisation settings':'Save your own learning goals, recommendation pace, languages and notification preference.'};
 const allowed=whatNext?policy.data?.can_recommend:insights?policy.data?.can_inspect:policy.data?.can_edit_settings;
 const reportQuery=cohortId?'?cohort_id='+encodeURIComponent(cohortId):'';
 return <><Header module={162} title={policy.data?.screens?.find((screen:Row)=>screen.tab===p.tab)?.label||p.tab} description={descriptions[p.tab]}><Button onClick={refresh}>Refresh personalisation</Button></Header>
  <Feedback error={policy.error||next.error||preferences.error||cohorts.error||action.error} notice={action.notice} loading={policy.loading||(whatNext?next.loading:settings?preferences.loading:cohorts.loading)}/>
  {policy.data&&!allowed&&<Alert severity="info">This destination requires the role shown in the workflow navigation.</Alert>}
  {whatNext&&allowed&&<>{next.data&&<section className="panel"><div className="row"><h2>Your learning plan</h2><Chip label={next.data.preferences.pace+' · up to '+next.data.limit+' suggestions'}/></div>{next.data.preferences.goals&&<p data-no-translate>{next.data.preferences.goals}</p>}<p className="muted">Goal terms influence ranking. Pace sets the suggestion limit. These are record-based rules, not AI-generated recommendations.</p><Button onClick={()=>router.push('/lms/162/Personalisation%20settings')}>Personalisation Settings</Button></section>}
   <div className="course-grid">{next.data?.items.map((item:Row)=><section className="panel recommendation" key={item.kind+'-'+item.id}><span className="eyebrow">{item.kind} · {item.course_title}</span><h2 data-no-translate>{item.title}</h2><p>{item.reason}</p>{item.goal_matches?.length>0&&<p className="muted" data-no-translate>Matches your goal terms: {item.goal_matches.join(', ')}</p>}<Button variant="contained" disabled={action.busy} onClick={()=>open(item)}>Take the next step</Button></section>)}</div>
   {next.data&&!next.data.items.length&&!next.loading&&<Empty>No next steps from your current records. Enrol in a course, continue available learning, or update your goals.</Empty>}
  </>}
  {insights&&allowed&&<><section className="panel"><h2>Class scope</h2><p className="muted">Choose a cohort or inspect all assigned courses. Topic strengths/gaps use submitted assessment evidence; current completion counts use published lessons and active/completed enrolments.</p>{cohorts.controls}<label className="field-label" htmlFor="insight-cohort">Cohort</label><select id="insight-cohort" className="full-select" value={cohortId} onChange={e=>setCohortId(e.target.value)}><option value="">All assigned courses and cohorts</option>{cohorts.data?.map(cohort=><option key={cohort.id} value={cohort.id}>{cohort.course_title} / {cohort.name}</option>)}</select><p className="muted">Assessment review boundary: below {policy.data?.review_below_percent}%.</p></section>
   <section className="panel"><h2>Topic strengths and gaps</h2><ServerTable key={'topics-'+cohortId+'-'+reportVersion} url={'/final/class-topics'+reportQuery} api={p.api} fields={[{key:'course',label:'Course'},{key:'topic',label:'Topic'},{key:'responses',label:'Responses'},{key:'accuracy',label:'Correct %'},{key:'status',label:'Evidence'}]}/></section>
   <section className="panel"><h2>Current lesson completion</h2><ServerTable key={'lessons-'+cohortId+'-'+reportVersion} url={'/lists/lesson_insights'+reportQuery} api={p.api} fields={[{key:'title',label:'Course'},{key:'learners',label:'Enrolled learners'},{key:'lessons',label:'Published lessons'},{key:'completed_lessons',label:'Lesson completions'}]}/></section>
  </>}
  {settings&&allowed&&form&&<section className="panel settings-panel"><h2>My personalisation settings</h2><form onSubmit={e=>{e.preventDefault();void action.act(async()=>{const updates=Object.fromEntries(changed.map(key=>[key,form[key]]));const saved=await p.api<Row>('/features/preferences',updates);preferences.setData(saved);setChanged([]);},'Personalisation settings saved. Recommendations use these saved goals and pace.');}}>
   <TextField fullWidth multiline minRows={4} label="My learning goals" value={form.goals} onChange={e=>change('goals',e.target.value)} slotProps={{htmlInput:{maxLength:4000}}}/><label className="field-label" htmlFor="personalisation-pace">Learning pace</label><select id="personalisation-pace" className="full-select" value={form.pace} onChange={e=>change('pace',e.target.value)}>{policy.data?.pace_options.map((option:Row)=><option key={option.value} value={option.value}>{option.value} · up to {option.limit} suggestions</option>)}</select>
   <TextField fullWidth required label="Preferred content language" margin="normal" value={form.language} onChange={e=>change('language',e.target.value)} slotProps={{htmlInput:{maxLength:50}}}/><label className="field-label" htmlFor="personalisation-locale">Interface language</label><select id="personalisation-locale" className="full-select" value={form.ui_language} onChange={e=>change('ui_language',e.target.value)}>{policy.data?.ui_languages.map((option:Row)=><option key={option.value} value={option.value}>{option.label}</option>)}</select>
   <label className="checkbox-line"><input type="checkbox" checked={form.notifications} onChange={e=>change('notifications',e.target.checked)}/> Receive new course-announcement notifications</label><p className="muted">Interface language updates after saving. Content language is used by translation browsing. Existing notifications remain when new notifications are disabled.</p><Button type="submit" variant="contained" disabled={action.busy||!changed.length}>Save settings</Button>{changed.length>0&&<Button disabled={action.busy} onClick={()=>{setChanged([]);setForm(preferences.data);}}>Discard unsaved changes</Button>}
  </form></section>}
 </>;
}
