export type Actor={role:string;roles?:string[];permissions?:string[]};
export function has(user:Actor|null|undefined,cap:string){return !!user?.permissions?.includes(cap);}
export function defaultTab(user:Actor|null,id:number,tabs:string[],requested?:string){return requested??(user?tabsFor(user,id,tabs)[0]:tabs[0])??'';}
export function tabsFor(user:Actor,id:number,tabs:string[]){
 const r=new Set(user.roles||[user.role]);
 if(id===162)return tabs.filter(t=>['Learner what next','What next'].includes(t)?r.has('Learner'):['Teacher class insights','Class insights'].includes(t)?has(user,'teaching_read')&&['Admin','Teacher','Coordinator'].some(role=>r.has(role)):['Personalisation settings','Preferences'].includes(t)?r.has('Learner')||r.has('Admin'):false);
 if(id===164)return tabs.filter(t=>['Language preference','Translated content view'].includes(t)?r.has('Learner'):['Translation queue / Editor','Translation queue'].includes(t)?has(user,'translate')||has(user,'translation_review'):['Glossary and coverage','Glossary'].includes(t)?has(user,'glossary_manage'):false);
 if(id===163)return tabs.filter(t=>['AI tutor chat','AI assistant','Course tutor'].includes(t)?r.has('Learner'):['Teacher tutor review','Tutor review'].includes(t)?has(user,'tutor_review'):['Tutor policy / Settings','Tutor settings'].includes(t)?has(user,'tutor_policy'):false);
 if(r.has('Admin'))return tabs;
 if(r.size===1&&r.has('Librarian'))return id===158?tabs:[];
 if(r.size===1&&r.has('Seller'))return id===180?tabs:id===156?tabs.filter(t=>['My courses','Course catalogue','Teaching dashboard'].includes(t)):[];
 if(!r.has('Learner')&&!r.has('Teacher')&&!r.has('Coordinator')&&!r.has('Admin')){
  const allowed=new Set<number>([156]);
  if(has(user,'content_write')||has(user,'content_review'))allowed.add(157);
  if(has(user,'translate')||has(user,'translation_review'))allowed.add(164);
  if(has(user,'library_manage'))allowed.add(158);
  if(r.has('Seller'))allowed.add(180);
  if(r.has('TA'))for(const n of [157,159,160,165,166,170,172,176,177,178])allowed.add(n);
  if(!allowed.has(id))return [];
 }
 const requirements:Record<string,string>={'Class schedule / Manage':'roster_manage','Course editor':'course_manage','Cohort setup':'roster_manage','Enrolment roster':'roster_manage','Course staff':'staff_assign','Teaching dashboard':'course_manage','Cohorts':'roster_manage','Content review':'content_review','Lesson editor':'content_write','Content editor':'content_write','Resource management':'library_manage','Librarian dashboard':'library_manage','Create assignment':'assessment_write','Question bank':'assessment_write','Marking queue':'mark','Tutor review':'assessment_write','Tutor settings':'assessment_write','Upload lecture':'lecture_manage','Lecture upload / Edit / Publish':'lecture_manage','Path builder':'path_manage','Teacher path progress':'teaching_read','Path progress':'teaching_read','Class insights':'teaching_read','Skills progress':'teaching_read','Participation':'teaching_read','Credential rules':'assessment_write','Teacher review':'mark','Teacher communication review':'mark','Exam insights':'teaching_read','NEET insights':'teaching_read','JEE insights':'teaching_read','UPSC insights':'teaching_read','Placement insights':'teaching_read','Career insights':'teaching_read'};
 if(r.has('TA')&&!has(user,'assessment_write')){if(id===170)return tabs.filter(t=>t==='Lab results');if([172,176,177,178].includes(id))return tabs.filter(t=>t==='Teacher review');}
 return tabs.filter(t=>t!=='Seller dashboard'||r.has('Teacher')||r.has('Seller')).filter(t=>t!=='Translation queue'||has(user,'translate')||has(user,'translation_review')).filter(t=>!requirements[t]||has(user,requirements[t]));
}
