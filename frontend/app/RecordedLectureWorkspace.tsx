'use client';

import {useEffect,useMemo,useRef,useState} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {Alert,Button,Chip,TextField} from '@mui/material';
import {Api,FeatureProps,Row,useData,useList,useCatalogue,useAction,Header,Feedback,Empty,FileInput,fileURL,ItemMeta} from './feature-shared';
import {createProgressQueue} from './lecture-progress';

const destination=(tab:string)=>'/lms/160/'+encodeURIComponent(tab);
const blank=()=>({course_id:'',course_title:'',title:'',description:'',topic:'',attachment_id:0,captions_id:null as number|null});

function LectureEditor({api,item,policy,onSaved,onCancel}:{api:Api;item:Row|null;policy:Row;onSaved:()=>void;onCancel:()=>void}){
 const courses=useList('/courses',api);
 const [form,setForm]=useState(()=>item?{course_id:String(item.course_id),course_title:item.course_title,title:item.title,description:item.description,topic:item.topic,attachment_id:Number(item.attachment),captions_id:item.captions as number|null}:blank());
 const action=useAction(onSaved);
 const change=(key:string,value:string|number|null)=>setForm(f=>({...f,[key]:value}));
 return <section className="panel"><h2>{item?'Edit lecture':'Upload a new lecture draft'}</h2><Feedback error={courses.error||action.error} notice={action.notice}/>
  <form onSubmit={e=>{e.preventDefault();void action.act(async()=>{await api('/features/catalogue/lectures'+(item?'/'+item.id+'/edit':''),{...form,course_id:Number(form.course_id),status:item?.status||policy.default_status});setForm(blank());},item?'Lecture updated.':'Lecture draft saved. Publish it when ready.');}}>
   {courses.controls}<label className="field-label" htmlFor="lecture-course">Assigned course</label><select id="lecture-course" required disabled={!!item} className="full-select" value={form.course_id} onChange={e=>setForm({...form,course_id:e.target.value,course_title:courses.data?.find(c=>String(c.id)===e.target.value)?.title||'',attachment_id:0,captions_id:null})}><option value="">Choose course</option>{form.course_id&&!courses.data?.some(c=>String(c.id)===form.course_id)&&<option value={form.course_id}>{form.course_title||item?.course_title}</option>}{courses.data?.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select>
   <TextField fullWidth required label="Lecture title" margin="normal" value={form.title} onChange={e=>change('title',e.target.value)} slotProps={{htmlInput:{maxLength:200}}}/><TextField fullWidth multiline minRows={3} label="Description" margin="normal" value={form.description} onChange={e=>change('description',e.target.value)}/><TextField fullWidth label="Topic" margin="normal" value={form.topic} onChange={e=>change('topic',e.target.value)}/>
   {form.course_id?<><FileInput api={api} courseId={Number(form.course_id)} accept={policy.video_accept} label="Lecture video (MP4 or WebM)" onChange={id=>change('attachment_id',id)}/>{form.attachment_id>0&&<p><a href={fileURL(form.attachment_id)} target="_blank" rel="noreferrer">Open selected video</a></p>}<FileInput api={api} courseId={Number(form.course_id)} accept={policy.captions_accept} label="Optional WebVTT captions" onChange={id=>change('captions_id',id)}/>{form.captions_id&&<Button onClick={()=>change('captions_id',null)}>Remove captions from lecture</Button>}</>:<p className="muted">Choose a course before uploading its video or captions.</p>}
   <p className="muted">Saving a new recording creates a draft. Existing learner progress is preserved; replacing a video after learners start requires a new lecture.</p><div className="actions"><Button variant="contained" type="submit" disabled={action.busy||!form.attachment_id}>Save lecture</Button>{item&&<Button disabled={action.busy} onClick={onCancel}>Cancel editing</Button>}</div>
  </form>
 </section>;
}

function LecturePlayer({item,api,policy,onBack}:{item:Row;api:Api;policy:Row;onBack:()=>void}){
 const video=useRef<HTMLVideoElement>(null),ready=useRef(false),last=useRef(item.progress?.position||0);
 const [notes,setNotes]=useState(item.progress?.notes||''),[speed,setSpeed]=useState('1'),[error,setError]=useState(''),[saved,setSaved]=useState<Row|null>(item.progress||null);
 const queue=useMemo(()=>createProgressQueue(snapshot=>api<Row>('/features/lectures/'+item.id+'/progress',snapshot)),[api,item.id]);
 const action=useAction(()=>{});
 const persist=async(completed=false,includeNotes=false)=>{
  if(!policy.can_track_progress)return;
  const position=ready.current?video.current?.currentTime||0:item.progress?.position||0;
  last.current=position;
  const row=await queue({position,completed,...(includeNotes?{notes}:{})});setSaved(row);setError('');
 };
 const autosave=(completed=false)=>void persist(completed).catch(e=>setError(e.message));
 return <section className="panel"><Button onClick={()=>void action.act(async()=>{await persist(false,true);onBack();},'Progress saved')}>Back to Lecture Library / Search</Button><h2 data-no-translate>{item.title}</h2><p data-no-translate>{item.description}</p><p className="muted">{item.course_title} · {item.topic}</p>
  <Feedback error={error||action.error} notice={action.notice}/>
  <video className="lecture-video" ref={video} controls src={fileURL(item.attachment)} onLoadedMetadata={()=>{ready.current=true;if(video.current){const position=Number(item.progress?.position||0);video.current.currentTime=Number.isFinite(video.current.duration)?Math.min(position,video.current.duration):position;}}} onError={()=>setError('Playback failed. Check that the uploaded file is a playable MP4 or WebM, then reopen it.')} onPause={()=>autosave()} onEnded={()=>autosave(true)} onTimeUpdate={()=>{if(ready.current&&video.current&&Math.abs(video.current.currentTime-last.current)>=policy.progress_save_seconds)autosave();}}>
   {item.captions&&<track kind="captions" label="Captions" src={fileURL(item.captions)} default/>}
  </video><div className="actions"><label>Playback speed <select aria-label="Playback speed" value={speed} onChange={e=>{setSpeed(e.target.value);if(video.current)video.current.playbackRate=Number(e.target.value);}}>{['0.5','0.75','1','1.25','1.5','2'].map(value=><option key={value} value={value}>{value}×</option>)}</select></label></div>
  {policy.can_track_progress?<>{saved&&<p className="muted">Last saved position: {Math.round(saved.position)} seconds · {saved.completed?'Completed':'In progress'}</p>}<TextField fullWidth multiline minRows={4} label="My lecture notes" value={notes} onChange={e=>setNotes(e.target.value)} slotProps={{htmlInput:{maxLength:20000}}}/><Button variant="contained" disabled={action.busy} onClick={()=>void action.act(()=>persist(false,true),'Notes and playback position saved.')}>Save notes and progress</Button></>:<Alert severity="info">Staff preview. Learner progress and notes are not recorded for this account.</Alert>}
 </section>;
}

export default function RecordedLectureWorkspace(p:FeatureProps){
 const router=useRouter(),pathname=usePathname();
 const editor=p.tab==='Lecture upload / Edit / Publish',player=p.tab==='Learner lecture player';
 const rawId=pathname.split('/').filter(Boolean)[3]||'';
 const lectureId=player&&/^\d+$/.test(rawId)?Number(rawId):0;
 const policy=useData<Row>('/lecture-workflow',p.api),catalogue=useCatalogue('lectures',p.api);
 const detail=useData<Row>(lectureId?'/features/lectures/resources/'+lectureId:'',p.api);
 const current=detail.data?.id===lectureId?detail.data:null;
 const [editing,setEditing]=useState<Row|null>(null);
 const refresh=()=>{catalogue.reload();detail.reload();};
 const action=useAction(refresh);
 useEffect(()=>{const reload=()=>{catalogue.reload();detail.reload();};window.addEventListener('focus',reload);return()=>window.removeEventListener('focus',reload);},[catalogue.reload,detail.reload]);
 const open=(id:number)=>router.push(destination('Learner lecture player')+'/'+id);
 return <><Header module={160} title={policy.data?.screens?.find((screen:Row)=>screen.tab===p.tab)?.label||p.tab} description={editor?'Upload a course recording, edit its metadata and publish it for learners.':player?'Choose a lecture or resume a recording with your saved progress and private notes.':'Search accessible course recordings by title, topic and publication state.'}><Button onClick={refresh}>Refresh lectures</Button></Header>
  <Feedback error={policy.error||catalogue.error||detail.error||action.error} notice={action.notice} loading={policy.loading||(lectureId?detail.loading:catalogue.loading)}/>
  {player&&lectureId?current&&policy.data&&<LecturePlayer key={current.id} item={current} api={p.api} policy={policy.data} onBack={()=>router.push(destination('Lecture library / Search'))}/>:player?<section className="panel player-start"><h2>Choose a recording to watch</h2><p>Find a recording in Lecture Library / Search. Opening it brings you here with its video, captions, saved position and private notes.</p><Button variant="contained" onClick={()=>router.push(destination('Lecture library / Search'))}>Find a lecture</Button></section>:<>
   {editor&&policy.data?.can_manage&&<LectureEditor key={editing?.id||'new'} api={p.api} item={editing} policy={policy.data} onSaved={()=>{setEditing(null);refresh();}} onCancel={()=>setEditing(null)}/>}
   {player&&<p className="muted">Select a published lecture below to open its player.</p>}{catalogue.toolbar}<div className="course-grid">{catalogue.items.map(item=><article className="panel" key={item.id}><ItemMeta item={item}/><h2>{item.title}</h2><p>{item.description}</p><p className="muted">{item.topic} · {item.progress?.completed?'Completed':item.progress?'Resume at '+Math.round(item.progress.position)+' seconds':'Not started'}</p><div className="actions"><Button variant="outlined" onClick={()=>open(item.id)}>{policy.data?.can_track_progress?'Open Learner Lecture Player':'Preview recording'}</Button>
    {editor&&policy.data?.can_manage&&<><Button onClick={()=>{setEditing(item);window.scrollTo({top:0,behavior:'smooth'});}}>Edit lecture</Button>{policy.data.publication_statuses.includes(item.status)&&<Button disabled={action.busy} onClick={()=>void action.act(()=>p.api('/features/catalogue/lectures/'+item.id+'/status',{status:item.status==='Draft'?'Published':'Draft'}),'Publication status updated.')}>{item.status==='Draft'?'Publish':'Unpublish'}</Button>}<Button color="warning" disabled={action.busy||item.status==='Archived'} onClick={()=>{if(window.confirm('Archive '+item.title+'? Existing learner progress and notes are retained.'))void action.act(()=>p.api('/features/catalogue/lectures/'+item.id+'/status',{status:'Archived'}),'Lecture archived; learner records retained.');}}>Archive</Button></>}
   </div></article>)}</div>{!catalogue.loading&&!catalogue.items.length&&<Empty>No lectures match your course access and filters. Authorized staff can upload a recording; learners see published recordings from enrolled courses.</Empty>}{catalogue.pagination}
  </>}
 </>;
}
