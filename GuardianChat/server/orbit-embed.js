/* Loaded by Orbit Play and Orbit Plaza. When the page is shown inside the swipe shell it
   (1) drops its own title bar (the shell supplies one), (2) forwards sideways swipes to the shell,
   (3) sends "leave this page" requests up instead of navigating the small frame. */
(function(){
  const embedded=window.parent!==window&&/[?&]embed=1\b/.test(location.search);
  window.orbitEmbedded=embedded;
  window.orbitGo=function(url){
    if(embedded)parent.postMessage({orbitShell:'go',url:String(url)},location.origin);else location.assign(url);
  };
  if(!embedded)return;
  document.documentElement.classList.add('embedded');
  const post=m=>parent.postMessage(Object.assign({orbitShell:'drag'},m),location.origin);
  let sx=0,sy=0,mode='',lastX=0,lastT=0,v=0;
  const scrollsSideways=n=>{for(;n&&n!==document.body&&n.nodeType===1;n=n.parentElement){const s=getComputedStyle(n);if(/(auto|scroll)/.test(s.overflowX)&&n.scrollWidth>n.clientWidth+2)return true}return false};
  addEventListener('touchstart',e=>{if(e.touches.length!==1){mode='no';return}const t=e.touches[0];sx=lastX=t.clientX;sy=t.clientY;lastT=performance.now();v=0;mode=scrollsSideways(e.target)?'no':''},{passive:true});
  addEventListener('touchmove',e=>{if(mode==='no'||e.touches.length!==1)return;const t=e.touches[0],dx=t.clientX-sx,dy=t.clientY-sy;
    if(!mode){if(Math.abs(dx)<10&&Math.abs(dy)<10)return;mode=Math.abs(dx)>Math.abs(dy)*1.4?'h':'no';if(mode==='h')post({phase:'start'})}
    if(mode==='h'){const now=performance.now();v=(t.clientX-lastX)/Math.max(1,now-lastT);lastX=t.clientX;lastT=now;post({phase:'move',dx})}},{passive:true});
  const end=e=>{if(mode==='h'){const t=e.changedTouches[0];post({phase:'end',dx:t.clientX-sx,v})}mode=''};
  addEventListener('touchend',end,{passive:true});addEventListener('touchcancel',end,{passive:true});
})();
