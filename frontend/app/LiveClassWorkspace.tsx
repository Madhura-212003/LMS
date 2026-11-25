'use client';

import {useEffect,useState} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {Button,Chip,TextField} from '@mui/material';
import {FeatureProps,Row,useData,useCatalogue,useAction,Header,Feedback,Empty,ItemEditor,ItemMeta} from './feature-shared';
import {AttendanceSummary} from './FinalWorkflows';

const destination=(tab:string)=>'/lms/159/'+encodeURIComponent(tab);

export default function LiveClassWorkspace(p:FeatureProps){
 const router=useRouter(),pathname=usePathname();
 const managePage=p.tab==='Class schedule / Manage',roomPage=p.tab==='Live class room',attendancePage=p.tab==='Attendance summary';
 const rawId=pathname.split('/').filter(Boolean)[3]||'';
 const classId=roomPage&&/^\d+$/.test(rawId)?Number(rawId):0;
 const workflow=useData<Row>('/live-workflow',p.api),schedule=useCatalogue('live',p.api);
 const detail=useData<Row>(classId?'/features/live/classes/'+classId:'',p.api);
 const current=detail.data?.id===classId?detail.data:null;
 const [enteredId,setEnteredId]=useState(0),[meeting,setMeeting]=useState(''),[video,setVideo]=useState(false),[body,setBody]=useState(''),[attendanceVersion,setAttendanceVersion]=useState(0);
 const entered=!!classId&&enteredId===classId;
 const room=useData<Row>(entered?'/features/live/'+classId+'/room':'',p.api);
 const activeRoom=room.data?.class_id===classId?room.data:null;
 const refresh=()=>{schedule.reload();detail.reload();room.reload();setAttendanceVersion(v=>v+1);};
 const action=useAction(refresh);
 useEffect(()=>{setVideo(false);setBody('');setMeeting('');setEnteredId(0);},[classId]);
 useEffect(()=>{const reload=()=>{schedule.reload();detail.reload();room.reload();setAttendanceVersion(v=>v+1);};window.addEventListener('focus',reload);return()=>window.removeEventListener('focus',reload);},[schedule.reload,detail.reload,room.reload]);
 useEffect(()=>{if(!entered||!workflow.data?.poll_ms)return;const timer=setInterval(()=>{detail.reload();room.reload();},workflow.data.poll_ms);return()=>clearInterval(timer);},[entered,workflow.data?.poll_ms,detail.reload,room.reload]);
 const open=(id:number)=>router.push(destination('Live class room')+'/'+id);
 const canSchedule=!!workflow.data?.can_schedule;
 const descriptions:Record<string,string>={
  'Class schedule / Manage':'Schedule, revise and cancel classes for your assigned courses and cohorts.',
  'Live class room':'Choose a class, join explicitly, and use its discussion, hand raising and video room.',
  'Attendance summary':'Review recorded attendance. Learners see their own cohort records; permitted staff can make audited corrections.',
  'Learner class schedule':'Your cohort classes, start and end times, and current server-checked joining availability.'};
 return <><Header module={159} title={workflow.data?.screens?.find((screen:Row)=>screen.tab===p.tab)?.label||p.tab} description={descriptions[p.tab]}>
  <div className="actions"><Button onClick={refresh}>Refresh classes</Button>{managePage&&canSchedule&&<ItemEditor kind="live" api={p.api} onSaved={refresh} button="Schedule class"/>}</div>
 </Header><Feedback error={workflow.error||schedule.error||detail.error||room.error||action.error} notice={action.notice} loading={workflow.loading||(classId?detail.loading:!attendancePage&&schedule.loading)}/>
 {attendancePage?<AttendanceSummary key={attendanceVersion} api={p.api} staff={!!workflow.data?.can_correct_attendance}/>:roomPage&&classId?<>
  <div className="actions"><Button onClick={()=>router.push(destination('Learner class schedule'))}>Back to class schedule</Button><Button onClick={()=>router.push(destination('Attendance summary'))}>Attendance Summary</Button></div>
  {current&&<section className="panel"><div className="row"><h2>{current.title}</h2><Chip label={current.status}/></div><p>{current.description}</p><p>{current.course_title} · {current.cohort_name} · {current.owner}</p><p>{new Date(current.start_at).toLocaleString()} — {new Date(current.end_at).toLocaleString()}</p>
   {!entered?<><p className="muted">{current.join_reason||'This class is open. Joining records attendance before opening the discussion or video.'}</p><Button variant="contained" disabled={action.busy||!current.can_join} onClick={()=>void action.act(async()=>{const result=await p.api<Row>('/features/live/'+classId+'/join',{});setMeeting(result.meeting_url);setEnteredId(classId);},'Joined classroom. Attendance recorded.')}>{current.attendance&&!current.attendance.left_at?'Resume classroom':'Join classroom'}</Button></>:<>
    <div className="actions"><Button disabled={action.busy} onClick={()=>void action.act(async()=>{await p.api('/features/live/'+classId+'/room',{action:'leave'});setEnteredId(0);setVideo(false);setMeeting('');},'Left classroom. Attendance retained.')}>Leave classroom</Button><Button disabled={!activeRoom?.open} onClick={()=>setVideo(v=>!v)}>{video?'Close video':'Open video room'}</Button></div>
    {video&&activeRoom?.open&&<iframe className="video-room" title={current.title+' video'} src={meeting} allow="camera; microphone; fullscreen; display-capture; autoplay" allowFullScreen/>}
    {activeRoom&&!activeRoom.open&&<p className="muted">The classroom has closed. Chat and hand raising are disabled; attendance remains available.</p>}
   </>}
  </section>}
  {entered&&<div className="bottom-grid"><section className="panel"><h2>Participants</h2>{activeRoom?.participants.map((person:Row)=><p key={person.id}>{person.name} {person.raised?'✋':''} <Chip size="small" label={person.left?'Left':person.status}/></p>)}<Button disabled={action.busy||!activeRoom?.open} onClick={()=>void action.act(()=>p.api('/features/live/'+classId+'/room',{action:'hand'}),'Hand state updated.')}>Raise / lower hand</Button></section>
   <section className="panel"><h2>Class discussion</h2><div className="room-chat">{activeRoom?.messages.map((message:Row)=><p key={message.id}><b>{message.user__first_name}</b><br/>{message.body}</p>)}</div><TextField fullWidth multiline minRows={2} label="Message" value={body} onChange={e=>setBody(e.target.value)} slotProps={{htmlInput:{maxLength:2000}}}/><Button disabled={action.busy||!activeRoom?.open||!body.trim()} onClick={()=>void action.act(async()=>{await p.api('/features/live/'+classId+'/room',{action:'chat',body});setBody('');},'Message sent.')}>Send message</Button></section></div>}
 </>:<>{roomPage&&<p className="muted">Open a class below, then select Join classroom. Opening a schedule entry does not mark attendance.</p>}{schedule.toolbar}
  {schedule.items.map(item=><section className="panel live-card" key={item.id}><ItemMeta item={item}/><h2>{item.title}</h2><p>{item.description}</p><p>{item.cohort_name} · {item.owner}</p><div className="class-time">{new Date(item.start_at).toLocaleString()} — {new Date(item.end_at).toLocaleString()}</div><p className="muted">{item.join_reason||'Open for joining'}</p><div className="actions"><Button variant="outlined" onClick={()=>open(item.id)}>Open Live Class Room</Button>{managePage&&canSchedule&&!['Cancelled','Ended'].includes(item.status)&&<><ItemEditor kind="live" item={item} api={p.api} onSaved={refresh} button="Edit schedule"/><Button color="warning" disabled={action.busy} onClick={()=>{if(window.confirm('Cancel '+item.title+'? Existing attendance and messages will be retained.'))void action.act(()=>p.api('/features/catalogue/live/'+item.id+'/status',{status:'Cancelled'}),'Class cancelled. New joins are blocked.');}}>Cancel class</Button></>}</div></section>)}
  {!schedule.items.length&&!schedule.loading&&<Empty>No class schedules match your assigned course/cohort access and filters.</Empty>}{schedule.pagination}
 </>}
 </>;
}
