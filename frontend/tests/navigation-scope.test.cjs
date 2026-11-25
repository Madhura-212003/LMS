const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),ts=require('typescript');
const source=ts.transpileModule(fs.readFileSync('app/navigation-scope.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const exported={};new Function('exports',source)(exported);

test('slow course and quiz responses cannot replace a different screen',async()=>{
 const scope=exported.createNavigationScope(),applied=[];
 const courseVisit=scope.enter('learner|/lms/156/My courses');
 let release;const response=new Promise(resolve=>release=resolve).then(()=>{if(scope.owns(courseVisit))applied.push('old course');});
 const libraryVisit=scope.enter('learner|/lms/158/Library catalogue');
 release();await response;
 assert.deepEqual(applied,[]);assert.ok(scope.owns(libraryVisit));
});
test('returning to the same route does not revive a response from an earlier visit',()=>{
 const scope=exported.createNavigationScope(),first=scope.enter('learner|quiz');
 assert.equal(scope.enter('learner|quiz'),first);
 scope.enter('learner|library');const revisit=scope.enter('learner|quiz');
 assert.ok(!scope.owns(first));assert.ok(scope.owns(revisit));
});
test('changing accounts invalidates results even on the same route',()=>{
 const scope=exported.createNavigationScope(),previous=scope.enter('student|course');
 scope.enter('teacher|course');assert.ok(!scope.owns(previous));
});
