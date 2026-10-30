/* Find friends (Chat). Broadcast matching: 3 Highly Important + 2 Considerable traits.
   Only people who switched on "Available to be friended" can receive a request; nothing about their traits is shown. */
(()=>{'use strict';
const $=id=>document.getElementById(id),btn=$('friendFindBtn'),dlg=$('friendDialog');
if(!btn||!dlg)return;
const node=(tag,text='',cls='')=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n};
const button=(text,fn,cls='')=>{const b=node('button',text,cls);b.type='button';b.onclick=fn;return b};
let catalog=null,mine=[],settings=null,tab='requests',picks=new Map(),busy=false;
const body=$('friendBody'),msg=$('friendMessage'),tabs=$('friendTabs');
const say=(text,bad=false)=>{msg.textContent=text||'';msg.dataset.bad=bad?'1':''};
async function call(path,payload){return payload?api(path,payload):api(path)}
function label(id){return catalog?.traits.find(t=>t.id===id)?.label||id}
function chips(selected,onToggle,state){const wrap=node('div','','fr-chips');for(const t of catalog.traits){const s=state?state(t.id):selected.has(t.id)?'on':'';const b=button(t.label,()=>onToggle(t.id),'fr-chip'+(s?' fr-'+s:''));b.setAttribute('aria-pressed',String(Boolean(s)));if(state)b.setAttribute('aria-label',t.label+(s==='high'?', highly important':s==='cons'?', considerable':', not chosen'));wrap.append(b)}return wrap}
function render(){tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===tab)));say('');
 if(tab==='requests')requests();else if(tab==='find')find();else me()}

async function requests(){body.replaceChildren(node('p','Loading…','muted'));
 try{const {requests:list}=await call('/friends/inbox');body.replaceChildren();refreshBadge();
  if(!list.length){body.append(node('p','No friend requests right now. Requests only arrive while "Available to be friended" is on, and only from people whose wishes match you.','muted'));return}
  for(const r of list){const card=node('article','','fr-card');
   card.append(node('strong',r.from.name),node('span',' @'+r.from.nickname,'muted'),node('p',r.intent_label+(r.note?' · '+r.note:''),'fr-intent'));
   const why=node('p','','fr-why');why.append(node('span','Matches what they want: ','muted'));for(const t of r.matched)why.append(node('span',t.label,'fr-tag'));card.append(why);
   const row=node('div','','fr-actions');
   const act=(text,action,cls)=>button(text,async()=>{row.querySelectorAll('button').forEach(b=>b.disabled=true);try{await call('/friends/respond',{id:r.id,action});card.replaceChildren(node('p',action==='accept'?'You are now friends with '+r.from.name+'. You can message them from your chats.':action==='block'?'Blocked. They will not be able to send you requests.':'Done.','muted'));if(action==='accept'&&typeof people==='function')people();refreshBadge()}catch(e){say(e.message,true);row.querySelectorAll('button').forEach(b=>b.disabled=false)}},cls);
   row.append(act('Accept','accept','fr-primary'),act('Decline','decline'),act('Ignore','ignore'),act('Block','block','fr-quiet'));card.append(row);body.append(card)}
 }catch(e){body.replaceChildren(node('p',e.message,'muted'))}}

function find(){body.replaceChildren();
 if(!settings||mine.length<1){/* sender need not be available themselves */}
 body.append(node('p','Pick exactly 5 traits you want in a friend. Tap a trait once for Highly Important (all 3 must match), twice for Considerable (at least 1 of 2 must match), three times to clear.','muted'));
 const counts=node('p','','fr-counts'),send=button('Send broadcast',sendIt,'fr-primary');
 const state=id=>picks.get(id)||'';
 const grid=chips(null,id=>{const s=picks.get(id);const high=[...picks.values()].filter(v=>v==='high').length,cons=[...picks.values()].filter(v=>v==='cons').length;
  if(!s){if(high<3)picks.set(id,'high');else if(cons<2)picks.set(id,'cons');else{say('You already chose 3 Highly Important and 2 Considerable traits. Clear one first.',true);return}}
  else if(s==='high'){if(cons<2)picks.set(id,'cons');else picks.delete(id)}else picks.delete(id);
  say('');paint()},state);
 const intent=node('select');intent.id='friendIntent';intent.setAttribute('aria-label','What kind of friendship');for(const i of catalog.intents)intent.append(new Option(i.label,i.id));
 const note=node('input');note.id='friendNote';note.maxLength=catalog.limits.note_max;note.placeholder='Optional short note ('+catalog.limits.note_max+' characters)';
 function paint(){grid.querySelectorAll('button').forEach((b,i)=>{const id=catalog.traits[i].id,s=state(id);b.className='fr-chip'+(s?' fr-'+s:'');b.setAttribute('aria-pressed',String(Boolean(s)));b.setAttribute('aria-label',catalog.traits[i].label+(s==='high'?', highly important':s==='cons'?', considerable':', not chosen'))});
  const h=[...picks.values()].filter(v=>v==='high').length,c=[...picks.values()].filter(v=>v==='cons').length;counts.textContent='Highly Important '+h+'/3 · Considerable '+c+'/2';send.disabled=!(h===3&&c===2)||busy}
 async function sendIt(){const high=[...picks].filter(([,v])=>v==='high').map(([k])=>k),considerable=[...picks].filter(([,v])=>v==='cons').map(([k])=>k);busy=true;paint();
  try{const r=await call('/friends/broadcast',{high,considerable,intent:intent.value,note:note.value.trim()});picks=new Map();note.value='';paint();say('Broadcast sent. You will see a notice when someone accepts. Broadcasts left today: '+r.remaining_today+'.');loadMine(list)}catch(e){say(e.message,true)}finally{busy=false;paint()}}
 const legend=node('p','','fr-legend');legend.append(node('span','Highly Important','fr-tag fr-high'),node('span','Considerable','fr-tag fr-cons'));
 const list=node('div','','fr-mine');
 body.append(legend,grid,counts,node('label','What kind of friendship?'),intent,note,send,node('h3','My broadcasts'),list);paint();loadMine(list)}
