'use client';

export type CourseScreen={tab:string;label:string;role:string;accessible:boolean};

export default function CourseFlowNavigation({screens,allowed,active,onNavigate,sidebar=false,workflowLabel='Courses and enrolment workflow',restrictedLabel='Staff access required'}:{
 screens:CourseScreen[];allowed:string[];active:string;onNavigate:(tab:string)=>void;sidebar?:boolean;workflowLabel?:string;restrictedLabel?:string;
}){
 return <nav className={sidebar?'course-flow-sidebar':'course-flow-navigation'+' workflow-steps-'+screens.length} aria-label={workflowLabel}>
  {screens.map((screen,index)=>{
   const enabled=screen.accessible&&allowed.includes(screen.tab);
   return <button key={screen.tab} type="button" disabled={!enabled} aria-current={active===screen.tab?'page':undefined}
    title={enabled?screen.label:screen.label+' requires an authorized '+screen.role+' or staff account'}
    onClick={()=>onNavigate(screen.tab)}>
    {!sidebar&&<span className="course-flow-step" aria-hidden="true">{index+1}</span>}
    <span className="course-flow-text"><strong>{screen.label}</strong><small>{screen.role}{!enabled?' · '+restrictedLabel:''}</small></span>
   </button>;
  })}
 </nav>;
}
