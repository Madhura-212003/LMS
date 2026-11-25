const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const ts=require('typescript');
const code=ts.transpileModule(fs.readFileSync('app/lecture-progress.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const exported={};new Function('exports',code)(exported);

test('playback progress saves cannot overtake an earlier notes save',async()=>{
 const sent=[];let release;
 const queue=exported.createProgressQueue(async snapshot=>{
  sent.push(snapshot);if(sent.length===1)await new Promise(resolve=>{release=resolve;});return snapshot;
 });
 const notes=queue({position:20,completed:false,notes:'Newest notes'});
 const automatic=queue({position:30,completed:false});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(sent.length,1);release();await Promise.all([notes,automatic]);
 assert.equal(sent.length,2);assert.equal(sent[0].notes,'Newest notes');assert.ok(!('notes' in sent[1]));
});

test('a failed progress request does not prevent the next explicit retry',async()=>{
 let attempts=0;
 const queue=exported.createProgressQueue(async snapshot=>{if(++attempts===1)throw new Error('Connection lost');return snapshot;});
 await assert.rejects(queue({position:4,completed:false}),/Connection lost/);
 assert.equal((await queue({position:8,completed:false,notes:''})).position,8);
 assert.equal(attempts,2);
});