async function loadMine(list){try{const {broadcasts}=await call('/friends/mine');list.replaceChildren();refreshBadge();
  if(!broadcasts.length){list.append(node('p','Nothing sent yet.','muted'));return}
  for(const b of broadcasts){const c=node('article','','fr-card');c.append(node('strong',b.intent_label),node('p',b.high.map(t=>t.label).join(', ')+' · also '+b.considerable.map(t=>t.label).join(' or '),'muted'));
   c.append(node('p',b.accepted.length?'Accepted by '+b.accepted.map(a=>a.name+(a.new?' (new)':'')).join(', '):'No one has accepted yet.','fr-accepted'));list.append(c)}
 }catch(e){list.replaceChildren(node('p',e.message,'muted'))}}

function me(){body.replaceChildren();const sel=new Set(mine),lim=catalog.limits;
 const toggle=node('label','','fr-switch'),box=node('input');box.type='checkbox';box.checked=Boolean(settings.available);toggle.append(box,node('span','Available to be friended'));
 const help=node('p','While this is on, you can receive friend requests from people whose wishes match your traits. Turn it off at any time and nobody can send you a request. Requests already waiting can still be answered.','muted');
 const count=node('p','','fr-counts'),grid=chips(sel,id=>{if(sel.has(id))sel.delete(id);else if(sel.size<lim.my_traits_max)sel.add(id);else say('Choose at most '+lim.my_traits_max+' traits.',true);paintMe()});
 function paintMe(){grid.querySelectorAll('button').forEach((b,i)=>{const on=sel.has(catalog.traits[i].id);b.className='fr-chip'+(on?' fr-on':'');b.setAttribute('aria-pressed',String(on))});count.textContent=sel.size+' chosen · pick '+lim.my_traits_min+' to '+lim.my_traits_max+' that describe you. Only you can see this list.'}
 const notify=node('select');notify.setAttribute('aria-label','Request notifications');for(const [v,t] of [['instant','Notify me straight away'],['daily','Daily summary at '+lim.daily_summary_hour+':00'],['off','Do not notify me (I will check the list)']])notify.append(new Option(t,v));notify.value=settings.notify;
 const hours=(sel0)=>{const s=node('select');s.append(new Option('Off',''));for(let h=0;h<24;h++)s.append(new Option((h<10?'0':'')+h+':00',String(h)));s.value=sel0===null||sel0===undefined?'':String(sel0);return s};
 const qs=hours(settings.quiet_start),qe=hours(settings.quiet_end),quiet=node('div','','fr-quiet-hours');quiet.append(node('span','Quiet hours from '),qs,node('span',' to '),qe);
 const saveBtn=button('Save',async()=>{saveBtn.disabled=true;try{const q=qs.value!==''&&qe.value!=='';
   await call('/friends/traits',{traits:[...sel]});
   const r=await call('/friends/settings',{available:box.checked,notify:notify.value,quiet_start:q?Number(qs.value):null,quiet_end:q?Number(qe.value):null,tz_offset:-new Date().getTimezoneOffset()});
   mine=[...sel];settings=r.settings;say(settings.available?'Saved. You are available to be friended.':'Saved. You are hidden from friend matching.')}catch(e){say(e.message,true)}finally{saveBtn.disabled=false}},'fr-primary');
 body.append(toggle,help,node('h3','About you'),grid,count,node('h3','Notifications'),notify,quiet,saveBtn);paintMe()}

async function refreshBadge(){try{await window.OrbitModuleNavigation?.refresh()}catch(_){}}
async function open(){say('');dlg.showModal();body.replaceChildren(node('p','Loading…','muted'));
 try{const d=await call('/friends/info');catalog=d;mine=d.mine;settings=d.settings;tab='requests';render()}catch(e){body.replaceChildren(node('p',e.message,'muted'))}}
tabs.addEventListener('click',e=>{const b=e.target.closest('button[data-tab]');if(!b||!catalog)return;tab=b.dataset.tab;render()});
btn.onclick=open;$('friendClose').onclick=()=>dlg.close();
})();
