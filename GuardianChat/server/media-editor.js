/* Shared Crop/Trim editor. Done prepares media; the composer publishes it. */
(()=>{
'use strict';
let activeBack=null;
const drafts=new WeakMap(),full=()=>({x:0,y:0,w:1,h:1}),copy=x=>JSON.parse(JSON.stringify(x));
const sameRect=(a,b)=>['x','y','w','h'].every(k=>Math.abs(a[k]-b[k])<1e-9);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),el=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n};
const icons={
 back:'<path d="m15 5-7 7 7 7"/>',
 crop:'<path d="M8 3v13a1 1 0 0 0 1 1h12M3 7h12a1 1 0 0 1 1 1v13"/>',
 trim:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8 8 13 13M8 16l13-13"/>',
 play:'<path d="m8 4 12 8-12 8Z"/>'
};
const svg=name=>'<svg aria-hidden="true" width="25" height="25" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+icons[name]+'</svg>';
function ranges(duration,start,end,split,maximum=60000){
 if(!Number.isFinite(duration)||start<0||end>duration||end-start<100)throw Error('Choose a section of at least 0.1 seconds');
 if(!split&&end-start>maximum)throw Error('Trim this section to '+maximum/1000+' seconds');
 const parts=[];for(let at=start;at<end;at=split?at+60000:end)parts.push([at,split?Math.min(end,at+60000):end]);return parts;
}
function rectangle(frame,image){
 const x=clamp((frame.x-image.x)/image.w,0,1),y=clamp((frame.y-image.y)/image.h,0,1);
 return {x,y,w:clamp((frame.x+frame.w-image.x)/image.w,0,1)-x,h:clamp((frame.y+frame.h-image.y)/image.h,0,1)-y};
}
function time(ms){const hundredths=Math.round(ms/10),seconds=Math.floor(hundredths/100),fraction=hundredths%100;return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')+(fraction?'.'+String(fraction).padStart(2,'0'):'')}
async function open({files,destination,token}){
 if(!files?.length)return null;
 if(!['vibe','plaza'].includes(destination))throw Error('Choose Vibe or Plaza');
 if(destination==='plaza'&&files.length>6)throw Error('Choose up to six photos/videos');
 const api=async(path,body)=>{
  const r=await fetch(path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
  const data=await r.json();if(!r.ok)throw Error(data.error||'Please check your connection and retry.');return data;
 };
 if(activeBack)throw Error('Finish the current edit first.');
 const policy=await api('/media-editor/policy'),maximum=(destination==='plaza'?policy.plaza_seconds:60)*1000;
 const states=[...files].map(file=>{
  if(file.size>policy.max_source_bytes)throw Error('Choose files up to 20 MB each');
  let s=drafts.get(file);
  if(!s||s.destination!==destination){s={file,destination,client:crypto.randomUUID(),rect:full(),ratio:'Original',start:0,end:0,asset:null,cached:null};drafts.set(file,s)}
  return s;
 });
 const baselines=states.map(s=>({rect:copy(s.rect),start:s.start,end:s.file.type.startsWith('video/')?(s.end||null):0}));
 const dialog=el('dialog');dialog.className='orbit-media-editor';dialog.setAttribute('aria-label','Media editor');
 const header=el('header'),heading=el('span'),main=el('section'),stage=el('div'),canvas=el('canvas'),tools=el('section'),notice=el('p'),progress=el('progress'),footer=el('footer');
 main.className='media-editor-main';stage.className='media-preview-stage';tools.className='media-editor-tools';canvas.setAttribute('aria-label','Media preview');notice.setAttribute('role','status');progress.max=100;progress.hidden=true;stage.append(canvas);main.append(stage);dialog.append(header,notice,progress,main,tools,footer);
 const button=(text,fn,icon)=>{const b=el('button');b.type='button';if(icon){b.innerHTML=svg(icon);b.append(el('span',text))}else b.textContent=text;if(text==='Apply')b.className='media-editor-apply';b.onclick=fn;return b};
 let at=0,mode='main',busy=false,closed=false,media=null,url=null,animation=null,job=null,xhr=null,generation=0,crop=null,trim=null,resolveResult;
 const pointers=new Map(),state=()=>states[at],video=()=>state().file.type.startsWith('video/');
 const result=new Promise(resolve=>resolveResult=resolve),back=button('Back',leave,'back'),done=button('Done',prepare);
 back.className='media-editor-back';back.setAttribute('aria-label','Back from media editor');done.className='media-editor-done';header.append(back,heading,done);document.body.append(dialog);dialog.showModal();
 dialog.addEventListener('cancel',e=>{e.preventDefault();leave()});activeBack=leave;
 const status=text=>notice.textContent=text,settings=s=>({crop_rect:s.rect,rotation:0,crop:'original',fit:'fit',start_ms:s.start,end_ms:s.end,split:destination==='vibe'&&s.end-s.start>60000});
 function dirty(){
  return states.some((s,i)=>!sameRect(s.rect,baselines[i].rect)||s.start!==baselines[i].start||baselines[i].end!==null&&s.end!==baselines[i].end)
   ||mode==='confirm'||mode==='crop'&&!sameRect(rectangle(crop.frame,crop.image),state().rect)||mode==='trim'&&(trim.start!==state().start||trim.end!==state().end);
 }
 function leave(){
  if(closed||mode==='confirm')return;if(!dirty()){close();return}
  const previous=mode;mode='confirm';pointers.clear();done.hidden=true;
  tools.replaceChildren(el('p','Discard these edits?'),button('Keep editing',()=>{mode=previous;showTools()}),button('Discard changes',()=>{states.forEach((s,i)=>{s.rect=copy(baselines[i].rect);s.start=baselines[i].start;s.end=baselines[i].end||0});close()}));footer.replaceChildren();
 }
 function close(value=null){
  if(closed)return;closed=true;generation++;xhr?.abort();if(job)api('/media-editor/cancel',{id:job}).catch(()=>{});
  release();dialog.close();dialog.remove();window.removeEventListener('pagehide',onHide);window.removeEventListener('beforeunload',beforeLeave);if(activeBack===leave)activeBack=null;resolveResult(value);
 }
 const onHide=()=>close(),beforeLeave=e=>{if(!closed&&dirty()){e.preventDefault();e.returnValue=''}};window.addEventListener('pagehide',onHide,{once:true});window.addEventListener('beforeunload',beforeLeave);
 function release(){
  if(animation)cancelAnimationFrame(animation);animation=null;
  if(media){media.onloadedmetadata=media.onloadeddata=media.onerror=null;media.pause?.();media.removeAttribute('src');if(media.tagName==='VIDEO')media.load();media.remove();media=null}
  if(url){URL.revokeObjectURL(url);url=null}
 }
 function setBusy(value){busy=value;done.disabled=value;done.textContent=value?'Preparing…':'Done';progress.hidden=!value;tools.querySelectorAll('button,input').forEach(n=>n.disabled=value)}
 function initialise(duration){
  if(!Number.isFinite(duration)||duration<100){status('This video cannot be previewed here. Choose another video.');return}
  const s=state();s.duration=duration;if(!s.end)s.end=destination==='plaza'?Math.min(duration,maximum):duration;if(baselines[at].end===null)baselines[at].end=s.end;done.disabled=false;showTools();
 }
 function source(){
  release();generation++;mode='main';crop=trim=null;const s=state();heading.textContent=states.length>1?(at+1)+' / '+states.length:'Edit media';
  url=URL.createObjectURL(s.file);media=el(video()?'video':'img');media.hidden=true;main.append(media);done.disabled=true;
  if(video()){
   media.playsInline=true;media.preload='auto';const mine=generation;media.onloadedmetadata=async()=>{
    if(Number.isFinite(media.duration)&&media.duration>0){initialise(Math.round(media.duration*1000));return}
    status('Preparing preview…');progress.hidden=false;
    try{await upload(s);if(!closed&&mine===generation)initialise(s.info.duration_ms)}catch(e){if(!closed)status(e.message)}finally{if(!closed&&!busy)progress.hidden=true}
   };
   media.onerror=()=>status('This video cannot be previewed here. Choose another video.');
   media.src=url;media.load();if(s.duration)initialise(s.duration);
  }else{media.onload=()=>{done.disabled=false;showTools()};media.onerror=()=>status('This photo cannot be opened. Choose another photo.');media.src=url}
  let lastPaint='';const draw=()=>{if(closed||!media)return;const signature=JSON.stringify([mode,stage.clientWidth,stage.clientHeight,dimensions(),media.readyState,media.complete,state().rect,crop,media.currentTime,pointers.size]);if(signature!==lastPaint){paint();lastPaint=signature}animation=requestAnimationFrame(draw)};animation=requestAnimationFrame(draw);
  status('Originals stay unchanged. Done returns to your composer.');showTools();
 }
 function bounds(){
  const w=Math.max(1,stage.clientWidth),h=Math.max(1,stage.clientHeight),dpr=Math.min(2,window.devicePixelRatio||1);
  if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
  const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return {w,h,ctx};
 }
 function dimensions(){return [media?.videoWidth||media?.naturalWidth||0,media?.videoHeight||media?.naturalHeight||0]}
 function cropMapping(rect){
  const [sw,sh]=dimensions(),{w,h}=bounds(),scale=Math.min(w/sw,h/sh)*.86;
  const image={x:(w-sw*scale)/2,y:(h-sh*scale)/2,w:sw*scale,h:sh*scale};
  return {image,frame:{x:image.x+rect.x*image.w,y:image.y+rect.y*image.h,w:rect.w*image.w,h:rect.h*image.h},viewW:w,viewH:h};
 }
 function paint(){
  const [sw,sh]=dimensions();if(!sw||!sh||video()&&media.readyState<2)return;const {w,h,ctx}=bounds();ctx.fillStyle='#090b20';ctx.fillRect(0,0,w,h);
  if(mode==='crop'&&crop){
   if(crop.viewW!==w||crop.viewH!==h)Object.assign(crop,cropMapping(rectangle(crop.frame,crop.image)));
   const i=crop.image,f=crop.frame;ctx.drawImage(media,i.x,i.y,i.w,i.h);ctx.fillStyle='#0009';ctx.beginPath();ctx.rect(0,0,w,h);ctx.rect(f.x,f.y,f.w,f.h);ctx.fill('evenodd');ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.strokeRect(f.x,f.y,f.w,f.h);
   if(pointers.size){ctx.strokeStyle='#ffffff88';ctx.lineWidth=.7;for(const k of [1,2]){ctx.beginPath();ctx.moveTo(f.x+f.w*k/3,f.y);ctx.lineTo(f.x+f.w*k/3,f.y+f.h);ctx.moveTo(f.x,f.y+f.h*k/3);ctx.lineTo(f.x+f.w,f.y+f.h*k/3);ctx.stroke()}}
   placeHandles();return;
  }
  const r=state().rect,sx=Math.round(r.x*sw),sy=Math.round(r.y*sh),cw=Math.max(1,Math.round((r.x+r.w)*sw)-sx),ch=Math.max(1,Math.round((r.y+r.h)*sh)-sy),scale=Math.min(w/cw,h/ch);
  ctx.drawImage(media,sx,sy,cw,ch,(w-cw*scale)/2,(h-ch*scale)/2,cw*scale,ch*scale);
  if(video()){
   const start=mode==='trim'?trim.start:state().start,end=mode==='trim'?trim.end:state().end;
   if(!media.paused&&(media.currentTime*1000<start||media.currentTime*1000>=end)){media.pause();media.currentTime=start/1000}
   const head=tools.querySelector('.trim-playhead');if(head)head.style.left=clamp(media.currentTime*1000/state().duration*100,0,100)+'%';
  }
 }
 function play(){
  const start=mode==='trim'?trim.start:state().start,end=mode==='trim'?trim.end:state().end;
  if(media.paused){if(media.currentTime*1000<start||media.currentTime*1000>=end)media.currentTime=start/1000;media.play().catch(()=>status('Tap Play again to preview.'))}else media.pause();
 }
 function showTools(){
  if(closed)return;heading.textContent=mode==='crop'?'Crop':mode==='trim'?'Trim':states.length>1?(at+1)+' / '+states.length:'Edit media';tools.replaceChildren();footer.replaceChildren();done.hidden=mode!=='main';stage.querySelectorAll('.crop-handle').forEach(n=>n.remove());
  if(mode==='crop'){cropTools();return}if(mode==='trim'){trimTools();return}
  if(mode==='confirm')return;
  status('Done applies your edits and returns to the composer.');
  tools.append(button('Crop',beginCrop,'crop'));
  if(video()){
   tools.append(button('Trim',beginTrim,'trim'),button('Play / pause',play,'play'));
   if(state().end)footer.append(el('small',time(state().start)+'–'+time(state().end)+' · '+Number(((state().end-state().start)/1000).toFixed(2))+' sec'));
  }
  if(states.length>1){if(at)footer.append(button('Previous',()=>{at--;source()}));footer.append(el('small',(at+1)+' of '+states.length));if(at+1<states.length)footer.append(button('Next',()=>{at++;source()}))}
 }
 function beginCrop(){
  if(busy)return;media.pause?.();const [sw,sh]=dimensions();if(!sw||!sh)return;
  crop={...cropMapping(state().rect),ratio:state().ratio,changed:false};mode='crop';status('Drag the picture to position it. Use the handles or pinch to zoom.');showTools();
 }
 function cropTools(){
  const ratios=el('div');ratios.className='crop-ratios';
  for(const label of ['Free','Original','1:1','4:5','9:16']){const b=button(label,()=>{crop.ratio=label;ratioFrame();crop.changed=true;showTools()});b.setAttribute('aria-pressed',String(crop.ratio===label));ratios.append(b)}
  tools.append(ratios);
  footer.append(button('Cancel',()=>{mode='main';showTools()}),button('Reset',()=>{crop={...cropMapping(full()),ratio:'Original',changed:true};showTools()}),button('Apply',()=>{state().rect=rectangle(crop.frame,crop.image);state().ratio=crop.ratio;mode='main';showTools()}));
  for(const name of ['nw','n','ne','e','se','s','sw','w']){
   const handle=button('',()=>{});handle.className='crop-handle';handle.dataset.handle=name;handle.setAttribute('aria-label','Crop '+({nw:'top left',n:'top',ne:'top right',e:'right',se:'bottom right',s:'bottom',sw:'bottom left',w:'left'})[name]);
   handle.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();resizeFrame(name,e.key==='ArrowRight'?4:e.key==='ArrowLeft'?-4:0,e.key==='ArrowDown'?4:e.key==='ArrowUp'?-4:0);crop.changed=true};
   stage.append(handle);
  }
 }
 function aspect(){const [w,h]=dimensions();return crop.ratio==='Free'?null:crop.ratio==='Original'?w/h:crop.ratio==='1:1'?1:crop.ratio==='4:5'?4/5:9/16}
 function containImage(){const f=crop.frame,i=crop.image;i.x=clamp(i.x,f.x+f.w-i.w,f.x);i.y=clamp(i.y,f.y+f.h-i.h,f.y)}
 function ratioFrame(){
  const f=crop.frame,i=crop.image,a=aspect();if(!a)return;const cx=f.x+f.w/2,cy=f.y+f.h/2,{w:vw,h:vh}=bounds();
  let w=Math.min(f.w,i.w,vw*.9),h=w/a;if(h>Math.min(i.h,vh*.9)){h=Math.min(i.h,vh*.9);w=h*a}
  f.w=w;f.h=h;f.x=clamp(cx-w/2,Math.max(0,i.x),Math.min(vw,i.x+i.w)-w);f.y=clamp(cy-h/2,Math.max(0,i.y),Math.min(vh,i.y+i.h)-h);
 }
 function placeHandles(){
  const f=crop.frame;for(const b of stage.querySelectorAll('.crop-handle')){const k=b.dataset.handle;b.style.left=(k.includes('w')?f.x:k.includes('e')?f.x+f.w:f.x+f.w/2)+'px';b.style.top=(k.includes('n')?f.y:k.includes('s')?f.y+f.h:f.y+f.h/2)+'px'}
 }
 function resizeFrame(name,dx,dy){
  const f=crop.frame,i=crop.image,old=copy(f),{w:vw,h:vh}=bounds(),minX=Math.max(0,i.x),minY=Math.max(0,i.y),maxX=Math.min(vw,i.x+i.w),maxY=Math.min(vh,i.y+i.h);
  let left=f.x,right=f.x+f.w,top=f.y,bottom=f.y+f.h;
  if(name.includes('w'))left=clamp(left+dx,minX,right-28);if(name.includes('e'))right=clamp(right+dx,left+28,maxX);
  if(name.includes('n'))top=clamp(top+dy,minY,bottom-28);if(name.includes('s'))bottom=clamp(bottom+dy,top+28,maxY);
  const a=aspect();
  if(a){let w=right-left,h=bottom-top;if(name==='n'||name==='s')w=h*a;else h=w/a;if(w>maxX-minX||h>maxY-minY)return;left=name.includes('w')?old.x+old.w-w:left;top=name.includes('n')?old.y+old.h-h:top;left=clamp(left,minX,maxX-w);top=clamp(top,minY,maxY-h);right=left+w;bottom=top+h}
  crop.frame={x:left,y:top,w:right-left,h:bottom-top};
 }
 stage.addEventListener('pointerdown',e=>{
  if(mode!=='crop'||busy)return;e.preventDefault();stage.setPointerCapture(e.pointerId);pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  crop.drag={handle:e.target.dataset?.handle||null,x:e.clientX,y:e.clientY};
  if(pointers.size===2){const [a,b]=[...pointers.values()];crop.pinch={distance:Math.hypot(a.x-b.x,a.y-b.y),image:copy(crop.image)}}
 });
 stage.addEventListener('pointermove',e=>{
  if(mode!=='crop'||!pointers.has(e.pointerId))return;e.preventDefault();pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});
  if(pointers.size===2&&crop.pinch){const [a,b]=[...pointers.values()],f=crop.frame,old=crop.pinch.image,factor=clamp(Math.hypot(a.x-b.x,a.y-b.y)/Math.max(1,crop.pinch.distance),Math.max(f.w/old.w,f.h/old.h),10),cx=f.x+f.w/2,cy=f.y+f.h/2;crop.image={w:old.w*factor,h:old.h*factor,x:cx-(cx-old.x)*factor,y:cy-(cy-old.y)*factor};containImage()}
  else{const d=crop.drag,dx=e.clientX-d.x,dy=e.clientY-d.y;if(d.handle)resizeFrame(d.handle,dx,dy);else{crop.image.x+=dx;crop.image.y+=dy;containImage()}d.x=e.clientX;d.y=e.clientY}
  crop.changed=true;
 });
 for(const name of ['pointerup','pointercancel'])stage.addEventListener(name,e=>{pointers.delete(e.pointerId);if(pointers.size<2&&crop){crop.pinch=null;const remaining=[...pointers.values()][0];if(remaining)crop.drag={handle:null,...remaining}}});
 function beginTrim(){if(busy||!state().duration)return;media.pause();trim={start:state().start,end:state().end};mode='trim';status(destination==='vibe'?'60 sec per Vibe. Longer selections split automatically.':'Maximum '+maximum/1000+' sec.');showTools()}
 function trimTools(){
  const summary=el('output'),strip=el('div'),thumbs=el('div'),before=el('span'),after=el('span'),start=button('',()=>{}),end=button('',()=>{}),playhead=el('i');
  strip.className='trim-strip';thumbs.className='trim-thumbnails';before.className=after.className='trim-excluded';start.className=end.className='trim-handle';start.setAttribute('aria-label','Trim start');end.setAttribute('aria-label','Trim end');playhead.className='trim-playhead';strip.append(thumbs,before,after,start,end,playhead);
  const apply=button('Apply',()=>{state().start=trim.start;state().end=trim.end;mode='main';showTools()});
  const paintTrim=()=>{
   const duration=state().duration,left=trim.start/duration*100,right=trim.end/duration*100;summary.textContent=time(trim.start)+'–'+time(trim.end)+' · '+Number(((trim.end-trim.start)/1000).toFixed(2))+' sec';before.style.cssText='left:0;width:'+left+'%';after.style.cssText='right:0;width:'+(100-right)+'%';start.style.left=left+'%';end.style.left=right+'%';apply.disabled=trim.end-trim.start<100||destination==='plaza'&&trim.end-trim.start>maximum;
  };
  let dragging=null;
  const move=e=>{
   if(!dragging)return;e.preventDefault();const box=strip.getBoundingClientRect(),value=Math.round(clamp((e.clientX-box.left)/box.width,0,1)*state().duration/10)*10;
   if(dragging==='start')trim.start=clamp(value,0,trim.end-100);else if(dragging==='end')trim.end=clamp(value,trim.start+100,state().duration);
   media.currentTime=(dragging==='start'?trim.start:dragging==='end'?Math.max(trim.start,trim.end-20):value)/1000;paintTrim();
  };
  strip.onpointerdown=e=>{dragging=e.target===start?'start':e.target===end?'end':'scrub';strip.setPointerCapture(e.pointerId);move(e)};
  strip.onpointermove=move;strip.onpointerup=strip.onpointercancel=()=>dragging=null;
  for(const [handle,key] of [[start,'start'],[end,'end']])handle.onkeydown=e=>{
   if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();trim[key]=clamp(trim[key]+(e.key==='ArrowRight'?100:-100),key==='start'?0:trim.start+100,key==='start'?trim.end-100:state().duration);media.currentTime=trim[key]/1000;paintTrim();
  };
  tools.append(summary,strip,button('Play / pause',play,'play'));
  footer.append(button('Cancel',()=>{mode='main';showTools()}),button('Reset',()=>{trim={start:0,end:state().duration};paintTrim()}),apply);paintTrim();thumbnails(thumbs);
 }
 async function thumbnails(target){
  const mine=generation,clip=el('video');clip.muted=true;clip.playsInline=true;clip.preload='auto';clip.hidden=true;main.append(clip);
  try{
   await new Promise((resolve,reject)=>{clip.onloadeddata=resolve;clip.onerror=reject;clip.src=url;clip.load()});
   for(let i=0;i<8;i++){
    if(closed||mine!==generation||mode!=='trim'||!target.isConnected)break;
    await new Promise(resolve=>{clip.onseeked=resolve;clip.currentTime=Math.min((i+.5)*state().duration/8000,Math.max(0,clip.duration-.05));setTimeout(resolve,1200)});
    if(!target.isConnected)break;const c=el('canvas');c.width=80;c.height=60;const scale=Math.max(80/clip.videoWidth,60/clip.videoHeight);c.getContext('2d').drawImage(clip,(80-clip.videoWidth*scale)/2,(60-clip.videoHeight*scale)/2,clip.videoWidth*scale,clip.videoHeight*scale);target.append(c);
   }
  }catch(_){}finally{clip.onloadeddata=clip.onseeked=clip.onerror=null;clip.pause();clip.removeAttribute('src');clip.load();clip.remove()}
 }
 async function upload(s){
  if(s.asset){if(s.info.duration_ms)s.end=Math.min(s.end,s.info.duration_ms);return}status('Preparing… Uploading original.');progress.value=0;
  const encoded=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(Error('This file could not be read.'));r.readAsDataURL(s.file)});
  if(closed)throw Error('Cancelled');
  const r=await new Promise((resolve,reject)=>{
   xhr=new XMLHttpRequest();xhr.open('POST','/media-editor/upload');xhr.setRequestHeader('Authorization','Bearer '+token);xhr.setRequestHeader('Content-Type','application/json');
   xhr.upload.onprogress=e=>{if(e.lengthComputable)progress.value=e.loaded/e.total*100};xhr.onabort=()=>reject(Error('Cancelled'));xhr.onerror=()=>reject(Error('Connection lost. Your edits are kept; retry.'));
   xhr.onload=()=>{try{const value=JSON.parse(xhr.responseText);xhr.status>=200&&xhr.status<300?resolve(value):reject(Error(value.error||'Please retry.'))}catch(e){reject(e)}};
   xhr.send(JSON.stringify({destination,client_id:s.client,media:encoded,mime:s.file.type}));
  });
  xhr=null;s.asset=r.id;s.info=r.info;if(s.info.duration_ms)s.end=Math.min(s.end,s.info.duration_ms);
 }
 async function prepare(){
  if(busy||mode!=='main')return;media.pause?.();setBusy(true);const outputs=[];
  try{
   for(const s of states){
    await upload(s);const edits=settings(s);if(s.info.duration_ms)ranges(s.info.duration_ms,s.start,s.end,edits.split,maximum);const fingerprint=JSON.stringify(edits);
    if(!s.cached||s.cached.fingerprint!==fingerprint){
     status('Preparing… Your edits are kept while processing.');progress.removeAttribute('value');
     if(s.processKey?.fingerprint!==fingerprint)s.processKey={fingerprint,id:crypto.randomUUID()};
     const queued=await api('/media-editor/process',{asset:s.asset,client_id:s.processKey.id,edits});job=queued.id;let response;
     do{if(closed)return;response=await api('/media-editor/job?id='+job);if(['failed','cancelled'].includes(response.state))throw Error(response.error||'Please retry.');if(response.state!=='ready')await new Promise(resolve=>setTimeout(resolve,600))}while(response.state!=='ready');
     job=null;s.cached={fingerprint,parts:response.parts};
    }
    outputs.push(...s.cached.parts);
   }
   close(outputs.map(p=>({media_id:p.id,mime:p.mime,poster:p.poster,duration_ms:p.duration_ms,start_ms:p.start_ms,end_ms:p.end_ms})));
  }catch(e){
   if(!closed){status(e.message);footer.replaceChildren(button('Retry',prepare));if(job){api('/media-editor/cancel',{id:job}).catch(()=>{});job=null;states.forEach(s=>s.processKey=null)}}
  }finally{if(!closed)setBusy(false)}
 }
 source();return result;
}
window.OrbitMediaEditor={open,ranges,rectangle,time,back(){if(!activeBack)return false;activeBack();return true}};
})();