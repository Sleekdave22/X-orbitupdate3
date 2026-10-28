const assert=require('node:assert/strict'),{create}=require('./vibe-cache.js');
let time=0,tag='a',allowed=true,visibility='public',loads=0,statuses=0,views=4;
const entries=new Map(),store={async prune(owner){for(const [key,e] of entries)if(e.owner!==owner||e.expiresAt<=time)entries.delete(key)},async get(k){return entries.get(k)},async put(e){entries.set(e.key,e)},async delete(k){entries.delete(k)}};
async function api(path){if(path.startsWith('/vibe/status')){statuses++;if(!allowed)throw Error('Unavailable');return {active:true,visibility,cache_tag:tag,server_now:time/1000,expires:3600,view_count:views,source:null}}loads++;return {visibility:'public',cache_tag:tag,server_now:time/1000,expires:3600,mime:'video/mp4',data:'eHg=',caption:'clip',view_count:1}}
const make=(extra={})=>create({owner:'one',api,store,now:()=>time,...extra});
(async()=>{
 let c=make();let [a,b]=await Promise.all([c.get('first'),c.get('first')]);assert.equal(loads,1);assert.equal(statuses,1);assert.equal(a.blob,b.blob);assert.equal(a.blob.size,2);
 views=7;assert.equal((await c.get('first')).view_count,7);assert.equal(loads,1,'Back/forward reuse bytes but refresh live metadata');
 c.destroy();c=make();await c.get('first');assert.equal(loads,1,'Reopening the page reuses persisted bytes');
 assert(!('data' in entries.get('one/first').metadata),'Base64 is not retained beside the Blob');
 tag='b';await c.get('first');assert.equal(loads,2,'Changed content/source reloads');
 allowed=false;await assert.rejects(c.get('first'),/Unavailable/);assert(!entries.has('one/first'),'Revocation purges the local copy');
 allowed=true;await c.get('first');assert.equal(loads,3);time=3601000;await assert.rejects(c.get('first'),/expired/);assert(!entries.has('one/first'));
 time=0;visibility='private';const n=loads;await assert.rejects(c.get('private'),/protected/);assert.equal(loads,n,'Private media never enters this cache');
 visibility='public';await c.get('first');c.destroy();const other=make({owner:'two'});await other.get('first');assert.equal(loads,n+2,'Accounts cannot share cached blobs');assert(!entries.has('one/first'));
 const offlineStore={async prune(){throw Error()},async get(){throw Error()},async put(){throw Error()},async delete(){throw Error()}};
 const fallback=make({store:offlineStore});await fallback.get('quota');const before=loads;await fallback.get('quota');assert.equal(loads,before,'Storage denial still permits memory reuse');
 const small=make({store:null,maxBytes:2});await small.get('a');await small.get('b');const prev=loads;await small.get('a');assert.equal(loads,prev+1,'Memory cache evicts least-recently-used bytes');
 c=make();c.destroy();await assert.rejects(c.get('closed'),/closed/);
 console.log('Vibe media reuse, persistent reopening, live authorization/counts, expiry, source change, private exclusion, account isolation, quota fallback and LRU bounds passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
