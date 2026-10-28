/* Visible-time clock and downward drag, shared by every public Vibe. */
(()=>{'use strict';
function clock({now=()=>performance.now(),frame=fn=>requestAnimationFrame(fn),cancel=id=>cancelAnimationFrame(id),canRun=()=>true,onProgress,onEnd}){
 let handle=null,last=null,elapsed=0,limit=0,active=false,previousRunning=false;
 function tick(t){if(!active)return;const running=canRun();if(last!==null&&running&&previousRunning)elapsed=Math.min(limit,elapsed+Math.max(0,t-last));last=t;previousRunning=running;onProgress(elapsed/limit,Math.max(0,limit-elapsed));if(elapsed>=limit){active=false;handle=null;onEnd();return}handle=frame(tick)}
 return {start(ms){this.stop();limit=ms;elapsed=0;last=now();active=true;previousRunning=canRun();onProgress(0,ms);handle=frame(tick)},stop(){active=false;if(handle!==null)cancel(handle);handle=null;last=null},resetAnchor(){last=now()}};
}
function swipe({surface,panel,onDrag=()=>{},onClose,onTap=()=>{},now=()=>performance.now(),height=()=>innerHeight}){
 let start=null,drag=false,closing=false,timer=null;
 const reset=()=>{clearTimeout(timer);start=null;drag=false;closing=false;panel.style.transition='';panel.style.transform='';panel.style.setProperty('--vibe-backdrop-opacity','1');onDrag(false)};
 surface.addEventListener('pointerdown',e=>{if(e.button!==undefined&&e.button!==0||closing)return;if(document.activeElement?.tagName==='INPUT')document.activeElement.blur();start={x:e.clientX,y:e.clientY,t:now(),id:e.pointerId};drag=false});
 surface.addEventListener('pointermove',e=>{if(!start||e.pointerId!==start.id||closing)return;const dy=e.clientY-start.y,dx=e.clientX-start.x;if(!drag){if(Math.abs(dx)>16&&Math.abs(dx)>Math.abs(dy)){start=null;return}if(dy<7||Math.abs(dx)>dy)return;drag=true;onDrag(true);surface.setPointerCapture?.(e.pointerId)}e.preventDefault();panel.style.transition='none';panel.style.transform='translateY('+Math.max(0,dy)+'px)';panel.style.setProperty('--vibe-backdrop-opacity',String(Math.max(.15,1-dy/height())))});
 function finish(e,cancelled=false){if(!start||e.pointerId!==start.id)return;const tap=!cancelled&&!drag&&Math.abs(e.clientX-start.x)<12&&Math.abs(e.clientY-start.y)<12,rect=tap?surface.getBoundingClientRect():null;if(tap)onTap(Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width)));const distance=Math.max(0,e.clientY-start.y),velocity=distance/Math.max(1,now()-start.t),dismiss=!cancelled&&drag&&(distance>=Math.min(140,height()*.18)||distance>45&&velocity>.55);start=null;if(dismiss){closing=true;panel.style.transition='transform 160ms ease-out';panel.style.transform='translateY('+height()+'px)';timer=setTimeout(()=>{onClose();reset()},160)}else{panel.style.transition='transform 160ms ease-out';panel.style.transform='translateY(0)';panel.style.setProperty('--vibe-backdrop-opacity','1');onDrag(false);drag=false}}
 surface.addEventListener('pointerup',e=>finish(e));surface.addEventListener('pointercancel',e=>finish(e,true));return {reset};
}
window.OrbitVibeMotion={clock,swipe};
})();
