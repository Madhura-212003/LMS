const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync('app/role-navigation.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const exportsObject={};new Function('exports',code)(exportsObject);
const {tabsFor}=exportsObject;
const modulesCode=ts.transpileModule(fs.readFileSync('app/modules.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const moduleExports={};new Function('exports',modulesCode)(moduleExports);
const caps={Admin:['course_manage','roster_manage','content_write','content_review','classroom_manage','assessment_write','mark','teaching_read','translate','translation_review','library_manage','staff_assign'],Coordinator:['course_manage','roster_manage','classroom_manage','teaching_read','staff_assign'],Teacher:['course_manage','roster_manage','content_write','content_review','classroom_manage','assessment_write','mark','teaching_read','translate','translation_review'],Author:['content_write'],Reviewer:['content_review','translation_review'],TA:['classroom_manage','mark','teaching_read'],Librarian:['library_manage'],Translator:['translate'],Seller:['course_manage'],Learner:[]};
for(const role of ['Admin','Coordinator','Teacher','TA'])caps[role].push('lecture_manage');
for(const role of ['Admin','Coordinator','Teacher'])caps[role].push('path_manage','tutor_review');
for(const role of ['Admin','Coordinator'])caps[role].push('tutor_policy','glossary_manage');
caps.Coordinator.push('translate','translation_review');
test('bare module routes select the first allowed tab for every role',()=>{
 for(const [role,permissions] of Object.entries(caps))for(const m of moduleExports.modules){
  const user={role,roles:[role],permissions},allowed=tabsFor(user,m.id,m.tabs);
  assert.equal(exportsObject.defaultTab(user,m.id,m.tabs),allowed[0]||'',`${role}: F${m.id}`);
 }
 const assistant={role:'TA',permissions:caps.TA};
 assert.equal(exportsObject.defaultTab(assistant,170,['Lab catalogue','Lab results']),'Lab results');
 assert.equal(exportsObject.defaultTab(assistant,170,['Lab catalogue','Lab results'],'Lab catalogue'),'Lab catalogue');
});
test('all 250 role/module navigation combinations match actor scope',()=>{
 const expected={Author:[156,157],Reviewer:[156,157,164],TA:[156,157,159,160,165,166,170,172,176,177,178],Librarian:[158],Translator:[156,164],Seller:[156,180]};
 for(const [role,permissions] of Object.entries(caps))for(const m of moduleExports.modules){
  const visible=tabsFor({role,roles:[role],permissions},m.id,m.tabs);
  assert.equal(visible.length>0,expected[role]?expected[role].includes(m.id):true,`${role}: F${m.id}`);
  if(!['Admin','Teacher','Seller'].includes(role))assert.ok(!visible.includes('Seller dashboard'),role);
 }
});
test('combined staff roles retain library and seller modules without broad teaching access',()=>{
 const u={role:'Author',roles:['Author','Librarian','Seller'],permissions:['content_write','library_manage','course_manage']};
 assert.deepEqual(tabsFor(u,158,['Library catalogue','Resource management']),['Library catalogue','Resource management']);
 assert.deepEqual(tabsFor(u,180,['Marketplace browse','Seller dashboard']),['Marketplace browse','Seller dashboard']);
 assert.deepEqual(tabsFor(u,168,['Quiz catalogue','Question bank']),[]);
});
test('Author can author assigned content without review, marking or staff controls',()=>{
 const u={role:'Author',roles:['Author'],permissions:['content_write']};
 assert.deepEqual(tabsFor(u,157,['Content catalogue','Content review','Lesson editor']),['Content catalogue','Lesson editor']);
 assert.deepEqual(tabsFor(u,156,['My courses','Cohorts','Teaching dashboard','Course staff']),['My courses']);
 assert.deepEqual(tabsFor(u,168,['Question bank']),[]);
});
test('Reviewer can review without an authoring control',()=>{
 const u={role:'Reviewer',roles:['Reviewer'],permissions:['content_review','translation_review']};
 assert.deepEqual(tabsFor(u,157,['Content catalogue','Content review','Lesson editor']),['Content catalogue','Content review']);
 assert.deepEqual(tabsFor(u,164,['Language preference','Translation queue','Glossary']),['Translation queue']);
});
test('TA gets marking and classroom access, without assessment authorship',()=>{
 const u={role:'TA',roles:['TA'],permissions:['mark','classroom_manage','teaching_read']};
 assert.deepEqual(tabsFor(u,166,['Feedback','Marking queue']),['Feedback','Marking queue']);
 assert.deepEqual(tabsFor(u,170,['Lab catalogue','Lab results']),['Lab results']);
 assert.deepEqual(tabsFor(u,172,['Practice library','Teacher review']),['Teacher review']);
 assert.deepEqual(tabsFor(u,165,['Assignments','Create assignment']),['Assignments']);
});
test('Coordinator manages cohorts and assignments of staff without marking or authoring',()=>{
 const u={role:'Coordinator',permissions:['course_manage','roster_manage','classroom_manage','staff_assign','teaching_read']};
 assert.deepEqual(tabsFor(u,156,['Cohorts','Teaching dashboard','Course staff']),['Cohorts','Teaching dashboard','Course staff']);
 assert.deepEqual(tabsFor(u,157,['Content catalogue','Content review','Lesson editor']),['Content catalogue']);
 assert.deepEqual(tabsFor(u,166,['Feedback','Marking queue']),['Feedback']);
});
test('Learner never sees staff controls',()=>{
 const u={role:'Learner',permissions:[]};
 assert.deepEqual(tabsFor(u,156,['My courses','Course catalogue','Cohorts','Course staff']),['My courses','Course catalogue']);
 assert.deepEqual(tabsFor(u,168,['Quiz catalogue','Results','Question bank']),['Quiz catalogue','Results']);
});

test('course workflow pages follow server capabilities',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===156).tabs;
 const learner=tabsFor({role:'Learner',permissions:[]},156,tabs);
 assert.deepEqual(learner,['Course catalogue','My courses','Notifications']);
 const teacher=tabsFor({role:'Teacher',permissions:caps.Teacher},156,tabs);
 for(const tab of ['Course editor','Cohort setup','Enrolment roster','Teaching dashboard'])assert.ok(teacher.includes(tab),tab);
 const author=tabsFor({role:'Author',permissions:caps.Author},156,tabs);
 for(const tab of ['Course editor','Cohort setup','Enrolment roster','Teaching dashboard'])assert.ok(!author.includes(tab),tab);
});

test('learning content follows the requested order with separate author and reviewer entry points',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===157).tabs;
 assert.deepEqual(tabs,['Content editor','Content review','Course viewer','Content catalogue']);
 assert.equal(exportsObject.defaultTab({role:'Author',permissions:caps.Author},157,tabs),'Content editor');
 assert.equal(exportsObject.defaultTab({role:'Reviewer',permissions:caps.Reviewer},157,tabs),'Content review');
 assert.equal(exportsObject.defaultTab({role:'Learner',permissions:[]},157,tabs),'Course viewer');
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},157,tabs),['Course viewer','Content catalogue']);
});

