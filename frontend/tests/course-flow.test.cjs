const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const React=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const code=ts.transpileModule(fs.readFileSync('app/CourseFlowNavigation.tsx','utf8'),{
 compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}
}).outputText;
const component={};new Function('require','exports',code)(require,component);

test('all server workflow steps remain visible while unauthorized steps are disabled',()=>{
 const screens=[
  {tab:'catalogue',label:'Catalogue from server',role:'Learner',accessible:true},
  {tab:'editor',label:'Editor from server',role:'Teacher',accessible:false},
  {tab:'roster',label:'Roster from server',role:'Coordinator',accessible:false},
 ];
 for(const sidebar of [false,true]){
  const html=renderToStaticMarkup(React.createElement(component.default,{screens,allowed:['catalogue'],active:'catalogue',sidebar,onNavigate:()=>{}}));
  assert.equal((html.match(/<button/g)||[]).length,3);
  assert.equal((html.match(/ disabled=""/g)||[]).length,2);
  assert.ok(html.indexOf('Catalogue from server')<html.indexOf('Editor from server'));
  assert.ok(html.indexOf('Editor from server')<html.indexOf('Roster from server'));
  for(const role of ['Learner','Teacher','Coordinator'])assert.ok(html.includes(role));
  assert.ok(html.includes('aria-current="page"'));
 }
});

test('a visible server step also requires the current client capability scope',()=>{
 const html=renderToStaticMarkup(React.createElement(component.default,{screens:[{tab:'editor',label:'Editor',role:'Teacher',accessible:true}],allowed:[],active:'catalogue',onNavigate:()=>{}}));
 assert.ok(html.includes('disabled=""'));
});
