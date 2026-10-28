"""Pilot lexical discovery. No remote model calls or approximate model numbers."""
import difflib,json,re,unicodedata
from collections import Counter
STOP=set('a an the i want to buy find looking for please me some of with and in near my cheap cheapest affordable budget'.split())
DEFAULT_SYNONYMS={'handset':'phone','mobile':'phone','cellphone':'phone','fone':'phone','notebook':'laptop','preowned':'used','secondhand':'used','grey':'gray','transmission':'gearbox','playstation':'ps','television':'tv','sofa':'couch','trainers':'sneakers'}

def init(server):
 with server.db() as d:
  d.executescript('''CREATE TABLE IF NOT EXISTS market_discovery(uid TEXT PRIMARY KEY,mode TEXT NOT NULL DEFAULT 'worldwide',country TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '');
  CREATE TABLE IF NOT EXISTS market_synonyms(term TEXT PRIMARY KEY,replacement TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS market_search_metrics(id INTEGER PRIMARY KEY,created INTEGER NOT NULL,query_terms INTEGER NOT NULL,results INTEGER NOT NULL,elapsed_ms INTEGER NOT NULL);
  ''')
  for k,v in DEFAULT_SYNONYMS.items():d.execute('INSERT OR IGNORE INTO market_synonyms VALUES(?,?)',(k,v))

def tokens(text):
 text=''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))
 # Storage units stay searchable as a number as well as a joined value.
 text=re.sub(r'\b(\d+)(gb|tb|mb)\b',r'\1 \2',text)
 return re.findall(r'[^\W_]+',text,flags=re.UNICODE)