test('digital library keeps the five requested destinations with librarian management gates',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===158).tabs;
 assert.deepEqual(tabs,['Library catalogue','Resource management','My library','Resource reader','Librarian dashboard']);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},158,tabs),['Library catalogue','My library','Resource reader']);
 assert.deepEqual(tabsFor({role:'Librarian',permissions:caps.Librarian},158,tabs),tabs);
});

test('live class flow separates scheduling from learner and TA classroom access',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===159).tabs;
 assert.deepEqual(tabs,['Class schedule / Manage','Live class room','Attendance summary','Learner class schedule']);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},159,tabs),tabs.slice(1));
 assert.deepEqual(tabsFor({role:'TA',permissions:caps.TA},159,tabs),tabs.slice(1));
 assert.deepEqual(tabsFor({role:'Teacher',permissions:caps.Teacher},159,tabs),tabs);
});

test('recorded lectures expose the requested authoring roles through a dedicated capability',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===160).tabs;
 assert.deepEqual(tabs,['Lecture upload / Edit / Publish','Learner lecture player','Lecture library / Search']);
 for(const role of ['Teacher','TA','Coordinator','Admin'])assert.deepEqual(tabsFor({role,permissions:caps[role]},160,tabs),tabs);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},160,tabs),tabs.slice(1));
 assert.ok(!caps.TA.includes('assessment_write'));assert.ok(!caps.Coordinator.includes('assessment_write'));
});

test('learning paths use the requested four-page order and Coordinator builder capability',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===161).tabs;
 assert.deepEqual(tabs,['Path builder','Teacher path progress','Learner path view','Path catalogue / Search']);
 for(const role of ['Teacher','Coordinator','Admin'])assert.deepEqual(tabsFor({role,permissions:caps[role]},161,tabs),tabs);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},161,tabs),tabs.slice(2));
 assert.ok(!caps.Coordinator.includes('assessment_write'));
});

test('personalised learning separates private learner steps, teaching evidence and self settings',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===162).tabs;
 assert.deepEqual(tabs,['Learner what next','Teacher class insights','Personalisation settings']);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},162,tabs),[tabs[0],tabs[2]]);
 for(const role of ['Teacher','Coordinator'])assert.deepEqual(tabsFor({role,permissions:caps[role]},162,tabs),[tabs[1]]);
 assert.deepEqual(tabsFor({role:'Admin',permissions:caps.Admin},162,tabs),tabs.slice(1));
});


test('AI tutor uses learner chat, staff review and coordinator policy without assessment escalation',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===163).tabs;
 assert.deepEqual(tabs,['AI tutor chat','Teacher tutor review','Tutor policy / Settings']);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},163,tabs),tabs.slice(0,1));
 assert.deepEqual(tabsFor({role:'Teacher',permissions:caps.Teacher},163,tabs),tabs.slice(1,2));
 assert.deepEqual(tabsFor({role:'Coordinator',permissions:caps.Coordinator},163,tabs),tabs.slice(1));
 assert.deepEqual(tabsFor({role:'Admin',permissions:caps.Admin},163,tabs),tabs.slice(1));
 assert.deepEqual(tabsFor({role:'TA',permissions:caps.TA},163,tabs),[]);
 assert.ok(!caps.Coordinator.includes('assessment_write'));
});


test('multilingual workflow separates learner reading, translation review and glossary control',()=>{
 const tabs=moduleExports.modules.find(m=>m.id===164).tabs;
 assert.deepEqual(tabs,['Language preference','Translated content view','Translation queue / Editor','Glossary and coverage']);
 assert.deepEqual(tabsFor({role:'Learner',permissions:[]},164,tabs),tabs.slice(0,2));
 assert.deepEqual(tabsFor({role:'Translator',permissions:caps.Translator},164,tabs),tabs.slice(2,3));
 assert.deepEqual(tabsFor({role:'Reviewer',permissions:caps.Reviewer},164,tabs),tabs.slice(2,3));
 assert.deepEqual(tabsFor({role:'Coordinator',permissions:caps.Coordinator},164,tabs),tabs.slice(2));
 assert.deepEqual(tabsFor({role:'Admin',permissions:caps.Admin},164,tabs),tabs.slice(2));
});
