const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const walk=n=>[n,...n.children.flatMap(walk)];
class Element{
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.style={};this.dataset={};this.events={};this.attrs={};this.isConnected=true;this.value='';this.disabled=false;this.hidden=false;this.clientWidth=360;this.clientHeight=400;this.naturalWidth=400;this.naturalHeight=200;this.videoWidth=this.tagName==='VIDEO'?160:0;this.videoHeight=this.tagName==='VIDEO'?90:0;this.duration=155;this.readyState=2;this.paused=true;this._time=0}
 append(...items){for(const n of items){n.parent=this;n.isConnected=true;this.children.push(n)}}replaceChildren(...items){for(const n of this.children)n.isConnected=false;this.children=[];this.append(...items)}
 setAttribute(k,v){this.attrs[k]=v}getAttribute(k){return this.attrs[k]}removeAttribute(k){delete this.attrs[k]}addEventListener(k,fn){this.events[k]=fn}
 showModal(){this.open=true}close(){this.open=false}remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this)}
 pause(){this.paused=true}play(){this.paused=false;return Promise.resolve()}load(){queueMicrotask(()=>{this.onloadedmetadata?.();this.onloadeddata?.()})}
 set src(value){this._src=value;if(this.tagName==='IMG')queueMicrotask(()=>this.onload?.())}get src(){return this._src}
 set currentTime(value){this._time=value;queueMicrotask(()=>this.onseeked?.())}get currentTime(){return this._time}
 querySelector(s){return this.querySelectorAll(s)[0]||null}querySelectorAll(s){return walk(this).slice(1).filter(n=>s.split(',').some(part=>part.startsWith('.')?n.className?.split(' ').includes(part.slice(1)):n.tagName===part.toUpperCase()))}
 getContext(){return {setTransform(){},fillRect(){},drawImage:()=>{this.draws=(this.draws||0)+1},beginPath(){},rect(){},fill(){},strokeRect(){},moveTo(){},lineTo(){},stroke(){}}}
 getBoundingClientRect(){return {left:0,top:0,width:320,height:60}}setPointerCapture(){}
}
const dialogs=[],requests=[];let serial=0,revoked=0,fail=false,lastEdits=null,nextFrame=null;
const context={window:{devicePixelRatio:1,addEventListener(){},removeEventListener(){}},document:{createElement:t=>new Element(t),body:{append:d=>dialogs.push(d)}},
crypto:{randomUUID:()=>String(++serial).padStart(10,'x')},URL:{createObjectURL:()=> 'blob:private',revokeObjectURL:()=>revoked++},requestAnimationFrame:fn=>{nextFrame=fn;return 1},cancelAnimationFrame(){},
FileReader:class{readAsDataURL(file){this.result='data:'+file.type+';base64,cGhvdG8=';queueMicrotask(()=>this.onload())}},
XMLHttpRequest:class{constructor(){this.upload={}}open(){}setRequestHeader(){}send(body){const data=JSON.parse(body);requests.push({path:'/media-editor/upload',body:data});this.status=200;this.responseText=JSON.stringify({id:'original-'+serial,info:{duration_ms:data.mime.startsWith('video/')?155000:0}});queueMicrotask(()=>this.onload())}abort(){}},
fetch:async(path,options={})=>{const body=options.body&&JSON.parse(options.body);requests.push({path,body});if(path==='/media-editor/process')lastEdits=body.edits;const failed=fail&&path==='/media-editor/process';if(failed)fail=false;return {ok:!failed,json:async()=>failed?{error:'Connection lost. Retry.'}:path==='/media-editor/policy'?{plaza_seconds:60,max_source_bytes:20*1024*1024}:path==='/media-editor/process'?{id:'job',state:'queued'}:{id:'job',state:'ready',parts:[{id:'rendered',mime:'image/jpeg',poster:'cGhvdG8=',duration_ms:lastEdits?.end_ms-lastEdits?.start_ms||0,start_ms:lastEdits?.start_ms||0,end_ms:lastEdits?.end_ms||0}]}}},
setTimeout:fn=>{queueMicrotask(fn);return 1},clearTimeout(){},queueMicrotask};vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/media-editor.js','utf8'),context);
const editor=context.window.OrbitMediaEditor,tick=()=>new Promise(setImmediate),label=n=>(n.textContent||'')+n.children.map(label).join(''),find=(d,text)=>d.querySelectorAll('button').find(b=>label(b)===text),file=(type='image/png')=>({size:100,type});
const point=(target,ms)=>({target,pointerId:1,clientX:320*ms/155000,preventDefault(){}});
(async()=>{
 assert.deepEqual(Array.from(editor.ranges(155000,0,155000,true),r=>Array.from(r)),[[0,60000],[60000,120000],[120000,155000]]);assert.throws(()=>editor.ranges(61000,0,61000,false));assert.equal(editor.time(23000),'00:23');assert.equal(editor.time(5500),'00:05.50');assert.equal(editor.time(59999),'01:00');
 let pending=editor.open({files:[file()],destination:'vibe',token:'synthetic'});await tick();find(dialogs.at(-1),'Back').onclick();assert.equal(await pending,null);assert(!requests.some(r=>r.path==='/media-editor/upload'));
 pending=editor.open({files:[file()],destination:'vibe',token:'synthetic'});await tick();let d=dialogs.at(-1);assert(find(d,'Crop'));assert(!find(d,'Trim'));find(d,'Crop').onclick();find(d,'1:1').onclick();find(d,'Apply').onclick();
 assert(editor.back());assert(find(d,'Discard changes'));assert(editor.back());assert(find(d,'Discard changes'));find(d,'Keep editing').onclick();find(d,'Crop').onclick();find(d,'9:16').onclick();find(d,'Cancel').onclick();
 const sending=find(d,'Done').onclick();find(d,'Preparing…').onclick();await sending;const selected=await pending;assert.equal(selected[0].media_id,'rendered');assert(Math.abs(lastEdits.crop_rect.w-.5)<1e-9);assert(Math.abs(lastEdits.crop_rect.h-1)<1e-9);assert(!requests.some(r=>r.path==='/vibe/publish'));assert(revoked>0);
 pending=editor.open({files:[file('video/mp4')],destination:'vibe',token:'synthetic'});await tick();d=dialogs.at(-1);find(d,'Trim').onclick();let strip=walk(d).find(n=>n.className==='trim-strip'),end=d.querySelectorAll('button').find(n=>n.attrs['aria-label']==='Trim end'),start=d.querySelectorAll('button').find(n=>n.attrs['aria-label']==='Trim start');
 strip.onpointerdown(point(end,23000));strip.onpointerup();strip.onpointerdown(point(start,5000));strip.onpointerup();assert(walk(d).some(n=>n.textContent==='00:05–00:23 · 18 sec'));find(d,'Apply').onclick();
 find(d,'Crop').onclick();find(d,'4:5').onclick();find(d,'Apply').onclick();find(d,'Trim').onclick();find(d,'Reset').onclick();find(d,'Cancel').onclick();fail=true;await find(d,'Done').onclick();assert(find(d,'Retry'));await find(d,'Retry').onclick();await pending;assert.equal(lastEdits.start_ms,5000);assert.equal(lastEdits.end_ms,23000);assert.equal(lastEdits.split,false);assert(lastEdits.crop_rect.w<1);
 pending=editor.open({files:[file()],destination:'vibe',token:'synthetic'});await tick();d=dialogs.at(-1);find(d,'Crop').onclick();find(d,'1:1').onclick();const stage=walk(d).find(n=>n.className==='media-preview-stage'),event=(id,x)=>({pointerId:id,clientX:x,clientY:200,target:stage,preventDefault(){}});stage.events.pointerdown(event(1,100));stage.events.pointerdown(event(2,150));stage.events.pointermove(event(2,200));stage.events.pointerup(event(2,200));stage.events.pointerup(event(1,100));find(d,'Apply').onclick();await find(d,'Done').onclick();await pending;assert(Math.abs(lastEdits.crop_rect.w-.25)<.0001);assert(Math.abs(lastEdits.crop_rect.h-.5)<.0001);
 pending=editor.open({files:[file('video/mp4')],destination:'plaza',token:'synthetic'});await tick();d=dialogs.at(-1);find(d,'Trim').onclick();find(d,'Reset').onclick();assert(find(d,'Apply').disabled,'Reset can show the full video but cannot bypass the approved limit');find(d,'Cancel').onclick();find(d,'Back').onclick();await pending;
 pending=editor.open({files:[file('video/mp4')],destination:'vibe',token:'synthetic'});await tick();d=dialogs.at(-1);
 const sourceVideo=walk(d).find(n=>n.tagName==='VIDEO'),previewCanvas=walk(d).find(n=>n.tagName==='CANVAS');
 sourceVideo.readyState=1;nextFrame();const beforeFrame=previewCanvas.draws||0;
 sourceVideo.readyState=2;nextFrame();assert.equal(previewCanvas.draws,beforeFrame+1,'First decoded frame repaints even while paused');
 nextFrame();assert.equal(previewCanvas.draws,beforeFrame+1,'Unchanged paused media is not repainted continuously');
 sourceVideo.currentTime=.5;nextFrame();assert.equal(previewCanvas.draws,beforeFrame+2,'Scrubbing invalidates the preview');
 find(d,'Back').onclick();await pending;
 console.log('Simple editor: Back/Done, separate Crop/Trim, Apply/Cancel/Reset, dirty exit, exact crop, combined edits, duration limit, duplicate Done and retry passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
