const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {Element,walk,content}=require('./browser-test-dom.cjs');
let now=0,stops=0,clips=[],timers=new Map(),timerID=0,revoked=[],recorders=[];
class Recorder{static isTypeSupported(x){return x.startsWith('video/webm')}constructor(stream,options){this.mimeType=options.mimeType;this.state='inactive';recorders.push(this)}start(){this.state='recording'}stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['synthetic recording'],{type:this.mimeType})});this.onstop?.()}}
const context={document:{createElement:t=>new Element(t)},navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop:()=>stops++}]})}},Blob,MediaRecorder:Recorder,Date:{now:()=>now},URL:{createObjectURL:()=>`blob:test-${clips.length}`,revokeObjectURL:x=>revoked.push(x)},setTimeout:(fn,ms)=>{timers.set(++timerID,{fn,ms});return timerID},clearTimeout:id=>timers.delete(id)};context.window=context;vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/evidence-camera.js','utf8'),context);
const event=y=>({clientY:y,pointerId:1,preventDefault(){}}),find=(root,text)=>walk(root).find(n=>n.tagName==='BUTTON'&&n.textContent===text);
(async()=>{
 const root=new Element(),camera=context.OrbitEvidenceCamera.mount({container:root,onCapture:b=>{if(b)clips.push(b)}});
 assert(!walk(root).some(n=>n.tagName==='INPUT'&&n.type==='file'),'No gallery/file picker');
 await walk(root).find(n=>n.attributes['aria-label']==='Capture result evidence with camera').onclick();const shutter=walk(root).find(n=>n.attributes['aria-label']?.startsWith('Camera shutter'));
 shutter.onpointerdown(event(100));shutter.onpointerup(event(100));assert.equal(clips[0].type,'image/jpeg');assert(stops>0);assert(walk(root).some(n=>n.tagName==='IMG'&&!n.hidden),'Unsent photo preview is visible only in this capture widget');
 await walk(root).find(n=>n.attributes['aria-label']==='Capture result evidence with camera').onclick();shutter.onpointerdown(event(120));const hold=[...timers.values()].find(t=>t.ms===350);now+=350;hold.fn();assert.equal(recorders.at(-1).state,'recording');
 shutter.onpointermove(event(20));now+=12000;shutter.onpointerup(event(20));assert.equal(recorders.at(-1).state,'recording','Swipe up locks recording after release');
 find(root,'Stop recording').onclick();assert(clips.at(-1).type.startsWith('video/'));assert.match(content(root),/Captured privately/);
 await walk(root).find(n=>n.attributes['aria-label']==='Capture result evidence with camera').onclick();find(root,'‹ Back to conversation').onclick();assert(!camera.active(),'Back stops the camera without uploading');camera.destroy();assert(!camera.active());assert(revoked.length>=2);
 const videoOnly=context.OrbitEvidenceCamera.mount({container:new Element(),videoRequired:true,onCapture:b=>{if(b)clips.push(b)}});assert(!find(videoOnly.root,'Photo'));assert(!find(videoOnly.root,'Video'));
 await walk(videoOnly.root).find(n=>n.attributes['aria-label']==='Capture result evidence with camera').onclick();const videoShutter=walk(videoOnly.root).find(n=>n.attributes['aria-label']?.startsWith('Camera shutter'));videoShutter.onpointerdown(event(100));videoShutter.onpointerup(event(100));assert.equal(recorders.at(-1).state,'recording','Video mode supports tap to start');now+=12000;find(videoOnly.root,'Stop recording').onclick();videoOnly.destroy();
 const vibe=context.OrbitEvidenceCamera.mount({container:new Element(),purpose:'vibe',maxSeconds:20,includeAudio:true,videoRequired:true,onCapture:b=>{if(b)clips.push(b)}});
 await walk(vibe.root).find(n=>n.attributes['aria-label']==='Open Vibe camera').onclick();const vibeShutter=walk(vibe.root).find(n=>n.attributes['aria-label']?.startsWith('Camera shutter'));vibeShutter.onclick();assert([...timers.values()].some(t=>t.ms===20000));assert(!content(vibe.root).includes('Video proof'));now+=20000;[...timers.values()].find(t=>t.ms===20000).fn();assert.match(content(vibe.root),/Review before publishing/);vibe.destroy();
 console.log('Camera evidence defaults, Vibe 20-second capture, Back, swipe lock and media cleanup passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
