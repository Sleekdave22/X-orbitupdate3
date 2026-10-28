/* Account discovery is separate from contacts and never grants messaging access. */
(()=>{
 let version=0,query='',next=null,ownerId=account?.id;
 const form=el('globalSearchForm'),input=el('globalSearchQuery'),status=el('globalSearchStatus'),results=el('globalSearchResults'),more=el('globalSearchMore');
 window.OrbitAccountSearch={resetForAccount(){if(ownerId===account?.id)return;ownerId=account?.id;version++;query='';next=null;input.value='';results.replaceChildren();status.textContent='';more.hidden=true}};
 async function search(append=false){
  const owner=account?.id,current=++version;
  if(!owner)return;
  if(!append)query=input.value.trim();
  if(query.replace(/^@/,'').length<2){status.textContent='Enter at least 2 characters';return}
  const offset=append?next:0;
  more.hidden=true;status.textContent='Searching…';
  if(!append)results.replaceChildren();
  try{
   const data=await api('/social/search?q='+encodeURIComponent(query)+'&offset='+(offset||0));
   if(version!==current||account?.id!==owner)return;
   for(const u of data.users){
    const row=document.createElement('div');row.className='account-result';
    const open=document.createElement('button');open.type='button';open.title='View this account and its connection options';
    const photo=document.createElement('span');photo.className='avatar';
    if(u.avatar){const img=document.createElement('img');img.src='data:'+u.avatar_mime+';base64,'+u.avatar;img.alt='';photo.append(img)}else photo.textContent=u.name.slice(0,1);
    const name=document.createElement('span');name.textContent=u.name;
    const detail=document.createElement('small');detail.textContent='@'+u.nickname+(u.contact?' · In your chats':'');name.append(detail);
    open.append(photo,name);open.onclick=()=>openSocialProfile(u.id);row.append(open);results.append(row);
   }
   next=data.next_offset;more.hidden=next===null;status.textContent=results.childElementCount?'Select an account to view its profile.':'No matching accounts. Try an exact @nickname or account ID.';
  }catch(e){if(version===current&&account?.id===owner){status.textContent=e.message;more.hidden=!append||next===null}}
 }
 form.onsubmit=e=>{e.preventDefault();search()};more.onclick=()=>search(true);
 input.oninput=()=>{version++;next=null;more.hidden=true;results.replaceChildren();status.textContent=''};
})();

/* A separate magnifier scopes message lookup to the open conversation. */
(()=>{
 const menu=el('navigationMenu'),toggle=el('menuToggle'),search=el('topSearch');let dialog=null,jumped=false;
 function closeMenu(focus=false){menu.hidden=true;toggle.setAttribute('aria-expanded','false');if(focus)toggle.focus()}
 function closeSearch(){dialog?.close();dialog=null;jumped=false}
 function sync(){
  const chat=activeScreen==='chat'&&!!peer;
  search.hidden=!account||!chat;search.setAttribute('aria-label',chat?'Search this chat':'Search accounts');search.title=chat?'Find messages in this conversation':'Find an account across X ORBIT';
  el('homeBack').hidden=!account;el('chatSearch').hidden=!account||activeScreen!=='contacts'||homeMode==='search';
  el('myProfile').hidden=!account;el('menuOrbitPlay').hidden=!account;
  if(!chat)closeSearch();closeMenu();
 }
 toggle.onclick=()=>{const open=menu.hidden;menu.hidden=!open;toggle.setAttribute('aria-expanded',String(open));if(open)menu.querySelector('button:not([hidden])')?.focus()};
 for(const id of ['myProfile','openSettings']){const b=el(id),action=b.onclick;b.setAttribute('role','menuitem');b.onclick=e=>{closeMenu();action?.call(b,e)}}
 el('menuOrbitPlay').onclick=()=>location.assign('/gaming.html');
 el('homeBack').onclick=()=>{if(activeScreen==='profile')el('profileBack').click();else if(activeScreen==='chat')contacts();else if(homeMode!=='chats')chooseHome('chats');else if(history.length>1)history.back()};
 document.addEventListener('click',e=>{if(!menu.hidden&&!menu.contains(e.target)&&!toggle.contains(e.target))closeMenu()});
 document.addEventListener('keydown',e=>{if(menu.hidden)return;if(e.key==='Escape'){e.preventDefault();closeMenu(true)}else if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const buttons=[...menu.querySelectorAll('button:not([hidden])')],i=buttons.indexOf(document.activeElement);buttons[e.key==='Home'?0:e.key==='End'?buttons.length-1:(i+(e.key==='ArrowDown'?1:buttons.length-1))%buttons.length]?.focus()}});
 function openSearch(){
  closeMenu();if(activeScreen!=='chat'||!peer){chooseHome('search');if(activeScreen!=='contacts')contacts();el('globalSearchQuery').focus();return}
  closeSearch();const target=peer.id,version=chatVersion;
  const d=document.createElement('dialog');dialog=d;d.className='conversation-search';d.setAttribute('aria-label','Search this chat');
  const heading=document.createElement('h2');heading.textContent='Search this chat';
  const close=document.createElement('button');close.type='button';close.textContent='Close';close.onclick=()=>d.close();
  const form=document.createElement('form');form.dataset.formInline='1';const input=document.createElement('input');input.type='search';input.maxLength=100;input.placeholder='Words or file name';input.setAttribute('aria-label','Search this conversation');
  const submit=document.createElement('button');submit.textContent='Search';form.append(input,submit);
  const status=document.createElement('p');status.setAttribute('role','status');const results=document.createElement('div');results.className='conversation-search-results';
  function find(){
   if(peer?.id!==target||chatVersion!==version){d.close();return}results.replaceChildren();
   const query=input.value.trim().toLocaleLowerCase();if(!query){status.textContent='Find messages in this conversation.';return}
   if(chatEntryPending){status.textContent='Messages are still loading. Search again shortly.';return}
   const rows=[...el('messages').querySelectorAll('[data-message-id]')].filter(row=>{const m=row._message;return m&&!m.view_once&&!m.protected_media&&!m.deleted_all&&((m.text||'')+' '+(m.filename||'')).toLocaleLowerCase().includes(query)}).reverse();
   status.textContent=rows.length?rows.length+(rows.length===1?' matching message':' matching messages')+(rows.length>100?' · showing the latest 100':''):'No matching messages';
   for(const row of rows.slice(0,100)){
    const m=row._message,b=document.createElement('button');b.type='button';b.textContent=(m.sender===account.id?'You':peer.name)+' · '+new Date(m.time).toLocaleString()+'\n'+(m.text||m.filename||'Message').slice(0,180);
    b.onclick=()=>{d.close();if(peer?.id!==target||version!==chatVersion||!row.isConnected)return;jumped=true;row.scrollIntoView({block:'center',behavior:'smooth'});row.classList.add('search-match');setTimeout(()=>row.classList.remove('search-match'),1600)};results.append(b);
   }
  }
  input.oninput=find;form.onsubmit=e=>{e.preventDefault();find()};d.append(heading,close,form,status,results);document.body.append(d);d.onclose=()=>{d.remove();if(dialog===d)dialog=null};d.showModal();find();input.focus();
 }
 search.onclick=openSearch;el('messages').addEventListener('scroll',()=>{const box=el('messages');if(box.scrollHeight-box.clientHeight-box.scrollTop<40)jumped=false});window.OrbitChatNavigation={sync,closeSearch,get viewingSearchResult(){return jumped}};sync();
})();

 document.getElementById("closeNavigation")?.addEventListener("click",()=>document.getElementById("menuToggle").click());
