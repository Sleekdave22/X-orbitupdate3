const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/personalization.js','utf8'),choices=JSON.parse(fs.readFileSync(__dirname+'/personalization.json','utf8'));
function boot({native=false,wallet=false,cached=true,owner='saved'}={}){
 const styles={},dataset={},classes=[],store=new Map(),selected=choices.find(p=>p.id==='green-pink');let requests=0;
 store.set('guardianchat-account',JSON.stringify({id:owner,token:'synthetic'}));store.set('guardianchat-theme','bright');if(cached)store.set('xorbit-palette-'+owner,JSON.stringify(selected));
 const context={JSON,Date,localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},window:{addEventListener(){}},document:{readyState:'loading',documentElement:{dataset,style:{setProperty:(k,v)=>styles[k]=v},classList:{add:n=>classes.push(n)}},getElementById:()=>null,addEventListener(){}},setInterval(){},fetch(){requests++;throw Error('Network must not be required for first paint')}};
 if(native||wallet)context[wallet?'GuardianWallet':'GuardianGaming']={session:()=>JSON.stringify({id:owner,token:'synthetic'}),palette:()=>JSON.stringify(selected),appearance:()=> 'bright',moduleTabs:()=>true};
 vm.createContext(context);vm.runInContext(source,context);return {styles,dataset,classes,requests};
}
for(const options of [{},{native:true,cached:false},{wallet:true,cached:false}]){const b=boot(options);assert.equal(b.styles['--personal-bubble'],'#1d7148');assert.equal(b.dataset.theme,'bright');assert.equal(b.requests,0);assert(!b.styles['--personal-wallpaper-dark'].includes('transparent'));}
const native=boot({native:true,cached:false});assert(native.classes.includes('native-module-shell'),'Native module shell must be selected before paint');
const missing=boot({cached:false,owner:'other'});assert.equal(missing.styles['--personal-bubble'],'#7C3AED','An account without a saved choice cannot inherit someone else’s theme');
for(const name of ['index.html','gaming.html','market.html','vibe.html','wallet.html']){const html=fs.readFileSync(__dirname+'/'+name,'utf8'),tag='<script src="/personalization.js"></script>';assert.equal(html.split(tag).length-1,1,name);assert(html.indexOf(tag)<html.indexOf('<link rel="stylesheet"'),name+' must apply saved appearance before styles');assert(!html.includes('defer src="/personalization.js"'));}
const chat=fs.readFileSync(__dirname+'/index.html','utf8');assert(chat.indexOf('id="homeBack"')<chat.indexOf('<h1>OrbitChat</h1>'));assert(chat.includes('<details id="chatSearch"'));assert(chat.includes('id="addContact"'));assert(chat.includes("search:el('chatSearch')"),'Published layout must move the whole Search control, never pull the form out');
console.log('Saved browser/native/wallet themes apply before DOM ready without network; header and collapsed Search contracts passed.');

const nativeSource=fs.readFileSync(__dirname+'/../chat/src/main/java/com/guardianlab/chat/MainActivity.kt','utf8');
assert(nativeSource.includes('private fun applyHomeOrder(root:LinearLayout){if(BuildConfig.COMPARISON_INTERFACE)return;'),'Legacy published order must not move Search above the fixed comparison module strip');
console.log('Fixed native module order overrides legacy published Search-first layouts.');
