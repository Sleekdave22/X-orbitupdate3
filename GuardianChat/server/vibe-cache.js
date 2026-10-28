/* Public Vibe bytes are reused; access is re-authorized on every opening. */
((root)=>{'use strict';
function persistentStore(indexedDB,limit=96*1024*1024){
 let opening;
 function db(){return opening||(opening=new Promise((resolve,reject)=>{const r=indexedDB.open('xorbit-public-vibe-cache',1);r.onupgradeneeded=()=>r.result.createObjectStore('media',{keyPath:'key'});r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);r.onblocked=()=>reject(Error('Cache unavailable'))}))}
 async function transaction(mode,work){const d=await db();return new Promise((resolve,reject)=>{const t=d.transaction('media',mode),store=t.objectStore('media');let value;work(store,v=>value=v);t.oncomplete=()=>resolve(value);t.onerror=()=>reject(t.error);t.onabort=()=>reject(t.error)})}
 return {
  get:key=>transaction('readonly',(s,done)=>{s.get(key).onsuccess=e=>done(e.target.result)}),
  delete:key=>transaction('readwrite',s=>s.delete(key)),
  put:entry=>transaction('readwrite',s=>{s.put(entry);s.getAll().onsuccess=e=>{const entries=e.target.result.filter(x=>{if(x.expiresAt<=Date.now()){s.delete(x.key);return false}return true}).sort((a,b)=>a.touched-b.touched);let size=entries.reduce((n,x)=>n+x.blob.size,0);for(const x of entries){if(size<=limit)break;s.delete(x.key);size-=x.blob.size}}}),
  prune:owner=>transaction('readwrite',s=>{s.getAll().onsuccess=e=>{for(const x of e.target.result)if(x.owner!==owner||x.expiresAt<=Date.now())s.delete(x.key)}})
 };
}
function create({owner,api,store,now=Date.now,maxBytes=64*1024*1024,decode=data=>new Blob([Uint8Array.from(atob(data.data),c=>c.charCodeAt(0))],{type:data.mime})}){
 const memory=new Map(),pending=new Map();let closed=false;
 const quietly=async(fn)=>{try{return await fn()}catch(_){return undefined}};
 const initial=store?quietly(()=>store.prune(owner)):Promise.resolve();
 function remember(entry){memory.delete(entry.key);memory.set(entry.key,entry);let size=[...memory.values()].reduce((n,x)=>n+x.blob.size,0);for(const [key,x] of memory){if(size<=maxBytes)break;memory.delete(key);size-=x.blob.size}}
 async function drop(id){const key=owner+'/'+id;memory.delete(key);if(store)await quietly(()=>store.delete(key))}
 async function load(id){
  const key=owner+'/'+id;await initial;
  try{
   const status=await api('/vibe/status?id='+encodeURIComponent(id));
   if(closed)throw Error('Vibe viewer closed');
   if(status.visibility!=='public')throw Error('Private Vibes stay in the protected viewer');
   if(!status.active||!status.cache_tag||status.expires<=status.server_now)throw Error('This Vibe has expired');
   let entry=memory.get(key)||(store?await quietly(()=>store.get(key)):null),fresh=false;
   if(entry&&(entry.owner!==owner||entry.key!==key||entry.expiresAt<=now()||entry.tag!==status.cache_tag)){await drop(id);entry=null}
   if(!entry){
    const data=await api('/vibe/media?id='+encodeURIComponent(id));
    if(closed)throw Error('Vibe viewer closed');
    if(data.visibility!=='public'||data.expires<=data.server_now)throw Error('This Vibe is unavailable');
    const blob=decode(data),metadata={...data};delete metadata.data;
    entry={key,owner,tag:data.cache_tag,blob,metadata,expiresAt:now()+Math.max(0,data.expires-data.server_now)*1000,touched:now()};fresh=true;
   }
   if(closed)throw Error('Vibe viewer closed');
   entry.touched=now();remember(entry);if(store&&fresh)await quietly(()=>store.put(entry));
   // Counters and relationships stay live, even when bytes are reused.
   return {...entry.metadata,...(entry.tag===status.cache_tag?status:{}),blob:entry.blob};
  }catch(e){await drop(id);throw e}
 }
 return {get(id){if(closed)return Promise.reject(Error('Vibe viewer closed'));if(!pending.has(id)){const p=load(id).finally(()=>pending.delete(id));pending.set(id,p)}return pending.get(id)},drop,destroy(){closed=true;memory.clear();pending.clear()}};
}
const exported={create,persistentStore};if(typeof module!=='undefined'&&module.exports)module.exports=exported;else root.OrbitVibeCache=exported;
})(typeof window==='undefined'?globalThis:window);
