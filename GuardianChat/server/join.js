'use strict';
(()=>{
 const el=id=>document.getElementById(id),storageKey='guardianchat-account';
 const invite=new URLSearchParams(location.search).get('invite')||'';
 let valid=false,busy=false,checking=false,completed=false;
 const status=message=>{el('joinStatus').textContent=message};
 function currentAccount(){try{const value=JSON.parse(localStorage.getItem(storageKey)||'null');return value&&typeof value.id==='string'&&typeof value.token==='string'&&value.token?value:null}catch{return null}}
 function alreadySignedIn(message='You are already signed in to X ORBIT.'){
  valid=false;el('joinForm').hidden=true;el('joinFields').disabled=true;el('openOrbit').hidden=false;el('signInOrbit').hidden=true;el('existingHint').hidden=false;el('retryInvite').hidden=true;el('joinHeading').textContent='Already signed in';status(message);el('joinPassword').value=el('joinConfirm').value='';
 }
 function details(){return {name:el('joinName').value.trim(),nickname:el('joinNickname').value.trim().replace(/^@/,'').toLowerCase(),birth_date:el('joinBirth').value,sex:el('joinSex').value,password:el('joinPassword').value}}
 function validation(){const value=details();if(!value.birth_date)return 'Enter your date of birth.';if(!value.sex)return 'Choose male, female or prefer not to say.';if(!value.name||value.name.length>40)return 'Enter a display name of 1–40 characters.';if(!/^[a-z0-9_]{3,24}$/.test(value.nickname))return 'Use a nickname with 3–24 letters, numbers or underscores.';if(value.password.length<10||value.password.length>128)return 'Use a password with 10–128 characters.';if(value.password!==el('joinConfirm').value)return 'Passwords do not match.';return ''}
 function sync(){el('joinSubmit').disabled=!valid||busy||completed||!!validation();if(el('joinConfirm').value&&el('joinConfirm').value!==el('joinPassword').value)status('Passwords do not match.');else if(valid&&!busy&&!completed)status('Your invitation is ready. Create your account below.')}
 function toggle(id,button,label){const input=el(id),show=input.type==='password';input.type=show?'text':'password';button.textContent=show?'Hide':'Show';button.setAttribute('aria-pressed',String(show));button.setAttribute('aria-label',(show?'Hide ':'Show ')+label)}
 el('showJoinPassword').onclick=()=>toggle('joinPassword',el('showJoinPassword'),'password');el('showJoinConfirm').onclick=()=>toggle('joinConfirm',el('showJoinConfirm'),'confirm password');
 for(const id of ['joinName','joinNickname','joinBirth','joinSex','joinPassword','joinConfirm'])el(id).addEventListener('input',sync);
 document.documentElement.dataset.theme=(()=>{try{return localStorage.getItem('guardianchat-theme')==='bright'?'bright':'dark'}catch{return 'dark'}})();
 async function request(path,body){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);try{const response=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer',signal:controller.signal});let payload;try{payload=await response.json()}catch{throw Error('The server could not complete this request. Please try again.')}return {response,payload}}finally{clearTimeout(timer)}}
 async function checkInvitation(){
  if(checking||completed)return;if(currentAccount()){alreadySignedIn();return}checking=true;valid=false;el('joinForm').hidden=true;el('joinFields').disabled=true;el('retryInvite').hidden=true;status('Checking your invitation…');
  try{
   if(!invite||invite.length>512){status('This invitation is invalid or has expired. Ask for a new invitation link.');return}
   const {response,payload}=await request('/invitations/check?'+new URLSearchParams({invite}));
   if(currentAccount()){alreadySignedIn();return}
   if(!response.ok||payload.valid!==true){status('This invitation is invalid or has expired. Ask for a new invitation link.');return}
   valid=true;el('joinForm').hidden=false;el('joinFields').disabled=false;sync();
  }catch{status('The invitation could not be checked. Check your connection and try again.');el('retryInvite').hidden=false}finally{checking=false}
 }
 el('retryInvite').onclick=checkInvitation;
 el('joinForm').onsubmit=async event=>{
  event.preventDefault();if(busy||completed)return;if(currentAccount()){alreadySignedIn();return}if(!valid){status('Check a valid invitation before creating an account.');return}const error=validation();if(error){status(error);return}
  busy=true;el('joinFields').disabled=true;el('joinSubmit').disabled=true;el('joinSubmit').textContent='Creating account…';status('Creating your account…');let created=false;
  try{
   const {response,payload}=await request('/register',{...details(),invite_link:invite});
   if(!response.ok){if(response.status===401||response.status===403||response.status===400&&payload.error==='This sign-up invitation is invalid or has been replaced'){valid=false;el('joinForm').hidden=true;status('This invitation is invalid or has expired. Ask for a new invitation link.')}else status(typeof payload.error==='string'?payload.error.slice(0,240):'Your account could not be created. Check the details and try again.');return}
   if(!payload||typeof payload.id!=='string'||typeof payload.token!=='string'||!payload.token)throw Error('Invalid account response');created=true;completed=true;
   if(currentAccount()){alreadySignedIn('Your new account was created, but another account is now signed in here. Open X ORBIT, or sign in later with your new nickname and password.');return}
   const account={id:payload.id,name:payload.name,nickname:payload.nickname,token:payload.token};localStorage.setItem(storageKey,JSON.stringify(account));el('joinPassword').value=el('joinConfirm').value='';status('Account created. Opening X ORBIT…');location.replace('/');
  }catch{if(created){completed=true;el('joinForm').hidden=true;el('openOrbit').hidden=false;status('Your account was created, but this browser could not save your sign-in. Open X ORBIT and sign in with your nickname and password.')}else status('Sign-up could not finish. Check your connection and try again, or sign in if your account was already created.')}finally{busy=false;el('joinFields').disabled=!valid||completed;el('joinSubmit').textContent='Create account →';el('joinSubmit').disabled=!valid||completed||!!validation()}
 };
 window.addEventListener('storage',event=>{if(event.key===storageKey&&currentAccount())alreadySignedIn()});
 document.addEventListener('pointerdown',event=>{const button=event.target.closest('button');if(!button||button.disabled)return;button.classList.remove('pressed');void button.offsetWidth;button.classList.add('pressed');setTimeout(()=>button.classList.remove('pressed'),400)});
 checkInvitation();
})();
