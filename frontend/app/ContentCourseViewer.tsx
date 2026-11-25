'use client';

import {useEffect} from 'react';
import {Button, Chip, LinearProgress} from '@mui/material';
import {Api, Row, useList, useAction, Header, Feedback, Empty} from './feature-shared';

export default function ContentCourseViewer({api,onOpen}:{api:Api;onOpen:(courseId:number,lessonId:number)=>Promise<void>}){
 const courses=useList('/courses',api), action=useAction(courses.reload);
 useEffect(()=>{const refresh=()=>courses.reload();window.addEventListener('focus',refresh);return()=>window.removeEventListener('focus',refresh);},[courses.reload]);
 return <><Header module={157} title="Course Viewer" description="Open a course you can access and read its lessons in order. Learners see published lessons from enrolled courses."><Button onClick={courses.reload}>Refresh courses</Button></Header>
  <Feedback error={courses.error||action.error} loading={courses.loading}/>{courses.controls}
  <div className="course-grid">{courses.data?.map((course:Row)=><section className="panel" key={course.id}>
   <div className="row"><span className="eyebrow">{course.subject} · {course.level}</span><Chip size="small" label={course.status}/></div>
   <h2 data-no-translate>{course.title}</h2><p data-no-translate>{course.description}</p><p className="muted">{course.owner}</p>
   {course.enrolment_status&&<><p>{course.enrolment_status} · {course.progress}% complete</p><LinearProgress variant="determinate" value={course.progress}/></>}
   <div className="actions"><Button variant="contained" disabled={action.busy} onClick={()=>void action.act(()=>onOpen(course.id,0),'Course opened')}>Open course viewer</Button></div>
  </section>)}</div>
  {!courses.loading&&!courses.data?.length&&<Empty>No accessible courses match this view. Learners need an enrolled place; staff need an assigned course.</Empty>}
 </>;
}
