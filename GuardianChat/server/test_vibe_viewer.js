const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element{
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.events={};this.hidden=false;this.value='';this.textContent='';this.style={setProperty(){}};this.isConnected=true;this.classList={contains:name=>this.className?.split(' ').includes(name)};this.attrs={};this.open=false}
 append(...nodes){for(const n of nodes){this.children.push(n);n.parent=this}}
 replaceChildren(...nodes){this.children=[];this.append(...nodes)}
 replaceWith(n){if(this.parent){const i=this.parent.children.indexOf(this);this.parent.children[i]=n;n.parent=this.parent}}
 setAttribute(k,v){this.attrs[k]=v}addEventListener(k,fn){this.events[k]=fn}
 querySelector(){return this.children.find(n=>n.className!=='vibe-upload-count')||null}querySelectorAll(){return []}showModal(){this.open=true}close(){this.open=false;this.events.close?.()}
 closest(){return null}pause(){}removeAttribute(){}focus(){this.focused=true}scrollIntoView(options){this.scrolled=options}
}
const ids=[...fs.readFileSync(__dirname+'/vibe.html','utf8').matchAll(/id="([^"]+)"/g)].map(m=>m[1]),nodes=Object.fromEntries(ids.map(id=>[id,new Element()])),calls=[],header=new Element(),future=Math.floor(Date.now()/1000)+3600;
const item={id:'post1',expires:future,mime:'image/png',viewed:false},group={uid:'friend',name:'Friend',nickname:'friend',contact:true,items:[item]},feed={account:{id:'me',name:'Me'},groups:[group,{uid:'stranger',name:'Other',contact:false,items:[{...item,id:'other'}]}],preferences:{public_hours:24,private_hours:24},emoji:['❤️','🔥']};
let replyReject=false;
const context={console,URLSearchParams,Uint8Array,Blob,atob,crypto:{randomUUID:()=> 'reply-test-client'},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},location:{search:'',assign(){throw Error('Reply must not navigate away')}},localStorage:{getItem:()=>JSON.stringify({id:'me',token:'synthetic'})},document:{hidden:false,activeElement:new Element(),getElementById:id=>nodes[id],createElement:tag=>new Element(tag),querySelector:selector=>selector==='header'?header:null,addEventListener(){}},window:{addEventListener(){}},OrbitActivity:{create:()=>null},setTimeout:()=>1,clearTimeout(){},clearInterval(){},setInterval(){},fetch:async(path,options)=>{const body=options.body?JSON.parse(options.body):undefined;calls.push({path,body});if(path==='/vibe/reply'&&replyReject)return {ok:false,json:async()=>({error:'Offline'})};return {ok:true,json:async()=>path.startsWith('/vibe/feed')?structuredClone(feed):path==='/users'?{users:[]}:path.startsWith('/vibe/preview')?{data:'cHJldmlldw==',mime:'image/jpeg'}:path.startsWith('/vibe/media')?{data:'aW1hZ2U=',mime:'image/png',caption:'Moment',expires:future,server_now:future-3600,visibility:'public',cache_tag:'image-v1'}:path.startsWith('/vibe/status')?{active:true,visibility:'public',expires:future,server_now:future-3600,cache_tag:'image-v1'}:{ok:true,id:42}}}};
context.performance={now:()=>0};context.requestAnimationFrame=()=>1;context.cancelAnimationFrame=()=>{};vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/vibe-motion.js','utf8'),context);context.OrbitVibeMotion=context.window.OrbitVibeMotion;vm.runInContext(fs.readFileSync(__dirname+'/vibe-cache.js','utf8'),context);context.OrbitVibeCache=context.window.OrbitVibeCache;vm.runInContext(fs.readFileSync(__dirname+'/vibe.js','utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await tick();await tick();assert.equal(nodes.ownVibe.children.length,1);assert.equal(nodes.vibeFeed.children.length,1,'Only contact previews appear under my Vibe');assert.equal(nodes.vibeFeed.children[0].children[0].children.at(-1).className,'vibe-upload-count');assert(!calls.some(c=>c.path==='/vibe/view'),'Thumbnails do not record a view');
 const opening=nodes.vibeFeed.children[0].onclick();await tick();assert(nodes.vibeViewer.open);assert(!calls.some(c=>c.path==='/vibe/view'),'Media must display before a view is recorded');nodes.vibeMedia.children[0].events.load();await opening;assert.equal(calls.filter(c=>c.path==='/vibe/view').length,1);assert.equal(nodes.vibeReactions.children.length,2);assert.equal(nodes.vibeReply.hidden,false);
 nodes.vibeReplyText.value='Nice moment';await nodes.vibeReply.onsubmit({preventDefault(){}});assert.equal(calls.at(-1).path,'/vibe/reply');assert.equal(calls.at(-1).body.text,'Nice moment');assert(nodes.vibeViewer.open,'Reply stays in viewer');assert.equal(nodes.vibeReplyText.value,'');
 replyReject=true;nodes.vibeReplyText.value='Retain me';await nodes.vibeReply.onsubmit({preventDefault(){}});const first=calls.at(-1).body.client_id;assert.equal(nodes.vibeReplyText.value,'Retain me');replyReject=false;await nodes.vibeReply.onsubmit({preventDefault(){}});assert.equal(calls.at(-1).body.client_id,first,'Network retry keeps the same identity');
 assert(context.window.OrbitVibe.back());assert.equal(nodes.vibeViewer.open,false);assert(!context.window.OrbitVibe.back());
 // A completed editor job must reveal the actual composer, preserve its draft,
 // and never publish as a side effect of Done.
 nodes.vibeCaption.value='Keep my caption';nodes.vibeAudience.hidden=false;
 context.OrbitMediaEditor={open:async()=>[{media_id:'private-render',mime:'video/mp4',poster:'cG9zdGVy',duration_ms:60000}]};
 await vm.runInContext("editVibeFiles([{type:'video/mp4'}])",context);
 assert(nodes.vibeCompose.open);assert(nodes.vibeCompose.focused);assert.equal(nodes.vibeCompose.scrolled.block,'start');assert.equal(nodes.vibeCaption.value,'Keep my caption');assert.equal(nodes.vibeAudience.hidden,false);assert.equal(nodes.vibeFiles.required,false);assert.equal(nodes.vibePendingPreview.children.length,1);
 assert(!calls.some(c=>c.path==='/vibe/publish'),'Done must not publish');
 const previous=nodes.vibePendingPreview.children[0];context.OrbitMediaEditor.open=async()=>null;
 await vm.runInContext("editVibeFiles([{type:'image/png'}])",context);assert.equal(nodes.vibePendingPreview.children[0],previous,'Cancel keeps the previously prepared draft');
 console.log('Compact contact-only previews, display-before-view receipt, inline reply/retry and viewer Back passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
