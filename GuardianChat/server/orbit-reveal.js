/* Open-from-the-icon reveal. A panel that is shown (hidden removed, or a dialog opened) grows out of the
   button that was just pressed. Used by settings, menus, notification panels and dialogs.
   Not used by the three main tabs (Play, Chat, Plaza): those swipe. Opening only; closing stays instant.
   Honours "reduce motion". */
(function(){
  const still=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  let last=null;
  const remember=e=>{const t=e.target.closest&&e.target.closest('button,a,summary,[role=button],[role=menuitem],[data-reveal-from]');if(t)last={t,at:performance.now()}};
  addEventListener('pointerdown',remember,true);addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' ')remember(e)},true);
  function origin(el,trigger){
    const r=el.getBoundingClientRect(),w=r.width||innerWidth,h=r.height||innerHeight;
    let x=w,y=0;
    if(trigger&&trigger.isConnected){const b=trigger.getBoundingClientRect();x=b.left+b.width/2-r.left;y=b.top+b.height/2-r.top}
    x=Math.max(0,Math.min(w,x));y=Math.max(0,Math.min(h,y));
    const rad=Math.ceil(Math.hypot(Math.max(x,w-x),Math.max(y,h-y)));
    return {x,y,rad};
  }
  function play(el,trigger){
    if(still()||!el.animate)return;
    if(!trigger&&last&&performance.now()-last.at<1500)trigger=last.t;
    const o=origin(el,trigger);
    el.animate([{clipPath:'circle(0px at '+o.x+'px '+o.y+'px)',opacity:.4},{clipPath:'circle('+o.rad+'px at '+o.x+'px '+o.y+'px)',opacity:1}],{duration:360,easing:'cubic-bezier(.2,.8,.2,1)'});
  }
  const SELECTOR='#settingsPanel,#navigationMenu,dialog,[data-reveal],#profile,#callList';
  const seen=new WeakSet();
  function watch(el){
    if(seen.has(el))return;seen.add(el);
    new MutationObserver(list=>{for(const m of list){if(m.attributeName==='hidden'&&!el.hidden&&m.oldValue!==null)play(el);if(m.attributeName==='open'&&el.open&&m.oldValue===null)play(el)}}).observe(el,{attributes:true,attributeFilter:['hidden','open'],attributeOldValue:true});
  }
  function scan(root){(root.querySelectorAll?root.querySelectorAll(SELECTOR):[]).forEach(watch);if(root.matches&&root.matches(SELECTOR))watch(root)}
  function start(){scan(document);new MutationObserver(l=>{for(const m of l)m.addedNodes.forEach(n=>{if(n.nodeType===1)scan(n)})}).observe(document.body,{childList:true,subtree:true})}
  // Tabs that open a different page (Vibe, My Orbit, Calls from Vibe): the next page grows from the tab that was pressed.
  const KEY='orbit-reveal-from';
  addEventListener('click',e=>{const t=e.target.closest&&e.target.closest('.orbit-bottom-nav button,[data-reveal-from]');if(!t)return;const b=t.getBoundingClientRect();try{sessionStorage.setItem(KEY,JSON.stringify({x:b.left+b.width/2,y:b.top+b.height/2,at:Date.now()}))}catch(_){}},true);
  try{const raw=sessionStorage.getItem(KEY);if(raw){sessionStorage.removeItem(KEY);const o=JSON.parse(raw);
    if(Date.now()-o.at<4000&&!still()&&document.documentElement.animate&&window.parent===window){const rad=Math.ceil(Math.hypot(Math.max(o.x,innerWidth-o.x),Math.max(o.y,innerHeight-o.y)));
      document.documentElement.animate([{clipPath:'circle(0px at '+o.x+'px '+o.y+'px)'},{clipPath:'circle('+rad+'px at '+o.x+'px '+o.y+'px)'}],{duration:380,easing:'cubic-bezier(.2,.8,.2,1)'})}}}catch(_){}
  window.OrbitReveal={play,watch};
  if(document.body)start();else addEventListener('DOMContentLoaded',start);
})();
