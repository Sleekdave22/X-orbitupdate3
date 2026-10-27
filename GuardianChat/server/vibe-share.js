/* One explicit audience chooser for source references from Plaza and Play. */
(()=>{'use strict';
const el=(tag,text='')=>{const n=document.createElement(tag);n.textContent=text;return n};
window.OrbitVibeShare={async show(api,source,{prompt=false}={}){
 const dialog=el('dialog'),form=el('form'),title=el('h3',prompt?'Would you like to share this listing to your Vibe?':'Share to Vibe'),choice=el('select'),contacts=el('fieldset'),message=el('p'),actions=el('div'),submit=el('button','Share to Vibe'),cancel=el('button',prompt?'Not Now':'Cancel'),key=crypto.randomUUID();
 dialog.setAttribute('aria-label','Share to Vibe');form.dataset.formInline='1';choice.setAttribute('aria-label','Vibe audience');
 for(const [value,label] of [['','Choose Public or Private Vibe'],['public','Public Vibe'],['private','Private Vibe']]){const o=el('option',label);o.value=value;choice.append(o)}
 contacts.hidden=true;contacts.append(el('legend','Select private contacts'));actions.className='row';cancel.type='button';submit.type='submit';actions.append(submit,cancel);form.append(title,el('p','This share lasts 24 hours. The original content stays in place.'),choice,contacts,message,actions);dialog.append(form);document.body.append(dialog);
 const close=()=>{dialog.close();dialog.remove()};cancel.onclick=close;dialog.addEventListener('cancel',()=>dialog.remove());choice.onchange=()=>{contacts.hidden=choice.value!=='private'};
 try{const r=await api('/users');for(const u of r.users){const label=el('label'),box=el('input');box.type='checkbox';box.value=u.id;box.style.width='auto';label.append(box,el('span',u.name));contacts.append(label)}}catch(e){message.textContent=e.message}
 form.onsubmit=async event=>{event.preventDefault();if(!choice.value){message.textContent='Choose Public or Private Vibe';return}submit.disabled=true;choice.disabled=true;contacts.disabled=true;try{const r=await api('/vibe/share',{...source,visibility:choice.value,audience:[...contacts.querySelectorAll('input:checked')].map(x=>x.value),client_id:key});message.textContent=r.already_published?'Already shared · no duplicate created':'Shared to your Vibe';submit.hidden=true;cancel.textContent='Done'}catch(e){message.textContent=e.message;submit.disabled=false;choice.disabled=false;contacts.disabled=false}};
 dialog.showModal();return dialog;
}};
window.OrbitVibeReturn={
 save(account,item,visibility){sessionStorage.setItem('orbit-vibe-return',JSON.stringify({uid:account.id,origin:location.origin,item,visibility,created:Date.now()}))},
 get(account){try{const r=JSON.parse(sessionStorage.getItem('orbit-vibe-return')||'null');return r&&r.uid===account.id&&r.origin===location.origin&&Date.now()-r.created>=0&&Date.now()-r.created<86400000&&['public','private'].includes(r.visibility)&&/^[a-f0-9]{32}$/.test(r.item)?r:null}catch{return null}},
 url(account){const r=this.get(account);return r?'/vibe.html?item='+r.item+'&visibility='+r.visibility:'/vibe.html'},
 clear(){sessionStorage.removeItem('orbit-vibe-return')}
};
})();
