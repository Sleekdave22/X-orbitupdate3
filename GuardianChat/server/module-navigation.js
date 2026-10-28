/* Shared live unread badges and links; existing module destinations stay in place. */
(()=>{'use strict';
let state=null,owner='',busy=false;
const accountNow=()=>typeof account==='undefined'?null:account;
const native=typeof GuardianGaming!=='undefined';
const make=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n};
function jump(page){if(native){if(page==='/')GuardianGaming.orbitChat();else if(page==='/gaming.html')GuardianGaming.orbitPlay();else GuardianGaming.market()}else location.assign(page)}
if(native&&GuardianGaming.moduleTabs?.())document.documentElement.classList.add('native-module-shell');
const module=document.body.dataset.orbitModule||(document.getElementById('chatsTab')?'chat':'');document.body.dataset.orbitModule=module;
if(['play','chat','market'].includes(module)){
 document.body.classList.add('orbit-module-shell');
 const heading=document.querySelector('header h1'),header=document.querySelector('header');
 const nav=module==='chat'?document.querySelector('.arena-account-row'):document.querySelector('.orbit-module-switcher')||make('nav');if(!nav)return;
 nav.classList.add('orbit-module-switcher');const specs=[['Play','/gaming.html','/branding/orbit-icon-plain.png'],['Chat','/','/navigation-icons/chat-icon.svg'],['Plaza','/market.html','/navigation-icons/orbit-market-icon.svg']];
 const current={play:0,chat:1,market:2}[module],items=specs.map(([label,page,icon],index)=>{
  let b=module==='chat'?document.getElementById(index===0?'gamingTab':index===2?'marketTab':'moduleChat'):[...nav.querySelectorAll('button')].find(button=>button.dataset.destination===page);
  if(!b){b=make('button');b.type='button';const img=make('img');img.src=icon;img.alt='';b.append(img,make('span',label));if(module==='chat')b.id='moduleChat'}else{const text=b.querySelector('span');if(text)text.textContent=label}
  nav.append(b);if(index===1)b.dataset.unreadChat='1';return {button:b,label:'Orbit '+label,activate:()=>jump(page)};
 });
 document.body.append(nav);nav.hidden=!accountNow();
 window.OrbitSwitch?.mount(nav,items,current);
 if(module==='market'||module==='play'){
  const settings=make('button');settings.type='button';settings.id=module==='market'?'marketSettings':'playSettings';settings.setAttribute('aria-label','Open settings');settings.title='Account settings';settings.innerHTML='<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>';
  settings.onclick=()=>{if(native&&GuardianGaming.settings)GuardianGaming.settings();else location.assign('/?home=settings')};header?.append(settings);const bell=document.getElementById('marketActivityBell');if(bell)header.append(bell);
 }
}
function badge(target,count,label='unread messages'){const host=target.querySelector('.orbit-tab-artwork')||target;let b=target.querySelector('.chat-unread-badge');if(!count){b?.remove();return}if(!b){b=make('span');b.className='chat-unread-badge';host.append(b)}b.textContent=count>99?'99+':String(count);b.setAttribute('aria-label',count+' '+label)}
function avatar(target,id){if(!target)return;target.dataset.accountId=id;const active=state?.vibes?.[id],live=active&&active.expires*1000>Date.now();target.classList.toggle('vibe-has-content',Boolean(live));let icon=target.querySelector('.vibe-profile-indicator');if(!live){icon?.remove();return}if(!icon){icon=make('button');icon.type='button';icon.className='vibe-profile-indicator';const img=make('img');img.src='/navigation-icons/vibe-icon.svg';img.alt='';icon.append(img);target.append(icon)}icon.setAttribute('aria-label','View active Vibe');icon.onclick=e=>{e.stopPropagation();e.preventDefault();location.assign('/vibe.html?item='+active.item+'&visibility='+active.visibility)}}
function paint(){
 const account=accountNow();if(!account||state?.account!==account.id)return;
 for(const id of ['chatsTab','vibeChat']){const target=document.getElementById(id);if(target)badge(target,state.unread_messages)}
 for(const [ids,key,label] of [[['callsTab','vibeCalls'],'missed_calls','unseen missed calls'],[['vibeTab'],'unseen_vibes','unseen Vibe posts']])for(const id of ids){const target=document.getElementById(id);if(target)badge(target,state[key],label)}
 document.querySelectorAll('[data-unread-chat]').forEach(n=>badge(n,state.unread_messages));
 document.querySelectorAll('[data-account-id]').forEach(n=>avatar(n,n.dataset.accountId));
 avatar(document.getElementById('ownAvatar'),account.id);
 if(typeof peer!=='undefined'&&peer)avatar(document.getElementById('peerAvatar'),peer.id);
 document.querySelectorAll('#people button[data-peer]').forEach(n=>avatar(n.querySelector('.avatar'),n.dataset.peer));
}
if(typeof loadAvatar==='function'){const original=loadAvatar;loadAvatar=async function(id,target,...args){if(target)target.dataset.accountId=id;await original(id,target,...args);avatar(target,id)}}
function clear(){const modules=document.querySelector('.orbit-module-switcher');if(modules)modules.hidden=!accountNow();document.querySelectorAll('.chat-unread-badge,.vibe-profile-indicator').forEach(n=>n.remove());document.querySelectorAll('.vibe-has-content').forEach(n=>n.classList.remove('vibe-has-content'))}
async function refresh(){const a=accountNow();if(!a){owner='';state=null;clear();return}if(document.hidden||busy)return;if(owner!==a.id){owner=a.id;state=null;clear()}busy=true;try{const r=await api('/navigation/state');if(accountNow()?.id!==a.id||r.account!==a.id)return;state=r;paint()}catch(_){/* Keep the last known badge on a transient connection failure. */}finally{busy=false}}
window.OrbitModuleNavigation={refresh,paint};refresh();setInterval(refresh,3000);document.addEventListener('visibilitychange',refresh);window.addEventListener('focus',refresh);
})();
