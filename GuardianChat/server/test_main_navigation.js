const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(__dirname+'/index.html','utf8'),nav=html.match(/<nav class="home-tabs orbit-bottom-nav"[\s\S]*?<\/nav>/)[0];
const tabs=[...nav.matchAll(/<button[^>]*id="([^"]+)"[\s\S]*?<\/button>/g)];
assert.deepEqual(tabs.map(x=>x[1]),['vibeTab','chatsTab','callsTab','profileTab']);
assert(tabs[0][0].includes('<span>Vibe</span>'));assert(tabs[0][0].includes('aria-label="Vibe"'));
assert(tabs.every(t=>t[0].includes('orbit-tab-artwork')));
for(const [i,icon] of ['vibe','chat','call','profile'].entries())assert(tabs[i][0].includes(`/navigation-icons/${icon}-icon.svg`));
assert(html.includes('id="gamingTab"'));assert(html.includes('id="marketTab"'));assert(!nav.includes('marketTab'));
assert(html.includes('<script src="/orbit-navigation.js?v=28"></script>'),'The shared navigation handlers must be loaded');
assert(html.includes('href="/navigation.css?v=28"'),'The fixed-bottom navigation stylesheet must be loaded');
for(const name of ['vibe-icon.svg','chat-icon.svg','call-icon.svg','profile-icon.svg','orbit-market-icon.svg'])assert.equal(fs.readFileSync(path.join(__dirname,'navigation-icons',name),'utf8'),fs.readFileSync(path.join(__dirname,'../chat/src/main/assets/navigation-icons',name),'utf8'));
const native=fs.readFileSync(__dirname+'/../chat/src/main/java/com/guardianlab/chat/MainActivity.kt','utf8');assert(native.includes('if(ownProfile)root.addView(homeTabs("profile"))'));assert(native.includes('if(page=="/vibe.html")root.addView(homeTabs("vibe").apply {tag="vibe-bottom-tabs"})'));
assert(fs.readFileSync(__dirname+'/vibe.html','utf8').includes('<span>Vibe</span>'));
assert(!native.includes('if(key!="vibe")addView(text(label,10f)'),'Native Vibe must display its label like the other tabs');
console.log('Four ordered tabs, supplied SVG parity, labelled accessible Vibe, retained upper Play/Market and native Profile/Vibe navigation passed.');

assert(html.includes('<body class="orbit-module-shell" data-orbit-module="chat">'),'Chat layout must be known before its first body paint');
assert(!fs.readFileSync(__dirname+'/orbit-navigation.js','utf8').includes('mainNavigation.style.width'),'Page content must not recalculate the four-tab width');
assert(fs.readFileSync(__dirname+'/vibe.html','utf8').includes('id="vibeSettingsButton"'),'Reserve Vibe settings in the initial header');
