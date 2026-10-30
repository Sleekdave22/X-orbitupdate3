/* The home swipe shell: Orbit Play | Orbit Chat | Orbit Plaza.
   One pager, one tab row, one shared line that follows your finger. Orbit Chat is the page's own
   #contacts section; Play and Plaza are their normal pages shown in frames (?embed=1). */
(function(){
  const contacts=document.getElementById('contacts'),playBtn=document.getElementById('gamingTab'),plazaBtn=document.getElementById('marketTab');
  if(!contacts||!playBtn||!plazaBtn)return;
  const NAMES=['play','chat','plaza'],TITLES=['Orbit Play',null,'Orbit Plaza'],URLS=['/gaming.html?embed=1',null,'/market.html?embed=1'];
  const reduce=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  const h=(tag,attrs={},kids=[])=>{const n=document.createElement(tag);for(const k in attrs)n.setAttribute(k,attrs[k]);n.append(...kids);return n};
  const chatBtn=h('button',{id:'chatPaneTab',type:'button','aria-label':'Open Orbit Chat'});
  chatBtn.innerHTML='<img src="/navigation-icons/chat-icon.svg" alt="" width="22" height="22"><span>Chat</span>';
  // Re-use the two existing buttons (they carry the unread badges) as the Play and Plaza tabs.
  playBtn.querySelector('span').textContent='Play';plazaBtn.querySelector('span').textContent='Plaza';
  plazaBtn.querySelector('img').src='/navigation-icons/orbit-market-icon.svg';
  const tabs=[playBtn,chatBtn,plazaBtn];
  const line=h('div',{class:'orbit-line','aria-hidden':'true'},[h('span')]);
  const bar=h('div',{id:'orbitTabs',role:'tablist','aria-label':'Orbit Play, Orbit Chat and Orbit Plaza'},[...tabs,line]);
  const frames=[null,null,null];
  const paneEls=NAMES.map(n=>h('div',{class:'orbit-pane',id:'pane-'+n,role:'tabpanel','aria-label':{play:'Orbit Play',chat:'Orbit Chat',plaza:'Orbit Plaza'}[n]}));
  const track=h('div',{id:'orbitTrack'},paneEls);
  const pager=h('div',{id:'orbitPager'},[bar,track]);
  contacts.replaceWith(pager);paneEls[1].append(contacts);
  const arena=document.querySelector('.arena-account-row');arena?.remove();
  for(const t of tabs){t.classList.add('orbit-tab');t.setAttribute('role','tab')}
  const title=document.querySelector('.brand-header h1');let chatTitle=title?title.textContent:'OrbitChat';
  let current=1;

  function ensureFrame(i){
    if(i===1||frames[i])return;
    const f=h('iframe',{src:URLS[i],title:TITLES[i],loading:'eager',allow:'camera;microphone;clipboard-write'});
    frames[i]=f;paneEls[i].append(f);
  }
  const width=()=>track.clientWidth||1;
  function paint(){
    if(!track.clientWidth)return;
    const p=Math.max(0,Math.min(2,track.scrollLeft/width()));
    line.style.transform='translateX('+(p*100)+'%)';
    const idx=Math.round(p);
    if(idx!==current){current=idx;label()}
    if(p>0.05&&p<1.95){ensureFrame(p<1?0:2)}
  }
  let raf=0;track.addEventListener('scroll',()=>{if(!raf)raf=requestAnimationFrame(()=>{raf=0;paint()})},{passive:true});
  function label(){
    tabs.forEach((t,i)=>{t.setAttribute('aria-selected',String(i===current));t.tabIndex=i===current?0:-1});
    if(title){if(current===1)title.textContent=chatTitle;else{if(title.textContent!==TITLES[0]&&title.textContent!==TITLES[2])chatTitle=title.textContent;title.textContent=TITLES[current]}}
    pager.dataset.pane=NAMES[current];
    paneEls.forEach((p,i)=>{p.toggleAttribute('inert',i!==current)});
    try{const u=new URL(location.href);if(current===1)u.searchParams.delete('pane');else u.searchParams.set('pane',NAMES[current]);history.replaceState(null,'',u)}catch(e){}
  }
  if(title)new MutationObserver(()=>{if(current!==1&&title.textContent!==TITLES[current]){chatTitle=title.textContent;title.textContent=TITLES[current]}}).observe(title,{childList:true,characterData:true,subtree:true});
  function go(i,smooth=true){
    i=Math.max(0,Math.min(2,i));ensureFrame(i);
    track.scrollTo({left:i*width(),behavior:smooth&&!reduce()?'smooth':'auto'});
    if(!smooth||reduce()){current=i;label();line.style.transform='translateX('+(i*100)+'%)'}
  }
  tabs.forEach((t,i)=>{t.onclick=ev=>{ev.preventDefault();ev.stopPropagation();go(i)}});
  bar.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const n=e.key==='Home'?0:e.key==='End'?2:current+(e.key==='ArrowRight'?1:-1);go(n);tabs[Math.max(0,Math.min(2,n))].focus()});
  addEventListener('resize',()=>go(current,false));

  // Swipes that start inside Play or Plaza arrive here as messages.
  let dragFrom=0;
  addEventListener('message',e=>{
    if(e.origin!==location.origin||!e.data||!e.data.orbitShell)return;
    const m=e.data;
    if(m.orbitShell==='go'){const u=String(m.url||'/');if(u==='/'||/^\/\?pane=chat/.test(u))go(1);else location.assign(u);return}
    if(m.orbitShell!=='drag')return;
    if(m.phase==='start'){dragFrom=track.scrollLeft;track.style.scrollSnapType='none'}
    else if(m.phase==='move'){track.scrollLeft=Math.max(0,Math.min(width()*2,dragFrom-m.dx))}
    else if(m.phase==='end'){track.style.scrollSnapType='';const w=width(),start=Math.round(dragFrom/w);let to=Math.round(track.scrollLeft/w);if(Math.abs(m.v)>0.45||Math.abs(m.dx)>w*0.18)to=start+(m.dx<0?1:-1);go(to)}
  });

  // A chat row swipes left to delete (existing behaviour). Swiping a row to the right moves to Orbit Play.
  const people=document.getElementById('people');let rx=0,ry=0;
  if(people){people.addEventListener('pointerdown',e=>{rx=e.clientX;ry=e.clientY},true);
    people.addEventListener('pointerup',e=>{const dx=e.clientX-rx,dy=e.clientY-ry;if(dx>70&&dx>Math.abs(dy)*1.5&&current===1)go(0)},true)}

  // Show the shell only where the chat list is the page, and only in the Chats view.
  function sync(){
    const on=!contacts.hidden||pager.dataset.keep==='1';
    const here=typeof activeScreen!=='undefined'&&activeScreen==='contacts';
    pager.hidden=!here;
    const chats=typeof homeMode==='undefined'||homeMode==='chats';
    bar.hidden=!chats;
    if(!chats&&current!==1)go(1,false);
    document.body.classList.toggle('orbit-shell-on',here&&chats);
  }
  const prev=window.syncMainNavigation;
  if(typeof prev==='function'){window.syncMainNavigation=function(){prev.apply(this,arguments);sync()}}
  const prevShow=window.show;if(typeof prevShow==='function')window.show=function(){const r=prevShow.apply(this,arguments);sync();return r};
  new MutationObserver(sync).observe(contacts,{attributes:true,attributeFilter:['hidden']});

  const want=new URLSearchParams(location.search).get('pane');
  const found=NAMES.indexOf(want),start=found<0?1:found;
  requestAnimationFrame(()=>{go(start,false);sync();(window.requestIdleCallback||(f=>setTimeout(f,1500)))(()=>{ensureFrame(0);ensureFrame(2)},{timeout:2500})});
  label();
  window.OrbitShell={go,pane:()=>NAMES[current]};
})();