def search(d,uid,items,q):
 arg=lambda n,default='':q.get(n,[default])[0]
 prefs=d.execute('SELECT * FROM market_discovery WHERE uid=?',(uid,)).fetchone()
 mode=arg('location',prefs['mode'] if prefs else 'worldwide');country=arg('country',prefs['country'] if prefs else '');city=arg('city',prefs['city'] if prefs else '')
 if mode not in ('near','country','worldwide','distance'):raise ValueError('Choose a valid location search')
 if mode in ('near','country') and not country or mode=='near' and not city:raise ValueError('Set your country and locality for this location search')
 if mode in ('near','country'):items=[v for v in items if v['country']==country]
 if mode=='near':items=[v for v in items if tokens(v['city'])==tokens(city)]
 items=__import__('market_location').refine(items,q,mode)
 if arg('category'):items=[v for v in items if v['category_id']==arg('category')]
 if arg('subcategory'):items=[v for v in items if v['subcategory']==arg('subcategory')]
 if arg('condition'):items=[v for v in items if v['condition']==arg('condition')]
 kind=arg('listing_type')
 if kind:
  if kind not in __import__('market_listing_types').TYPES:raise ValueError('Choose a valid listing type')
  items=[v for v in items if v['listing_type']==kind]
 currency=arg('currency')
 if currency:items=[v for v in items if v['currency']==currency]
 sort=arg('sort','relevance')
 if sort not in ('relevance','price_asc','price_desc','distance'):raise ValueError('Choose relevance, price order or nearest first')
 if sort.startswith('price_') and not currency and len({v['currency'] for v in items if v['amount_minor'] is not None})>1:raise ValueError('Choose one currency before sorting prices')
 if sort=='distance' and not arg('latitude'):raise ValueError('Choose your approximate location before sorting by distance')
 for key,operation in [('min_price',lambda a,b:a>=b),('max_price',lambda a,b:a<=b)]:
  if arg(key):
   if kind=='JOB':raise ValueError('Use salary filters for jobs')
   from market_pilot import amount
   threshold=amount(arg(key),currency);items=[v for v in items if v['listing_type']!='JOB' and v['amount_minor'] is not None and operation(v['amount_minor'],threshold)]
 for key,operation in [('min_salary',lambda a,b:a>=b),('max_salary',lambda a,b:a<=b)]:
  if arg(key):
   if kind!='JOB':raise ValueError('Choose Jobs to filter salaries')
   from market_pilot import amount
   threshold=amount(arg(key),currency);items=[v for v in items if v['amount_minor'] is not None and operation(v['type_details'].get('salary_max_minor',v['amount_minor']) if key=='min_salary' else v['amount_minor'],threshold)]
 synonyms={r['term']:r['replacement'] for r in d.execute('SELECT * FROM market_synonyms')}
 canonical=lambda word:synonyms.get(word,word)
 query=arg('q')[:120];terms=[canonical(t) for t in tokens(query) if t not in STOP][:16]
 docs=[];vocabulary=set()
 for item in items:
  weights=Counter()
  for field,mult in [(item['title'],4),(json.dumps(item['attributes'],ensure_ascii=False)+' '+json.dumps(item.get('type_details',{}),ensure_ascii=False),3),(item['description'],1),(item['category']+' '+item['subcategory']+' '+item['condition']+' '+item['shop_name']+' '+item['nickname']+' '+item['city']+' '+item.get('listing_type','PRODUCT')+' '+item.get('country',''),1)]:
   for word in tokens(field):weights[canonical(word)]+=mult
  docs.append((item,weights));vocabulary.update(weights)
 corrected=[];changes=[]
 for term in terms:
  replacement=term
  # Never fuzz years, storage, game generations or alphanumeric model numbers.
  if term not in vocabulary and len(term)>=4 and not any(c.isdigit() for c in term) and arg('original')!='1':
   matches=difflib.get_close_matches(term,sorted(w for w in vocabulary if not any(c.isdigit() for c in w)),n=1,cutoff=.82)
   if matches:replacement=matches[0];changes.append((term,replacement))
  corrected.append(replacement)
 exact=[];related=[];budget=bool(set(tokens(query))&{'cheap','cheapest','affordable','budget'})
 for item,weights in docs:
  hits=[t in weights for t in corrected];score=sum(min(12,weights[t]) for t in corrected if t in weights)
  numeric=[t for t in corrected if any(c.isdigit() for c in t)]
  if all(hits):exact.append((score,item))
  elif corrected and sum(hits)>=max(1,len(corrected)//2) and all(t in weights for t in numeric):related.append((score,item))
 def rank(pair):
  score,v=pair
  if sort.startswith('price_'):return (v['amount_minor'] is None,(v['amount_minor'] or 0)*(1 if sort=='price_asc' else -1),-score,-v['created'],v['id'])
  if sort=='distance':return (v['distance_km'] is None,v['distance_km'] or 0,-score,-v['created'],v['id'])
  return (-score,-int(v.get('featured',0)),v['amount_minor'] if budget and v['amount_minor'] is not None else 10**15,-v['created'],v['id'])
 exact.sort(key=rank);related.sort(key=rank);offset=max(0,min(100000,int(arg('offset','0'))))
 favorites={r[0] for r in d.execute('SELECT DISTINCT m.category_id FROM market_saves s JOIN market_listing_meta m ON m.id=s.listing WHERE s.uid=?',(uid,))}
 page=[v for _,v in exact[offset:offset+20]]
 recommendations=sorted(page,key=lambda v:(-int(v.get('featured',0)),-int(v['category_id'] in favorites),-v['created'],v['id']))[:4] if sort=='relevance' and not query and not arg('category') and not offset and len(page)>4 else []

 return {'listings':[v for _,v in exact[offset:offset+20]],'more':len(exact)>offset+20,'total':len(exact),'related':[v for _,v in related[:8]] if not exact else [],'interpretation':' '.join(corrected) if changes else None,'original_query':query,'location':{'mode':mode,'country':country,'city':city},'recommendations':recommendations,'recommendation_basis':'Featured listings, saved categories and recent discoveries','engine':'lexical-v1','semantic_enabled':False}

def save_preferences(server,uid,b):
 from market_pilot import COUNTRIES,text
 mode=b.get('mode');country=b.get('country','');city=text(b.get('city',''),100)
 if mode not in ('near','country','worldwide') or country and country not in COUNTRIES or mode!='worldwide' and country not in COUNTRIES or mode=='near' and not city:raise ValueError('Choose a location scope and valid country/locality')
 with server.db() as d:d.execute('INSERT INTO market_discovery VALUES(?,?,?,?) ON CONFLICT(uid) DO UPDATE SET mode=excluded.mode,country=excluded.country,city=excluded.city',(uid,mode,country,city))
 return {'ok':True}
