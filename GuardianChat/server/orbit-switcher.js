/* One shared indicator; existing module routes and handlers remain authoritative. */
(()=>{'use strict';
const reduced=()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
function mount(host,items,selected){
 const line=document.createElement('span');line.className='orbit-shared-line';line.setAttribute('aria-hidden','true');host.classList.add('orbit-swipe-tabs');host.setAttribute('role','tablist');host.setAttribute('aria-label','Orbit sections');
 let down=null,dragging=false,consumed=false,leaving=false;
 const paint=p=>{line.style.transform='translateX('+(Math.max(0,Math.min(2,p))*100)+'%)'};
 function go(index){if(leaving||index===selected){paint(selected);return}leaving=true;line.style.transition=reduced()?'none':'transform 180ms ease-out';paint(index);
  try{sessionStorage.setItem('orbit-switch-direction',index>selected?'1':'-1')}catch(_){}
  const page=document.querySelector('main');if(page&&!reduced())page.animate?.([{transform:'translateX(0)',opacity:1},{transform:'translateX('+(index>selected?-28:28)+'px)',opacity:.65}],{duration:160,easing:'ease-out'});
  setTimeout(()=>items[index].activate(),reduced()?0:165);
 }
 items.forEach((item,index)=>{const b=item.button;b.setAttribute('role','tab');b.setAttribute('aria-selected',String(index===selected));b.setAttribute('aria-label',item.label);b.tabIndex=index===selected?0:-1;b.onclick=()=>{if(!consumed)go(index);consumed=false};b.addEventListener('keydown',e=>{const next=e.key==='ArrowRight'?Math.min(2,index+1):e.key==='ArrowLeft'?Math.max(0,index-1):e.key==='Home'?0:e.key==='End'?2:null;if(next===null)return;e.preventDefault();items[next].button.focus();go(next)})});
 host.append(line);paint(selected);
 host.addEventListener('pointerdown',e=>{if(e.button!==undefined&&e.button!==0||leaving)return;down={x:e.clientX,y:e.clientY,time:performance.now(),id:e.pointerId};dragging=false;consumed=false});
 host.addEventListener('pointermove',e=>{if(!down||e.pointerId!==down.id)return;const dx=e.clientX-down.x,dy=e.clientY-down.y;if(!dragging&&Math.abs(dy)>12&&Math.abs(dy)>Math.abs(dx)){down=null;return}if(Math.abs(dx)<10&&!dragging)return;dragging=true;consumed=true;host.setPointerCapture?.(e.pointerId);e.preventDefault();line.style.transition='none';paint(selected-dx/Math.max(1,host.clientWidth))});
 function end(e,cancel=false){if(!down||e.pointerId!==down.id)return;const dx=e.clientX-down.x,elapsed=Math.max(1,performance.now()-down.time),moved=dragging;down=null;dragging=false;line.style.transition=reduced()?'none':'transform 180ms ease-out';const threshold=Math.abs(dx)>host.clientWidth*.22||Math.abs(dx)>32&&Math.abs(dx)/elapsed>.6;if(moved&&!cancel&&threshold)go(Math.max(0,Math.min(2,selected+(dx<0?1:-1))));else paint(selected);if(moved)setTimeout(()=>consumed=false,250)}
 host.addEventListener('pointerup',e=>end(e));host.addEventListener('pointercancel',e=>end(e,true));
 return {go};
}
window.OrbitSwitch={mount};
if(document.body.dataset.orbitModule==="vibe"&&!reduced())document.querySelector("main")?.animate?.([{opacity:.4,transform:"translateY(7px)"},{opacity:1,transform:"translateY(0)"}],{duration:170,easing:"ease-out"});
try{const direction=sessionStorage.getItem('orbit-switch-direction');sessionStorage.removeItem('orbit-switch-direction');if(direction&&!reduced())document.querySelector('main')?.animate?.([{transform:'translateX('+(Number(direction)*28)+'px)',opacity:.65},{transform:'translateX(0)',opacity:1}],{duration:180,easing:'ease-out'})}catch(_){}
// Small local openings animate independently; main module changes use the slider above.
document.addEventListener('toggle',e=>{if(e.target.tagName==='DETAILS'&&e.target.open&&!reduced())for(const child of e.target.children)if(child.tagName!=='SUMMARY')child.animate?.([{opacity:0,transform:'translateY(-5px)'},{opacity:1,transform:'translateY(0)'}],{duration:170,easing:'ease-out'})},true);
document.addEventListener('click',e=>{const b=e.target.closest?.('button');if(!b||b.closest('.orbit-swipe-tabs')||reduced())return;if(b.matches('[data-tab],.profile-nav-tab,#tabBrowse,#tabShop,#sellItem,#publicVibe,#privateVibe'))requestAnimationFrame(()=>{const target=document.getElementById('view')||document.getElementById('vibeFeed');if(target&&!target.classList.contains('live-room'))target.animate?.([{opacity:.4,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}],{duration:170,easing:'ease-out'})})});
})();
