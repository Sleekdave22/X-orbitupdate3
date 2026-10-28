/* Account pairs style bubbles, selected tabs, module links, headings and wallpapers. */
(()=>{
 let owner='',session='',choices=[],generation=0,lastFetch=0,busy=false,draft=null,previewBright=false;
 const fallback={id:'orbit-cyan-navy',roles:2,accent:'#7C3AED',bubble:'#7C3AED',ink:'#FFFFFF',received:'#202546',receivedInk:'#F1F5F9',headingDark:'#22D3EE',headingLight:'#0E7490'};
 const variables={bubble:'bubble',ink:'ink',received:'received','received-ink':'receivedInk','heading-dark':'headingDark','heading-light':'headingLight'};
 const clearTint='linear-gradient(transparent,transparent)';
 function mix(hex,base,amount){hex=/^#[0-9a-f]{6}$/i.test(hex)?hex:'#202546';return '#'+[1,3,5].map(i=>Math.round(parseInt(hex.slice(i,i+2),16)*amount+base*(1-amount)).toString(16).padStart(2,'0')).join('')}
 function wallpaperTint(p,bright){if(p.id===fallback.id)return clearTint;const colors=bright?[mix(p.bubble,255,.32),mix(p.received,255,.42),mix(p.received,255,.18)]:[mix(p.bubble,0,.72),mix(p.received,0,.65),mix(p.received,0,.2)];return 'linear-gradient(180deg,'+colors[0]+','+colors[1]+' 56%,'+colors[2]+')'}
 function bridge(){return typeof GuardianGaming!=='undefined'?GuardianGaming:typeof GuardianWallet!=='undefined'?GuardianWallet:null}
 function account(){try{const native=bridge();return native?JSON.parse(native.session()):JSON.parse(localStorage.getItem('guardianchat-account')||'null')}catch(_){return null}}
 function apply(p){p=p?.roles===2?p:fallback;for(const [css,key] of Object.entries(variables))document.documentElement.style.setProperty('--personal-'+css,p[key]||fallback[key]);for(const bright of [false,true])document.documentElement.style.setProperty('--personal-wallpaper-'+(bright?'light':'dark'),wallpaperTint(p,bright));document.documentElement.dataset.palette=p.id}
 function cached(id){try{const native=bridge();if(native&&typeof native.palette==='function')return JSON.parse(native.palette());return JSON.parse(localStorage.getItem('xorbit-palette-'+id))}catch(_){return null}}
 function selected(){return choices.find(p=>p.id===(draft||document.documentElement.dataset.palette))}
 function preview(p){
  const scene=document.getElementById('paletteScene');if(!scene||!p)return;
  scene.dataset.mode=previewBright?'bright':'dark';
  scene.style.setProperty('--preview-tint',wallpaperTint(p,previewBright));
  scene.style.setProperty('--preview-art','url("/branding/'+(previewBright?'orbit-wallpaper-v2.png':'orbit-wallpaper.png')+'?v=19")');
  document.getElementById('palettePreviewHeading').style.color=p[previewBright?'headingLight':'headingDark']||fallback[previewBright?'headingLight':'headingDark'];
  for(const [id,first] of [['sentPreview',true],['receivedPreview',false]]){const e=document.getElementById(id);e.style.backgroundColor=first?p.bubble:p.received;e.style.color=first?p.ink:p.receivedInk}
  for(const [id,bright] of [['paletteDark',false],['paletteLight',true]])document.getElementById(id).setAttribute('aria-pressed',String(previewBright===bright));
 }
 function choose(id){if(busy||!owner||!choices.some(p=>p.id===id))return;draft=id;document.getElementById('paletteStatus').textContent='Preview only — press Select to apply.';render()}
 function render(){
  const list=document.getElementById('paletteOptions');if(!list)return;
  const signature=choices.map(p=>p.id).join('|');
  if(list.dataset.choices!==signature){
   list.dataset.choices=signature;list.replaceChildren();
   for(const p of choices){
    const option=document.createElement('button');option.type='button';option.className='palette-option';option.dataset.palette=p.id;option.setAttribute('role','radio');
    const swatch=document.createElement('span');swatch.className='pair-swatch';swatch.setAttribute('aria-hidden','true');swatch.style.background='linear-gradient(90deg,'+p.bubble+' 50%,'+p.received+' 50%)';
    const label=document.createElement('span');label.className='palette-label';label.textContent=p.name;
    const mark=document.createElement('span');mark.className='pair-selected-mark';mark.setAttribute('aria-hidden','true');mark.textContent='✓';
    option.append(swatch,label,mark);option.onclick=()=>choose(p.id);list.append(option);
   }
  }
  const p=selected();
  for(const option of list.children){const checked=option.dataset.palette===p?.id;option.setAttribute('aria-checked',String(checked));option.tabIndex=checked?0:-1;option.disabled=!owner||busy}
  const save=document.getElementById('savePalette'),unchanged=p?.id===document.documentElement.dataset.palette;
  save.disabled=!owner||busy||!p||unchanged;save.textContent=busy?'Selecting…':unchanged?'Selected':'Select';
  document.getElementById('closePalette').disabled=busy;preview(p);
 }
 async function refresh(force=false){
  const a=account(),next=a?.id||'';
  if(next!==owner||a?.token!==session){owner=next;session=a?.token||'';generation++;busy=false;draft=null;choices=[];const dialog=document.getElementById('personalizationDialog');if(dialog?.open)dialog.close();apply(owner?cached(owner):null);render();lastFetch=0}
  if(!owner||busy||(!force&&Date.now()-lastFetch<30000))return;
  lastFetch=Date.now();const g=generation,uid=owner,token=session;
  try{const r=await fetch('/preferences',{headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error();const data=await r.json();if(g!==generation||account()?.id!==uid||account()?.token!==token)return;choices=data.choices;const p=choices.find(p=>p.id===data.palette);if(!p)return;localStorage.setItem('xorbit-palette-'+uid,JSON.stringify(p));apply(p);render()}catch(_){/* Offline: retain only this account's saved pair. */}
 }
 async function save(){
  const a=account(),status=document.getElementById('paletteStatus'),p=selected();if(!a||a.id!==owner||a.token!==session||busy||!p||p.id===document.documentElement.dataset.palette)return;
  const uid=owner,token=session,g=++generation;busy=true;render();status.textContent='Selecting…';
  try{const r=await fetch('/preferences',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({palette:p.id})});if(!r.ok)throw Error('Could not save. Your current colours are unchanged. Try again.');const data=await r.json();if(g!==generation||account()?.id!==uid||account()?.token!==token)return;choices=data.choices;const saved=choices.find(p=>p.id===data.palette);if(!saved)throw Error('The selected pair is unavailable. Try again.');localStorage.setItem('xorbit-palette-'+uid,JSON.stringify(saved));draft=null;apply(saved);status.textContent=saved.name+' selected for your account.'}catch(e){if(g===generation)status.textContent=e.message}finally{if(g===generation){busy=false;render()}}
 }
 function mount(){
  const settings=document.getElementById('settingsPanel');if(!settings)return;
  const button=document.createElement('button');button.id='openPersonalization';button.type='button';button.textContent='Personalization';button.title='Preview and select a colour pair with its matching wallpaper';settings.insertBefore(button,settings.querySelector('label[for=appearance]'));
  const dialog=document.createElement('dialog');dialog.id='personalizationDialog';dialog.setAttribute('aria-label','Personalization');
  dialog.innerHTML='<h2>Choose your colour pair</h2><p>Left half: sent messages and selected tabs. Right half: received messages and faded inactive tabs.<br>Preview a pair, then press Select to save it.</p><div class="palette-mode" role="group" aria-label="Wallpaper preview appearance"><button type="button" id="paletteDark">Dark preview</button><button type="button" id="paletteLight">Light preview</button></div><div id="paletteScene" class="palette-scene"><strong id="palettePreviewHeading">OrbitChat · OrbitPlay</strong><div class="palette-preview received-preview" id="receivedPreview">A message for you</div><div class="palette-preview sent-preview" id="sentPreview">Your reply</div></div><div id="paletteOptions" role="radiogroup" aria-label="Colour pairs"></div><p id="paletteStatus" role="status"></p><div class="palette-footer"><button type="button" id="closePalette">Close</button><button type="button" id="savePalette" class="orbit-primary">Select</button></div>';
  document.body.append(dialog);
  button.onclick=()=>{draft=null;previewBright=document.documentElement.dataset.theme==='bright';document.getElementById('paletteStatus').textContent='';dialog.showModal();render();refresh(true)};
  dialog.onclose=()=>{draft=null};dialog.addEventListener('cancel',e=>{if(busy)e.preventDefault()});
  document.getElementById('savePalette').onclick=save;document.getElementById('closePalette').onclick=()=>dialog.close();
  for(const [id,bright] of [['paletteDark',false],['paletteLight',true]])document.getElementById(id).onclick=()=>{previewBright=bright;preview(selected())};
  document.getElementById('paletteOptions').onkeydown=e=>{const directions={ArrowDown:1,ArrowRight:1,ArrowUp:-1,ArrowLeft:-1};if(busy||(!directions[e.key]&&!['Home','End'].includes(e.key)))return;e.preventDefault();const current=choices.findIndex(p=>p.id===selected()?.id),index=e.key==='Home'?0:e.key==='End'?choices.length-1:(current+directions[e.key]+choices.length)%choices.length;if(index<0||!choices[index])return;choose(choices[index].id);document.getElementById('paletteOptions').children[index].focus()};
 }
 // Apply this account's saved appearance before any stylesheet or body can paint.
 try{const native=bridge();if(native)document.documentElement.classList?.add('orbit-native');if(native&&typeof native.moduleTabs==='function'&&native.moduleTabs())document.documentElement.classList?.add('native-module-shell');document.documentElement.dataset.theme=native&&typeof native.appearance==='function'?native.appearance():localStorage.getItem('guardianchat-theme')==='bright'?'bright':'dark'}catch(_){}
 const initial=account();apply(initial?cached(initial.id):null);
 window.OrbitPersonalization={refresh};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{mount();refresh(true)});else{mount();refresh(true)}
 setInterval(()=>refresh(),2000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh(true)});window.addEventListener('storage',()=>refresh(true));
})();
