/* Conditional listing controls use the existing form, buttons and conversation. */
window.OrbitMarketTypes={
 labels:{PRODUCT:'Product',SERVICE:'Service',SKILL:'Skill / Expertise',JOB:'Job / Employment'},
 modes:{fixed:'Fixed price',starting_from:'Starting from',hourly:'Hourly rate',negotiable:'Negotiable',quote:'Request quotation',contact:'Contact for pricing',opportunities:'Contact for opportunities',offers:'Open to offers',for_hire:'Available for hire',not_disclosed:'Salary not disclosed',fixed_salary:'Salary',salary_range:'Salary range'},
 numeric:new Set(['fixed','starting_from','hourly','fixed_salary','salary_range']),
 locate(lat,lon,status){
  if(!navigator.geolocation){status.textContent='Location is unavailable. Search by country and city instead.';return}
  status.textContent='Waiting for location permission…';navigator.geolocation.getCurrentPosition(p=>{lat.value=p.coords.latitude.toFixed(2);lon.value=p.coords.longitude.toFixed(2);status.textContent='Approximate location ready (about 1 km precision).'},()=>{status.textContent='Location was not shared. You can still search by country and city.'},{enableHighAccuracy:false,timeout:12000,maximumAge:300000});
 },
 money(value,currency){return new Intl.NumberFormat(undefined,{style:'currency',currency}).format(value/(currency==='JPY'?1:100))},
 price(a){
  if(!a.listing_type||a.pricing_mode==='legacy')return a.amount_minor==null?(a.price||'Price on request'):this.money(a.amount_minor,a.currency);
  const mode=a.pricing_mode;
  if(a.amount_minor==null)return this.modes[mode]||'Contact for details';
  const money=this.money(a.amount_minor,a.currency);
  return mode==='starting_from'?'Starting from '+money:mode==='hourly'?money+' / hour':mode==='salary_range'?money+' – '+this.money(a.type_details.salary_max_minor,a.currency):mode==='fixed_salary'?'Salary: '+money:money;
 },
 async application(a){
  try{const url=new URL(a.type_details?.application_url);if(url.protocol!=='https:'||url.username||url.password)throw Error();if(native&&GuardianGaming.openLink)GuardianGaming.openLink(url.href);else window.open(url.href,'_blank','noopener,noreferrer');say('Application website opened. Follow the employer’s instructions; no application has been submitted by Orbit.')}catch{say('Application website is unavailable')}
 },
 fields(f,a){
  const type=select(f,'What would you like to advertise?','listing_type',catalog.listing_types,a?.listing_type||'PRODUCT');
  const mode=select(f,'Pricing / salary mode','pricing_mode',[],null),extra=node('div','','listing-type-fields');f.append(extra);
  const detailsByType={[a?.listing_type||'PRODUCT']:{...a?.type_details}},controls={};
  function remember(){if(!extra.dataset.kind)return;detailsByType[extra.dataset.kind]=Object.fromEntries([...extra.querySelectorAll('[data-type-field]')].map(i=>[i.name,i.value]))}
  function extras(){const kind=type.value,d=detailsByType[kind]||{};extra.replaceChildren();extra.dataset.kind=kind;
   const add=(label,name,options=null,required=false)=>{const i=options?select(extra,label,name,options,d[name]):field(extra,label,name,d[name]||'',name==='application_instructions'||name==='required_skills'?'textarea':'input',name==='application_instructions'||name==='required_skills'?1500:500);i.dataset.typeField='1';i.required=required;return i};
   if(kind!=='PRODUCT')add('Work location','work_mode',[{id:'local',name:'Local'},{id:'remote',name:'Remote'},{id:'hybrid',name:'Hybrid'}]);
   if(kind==='SERVICE'){add('Experience','experience');add('Qualifications (optional)','qualifications')}
   if(kind==='SKILL'){add('Specialization','specialization');add('Experience level','experience');add('Certifications (optional)','certifications');add('Availability for work','work_availability',[{id:'available',name:'Available'},{id:'limited',name:'Limited availability'},{id:'unavailable',name:'Currently unavailable'}])}
   if(kind==='JOB'){add('Employer / business','employer',null,true);add('Employment type','employment_type',['full_time','part_time','contract','freelance','internship','temporary'],true);add('Required skills','required_skills');add('Experience requirements','experience');add('Application instructions','application_instructions',null,true);add('Application website (optional, HTTPS)','application_url').type='url';add('Application deadline (optional)','application_deadline').type='date'}
   extra.onchange=()=>controls.sync?.();
  }
  function modes(){const spec=catalog.listing_types.find(t=>t.id===type.value);mode.replaceChildren(...spec.pricing_modes.map(m=>{const o=node('option',m.name);o.value=m.id;return o}));mode.value=a?.listing_type===type.value&&spec.pricing_modes.some(m=>m.id===a.pricing_mode)?a.pricing_mode:spec.default_mode}
  modes();extras();
  type.onchange=()=>{remember();modes();extras();controls.sync?.(true)};mode.onchange=()=>controls.sync?.();
  return {type,mode,controls,details(){return Object.fromEntries([...extra.querySelectorAll('[data-type-field]')].map(i=>[i.name,i.value]))}};
 }
};
