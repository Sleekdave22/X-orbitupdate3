"""Additive, persistent Market pilot. Legacy advert routes remain supported."""
import base64, hashlib, io, json, re, time, uuid
from decimal import Decimal, InvalidOperation
from PIL import Image, ImageOps

CATEGORIES = [
 ('electronics','📱','Electronics',['Phones','Audio','Cameras'],['brand','model','storage','color']),
 ('vehicles','🚗','Vehicles',['Cars','Motorcycles','Parts'],['make','model','year','mileage','transmission']),
 ('property','🏠','Property',['Sale','Rent','Land'],['property_type','bedrooms','pricing_basis']),
 ('fashion','👕','Fashion',['Clothing','Shoes','Accessories'],['brand','size','color']),
 ('home','🛋️','Home & Furniture',['Furniture','Appliances','Decor'],['brand','material','dimensions']),
 ('beauty','💄','Beauty',['Skincare','Hair','Fragrance'],['brand','product_type']),
 ('tools','🧰','Tools & Equipment',['Tools','Industrial','Agriculture'],['brand','model']),
 ('sports-gaming','⚽','Sports & Gaming',['Gaming','Sports','Fitness'],['brand','model','platform']),
 ('computers','💻','Computers',['Laptops','Desktops','Components'],['brand','model','storage','memory']),
 ('baby-kids','👶','Baby & Kids',['Clothing','Toys','Equipment'],['age_range','brand']),
 ('services','🔧','Services',['Repairs','Professional','Creative'],['service_area','pricing_basis']),
 ('other','📦','Other',['General'],['brand','model'])]
LEGACY={'Gaming':'sports-gaming','Devices & accessories':'electronics','Fashion':'fashion','Food':'other','Services':'services','Digital':'other','Other':'other'}
STATES={'DRAFT','PENDING_REVIEW','ACTIVE','PAUSED','RESERVED','SOLD','REMOVED'}
CONDITIONS={'new','used','refurbished','not_applicable'}
CURRENCIES={'NGN','USD','EUR','GBP','CAD','AUD','GHS','KES','ZAR','INR','JPY','AED','CNY','BRL'}
# ISO 3166 alpha-2, independent of the device's network region.
COUNTRIES=set('AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split())

def init(server):
 with server.db() as d:
  d.executescript('''
  CREATE TABLE IF NOT EXISTS market_categories(id TEXT PRIMARY KEY,name TEXT NOT NULL,icon TEXT NOT NULL,subcategories TEXT NOT NULL,attributes TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS market_seller_meta(uid TEXT PRIMARY KEY,country TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '',restricted INTEGER NOT NULL DEFAULT 0,reason TEXT NOT NULL DEFAULT '');
  CREATE TABLE IF NOT EXISTS market_listing_meta(id TEXT PRIMARY KEY,category_id TEXT NOT NULL,subcategory TEXT NOT NULL DEFAULT '',amount_minor INTEGER,currency TEXT NOT NULL DEFAULT '',condition TEXT NOT NULL DEFAULT '',country TEXT NOT NULL DEFAULT '',city TEXT NOT NULL DEFAULT '',attributes TEXT NOT NULL DEFAULT '{}',delivery TEXT NOT NULL DEFAULT '[]',availability TEXT NOT NULL DEFAULT 'in_stock',state TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,updated INTEGER NOT NULL,featured INTEGER NOT NULL DEFAULT 0);
  CREATE INDEX IF NOT EXISTS market_listing_meta_category ON market_listing_meta(category_id,state);
  CREATE TABLE IF NOT EXISTS market_images(id TEXT PRIMARY KEY,listing TEXT NOT NULL,mime TEXT NOT NULL,data BLOB NOT NULL,position INTEGER NOT NULL);
  CREATE INDEX IF NOT EXISTS market_images_listing ON market_images(listing,position);
  CREATE TABLE IF NOT EXISTS market_listing_audit(id INTEGER PRIMARY KEY,listing TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,created INTEGER NOT NULL,revision INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS market_pilot_keys(uid TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,listing TEXT NOT NULL,PRIMARY KEY(uid,key));
  CREATE TABLE IF NOT EXISTS market_seller_reports(seller TEXT NOT NULL,reporter TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(seller,reporter));
  ''')
  if 'delivery_regions' not in {r[1] for r in d.execute('PRAGMA table_info(market_listing_meta)')}:
   d.execute("ALTER TABLE market_listing_meta ADD COLUMN delivery_regions TEXT NOT NULL DEFAULT '[]'")
  for ident,icon,name,subs,attrs in CATEGORIES:
   d.execute('INSERT OR IGNORE INTO market_categories(id,name,icon,subcategories,attributes) VALUES(?,?,?,?,?)',(ident,name,icon,json.dumps(subs),json.dumps(attrs)))
 __import__('market_search').init(server)
 __import__('market_connections').init(server)
 __import__('market_demo').init(server)
 __import__('market_admin').init(server)
 __import__('market_demand').init(server)

def catalog(d,all=False):
 return [dict(r)|{'subcategories':json.loads(r['subcategories']),'attributes':json.loads(r['attributes'])} for r in d.execute('SELECT * FROM market_categories'+('' if all else ' WHERE enabled=1')+' ORDER BY rowid')]

def text(value,maximum=200,required=False):
 if not isinstance(value,str):raise ValueError('Text fields must contain text')
 value=re.sub(r'\s+',' ',value).strip()
 if len(value)>maximum or required and not value:raise ValueError('Check required fields and their length')
 return value

def seller(d,uid):
 from market import account_of
 r=account_of(d,uid)
 if not r:raise ValueError('Open your existing account’s shop first')
 meta=d.execute('SELECT * FROM market_seller_meta WHERE uid=?',(uid,)).fetchone()
 if meta and meta['restricted']:raise ValueError('Selling is restricted. Contact Market moderation.')
 return r

def row(d,ident):
 from market import BASE
 r=d.execute(BASE+'WHERE a.id=?',(ident,)).fetchone()
 if not r:raise ValueError('Listing no longer available')
 return r

def view(d,r,uid):
 from market import ad_view
 out=ad_view(r,uid);m=d.execute('SELECT * FROM market_listing_meta WHERE id=?',(r['id'],)).fetchone()
 out.update(dict(m) if m else {'category_id':LEGACY.get(r['category'],'other'),'subcategory':'','amount_minor':None,'currency':'','condition':'','country':'','city':'','availability':'in_stock','attributes':'{}','delivery':'[]','state':{'active':'ACTIVE','held':'PENDING_REVIEW','removed':'REMOVED'}.get(r['status'],'PAUSED'),'revision':0,'updated':r['created'],'featured':0})
 out['attributes']=json.loads(out['attributes']);out['delivery']=json.loads(out['delivery'])
 out['delivery_regions']=json.loads(out.get('delivery_regions','[]'))
 out['images']=[x['id'] for x in d.execute('SELECT id FROM market_images WHERE listing=? ORDER BY position',(r['id'],))]
 out['legacy']=m is None
 return out

def accessible(d,uid,ident,owner=False):
 r=row(d,ident);v=view(d,r,uid)
 if owner and r['uid']!=uid:raise ValueError('Only the listing owner may do that')
 restricted=d.execute('SELECT restricted FROM market_seller_meta WHERE uid=?',(r['uid'],)).fetchone()
 if r['uid']!=uid and (v['state'] not in ('ACTIVE','RESERVED','SOLD') or r['expires']<=int(time.time()) or restricted and restricted[0]):raise ValueError('Listing no longer available')
 return v

def amount(value,currency):
 if not isinstance(currency,str) or currency not in CURRENCIES:raise ValueError('Choose a supported currency')
 try:
  dec=Decimal(str(value));factor=1 if currency=='JPY' else 100;scaled=dec*factor
  if not dec.is_finite() or dec<0 or scaled!=scaled.to_integral_value() or scaled>10**14:raise ValueError()
  return int(scaled)
 except (InvalidOperation,ValueError,TypeError):raise ValueError('Enter a valid non-negative price in the selected currency')

def images_input(items):
 if not isinstance(items,list) or len(items)>6:raise ValueError('Use up to six product images')
 result=[]
 for item in items:
  try:
   if not isinstance(item,dict) or len(item.get('data',''))>4*1024*1024:raise ValueError()
   raw=base64.b64decode(item['data'],validate=True)
   if len(raw)>3*1024*1024:raise ValueError()
   with Image.open(io.BytesIO(raw)) as im:
    if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>20_000_000 or getattr(im,'n_frames',1)!=1:raise ValueError()
    im.load();im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1600,1600));out=io.BytesIO();im.save(out,'JPEG',quality=86)
   result.append(out.getvalue())
  except Exception:raise ValueError('Use valid JPG, PNG or WebP photographs under 3 MB and 20 megapixels')
 return result

def notify(d,uid,event,listing,message):
 import account_notifications
 if not __import__('market_admin').settings(d)['notifications_enabled']:return
 account_notifications.add(d,uid,'market','shop',message,{'listing':listing,'event':event})
 for saved in d.execute('SELECT uid FROM market_saves WHERE listing=? AND uid<>?',(listing,uid)):
  account_notifications.add(d,saved['uid'],'market','saved','Saved item changed: '+message,{'listing':listing,'event':'saved_changed'})

def get(server,uid,path,q):
 arg=lambda n,default='':q.get(n,[default])[0]
 with server.db() as d:
  if path=='/market/catalog':return {'categories':catalog(d),'currencies':sorted(CURRENCIES),'conditions':sorted(CONDITIONS),'max_images':6,'discovery':dict(d.execute('SELECT * FROM market_discovery WHERE uid=?',(uid,)).fetchone() or {})}
  if path=='/market/listing':return {'listing':accessible(d,uid,arg('id'))}
  if path=='/market/image':
   image=d.execute('SELECT * FROM market_images WHERE id=?',(arg('id'),)).fetchone()
   if not image:raise ValueError('Image unavailable')
   accessible(d,uid,image['listing']);return {'mime':image['mime'],'data':base64.b64encode(image['data']).decode()}
  if path in ('/market/listings','/market/mine'):
   from market import BASE
   where='WHERE a.uid=? AND a.status!=\'removed\'' if path.endswith('/mine') else "WHERE a.status='active' AND a.expires>? AND NOT EXISTS(SELECT 1 FROM market_seller_meta s WHERE s.uid=a.uid AND s.restricted=1)"
   params=[uid] if path.endswith('/mine') else [int(time.time())]
   rows=d.execute(BASE+where+' ORDER BY a.created DESC,a.id DESC',params).fetchall()
   items=[view(d,r,uid) for r in rows]
   if path=='/market/listings':return __import__('market_search').search(d,uid,items,q)
   offset=max(0,min(100000,int(arg('offset','0'))));return {'listings':items[offset:offset+20],'more':len(items)>offset+20,'total':len(items)}
  if path=='/market/store':
   target=arg('id');r=d.execute('SELECT m.shop_name,m.about,u.id,u.name,u.nickname,u.avatar,u.avatar_mime FROM market_accounts m JOIN users u ON u.id=m.uid WHERE m.uid=?',(target,)).fetchone()
   if not r:raise ValueError('Store unavailable')
   meta=d.execute('SELECT country,city,restricted FROM market_seller_meta WHERE uid=?',(target,)).fetchone()
   if meta and meta['restricted'] and uid!=target:raise ValueError('Store unavailable')
   from market import BASE
   listings=[view(d,a,uid) for a in d.execute(BASE+'WHERE a.uid=? AND a.status!=\'removed\' ORDER BY a.created DESC',(target,))]
   if uid!=target:listings=[v for v in listings if v['state'] in ('ACTIVE','RESERVED','SOLD') and v['expires']>int(time.time())]
   return {'seller':dict(r)|dict(meta or {})|{'verified':False,'reviews':None},'listings':listings,'mine':target==uid}
 raise ValueError('Unknown Market pilot route')

def post(server,uid,action,b):
 if action=='search_preferences':return __import__('market_search').save_preferences(server,uid,b)
 now=int(time.time())
 if action=='save_listing':
  # Decode images before acquiring the write lock; never store undecoded source bytes.
  photos=images_input(b['images']) if 'images' in b else None
  fingerprint=hashlib.sha256(json.dumps(b,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with server.db() as d:
   d.execute('BEGIN IMMEDIATE');seller(d,uid);ident=text(b.get('id',''),40);key=text(b.get('client_id',''),80,not ident)
   if not ident:
    prior=d.execute('SELECT * FROM market_pilot_keys WHERE uid=? AND key=?',(uid,key)).fetchone()
    if prior:
     if prior['fingerprint']!=fingerprint:raise ValueError('Retry key already used for different content')
     return {'ok':True,'id':prior['listing'],'already_saved':True}
   old=accessible(d,uid,ident,True) if ident else None
   if old and old['state'] in ('REMOVED','RESERVED','SOLD','PENDING_REVIEW'):raise ValueError('This listing cannot be edited in its current state')
   if old and b.get('revision')!=old['revision']:raise ValueError('Listing changed. Reopen it before editing.')
   title=text(b.get('title',''),80,True);description=text(b.get('description',''),3000,True);category=b.get('category_id')
   if not isinstance(category,str):raise ValueError('Choose a category')
   cat=d.execute('SELECT * FROM market_categories WHERE id=? AND enabled=1',(category,)).fetchone()
   if not cat:raise ValueError('Choose a category')
   sub=text(b.get('subcategory',''),80,True)
   if sub not in json.loads(cat['subcategories']):raise ValueError('Choose a subcategory')
   currency=b.get('currency');minor=amount(b.get('price'),currency);condition=b.get('condition');country=b.get('country');city=text(b.get('city',''),100,True)
   if not isinstance(country,str) or not isinstance(condition,str) or country not in COUNTRIES or condition not in CONDITIONS:raise ValueError('Choose a country and condition')
   attrs=b.get('attributes',{});delivery=b.get('delivery',[]);availability=b.get('availability','in_stock')
   if not isinstance(attrs,dict) or set(attrs)-set(json.loads(cat['attributes'])):raise ValueError('Unsupported category attributes')
   attrs={k:text(v,100) for k,v in attrs.items()}
   if not isinstance(delivery,list) or not delivery or len(delivery)>3 or any(x not in ('pickup','local_delivery','shipping') for x in delivery):raise ValueError('Choose delivery or pickup options')
   regions=b.get('delivery_regions',[country])
   if not isinstance(regions,list) or len(regions)>30 or any(not isinstance(c,str) or c not in COUNTRIES for c in regions):raise ValueError('Use supported two-letter delivery country codes')
   if 'shipping' in delivery and not regions:raise ValueError('Specify supported shipping countries')
   if availability not in ('in_stock','made_to_order','unavailable'):raise ValueError('Choose availability')
   state=b.get('state','DRAFT');config=__import__('market_admin').settings(d)
   if state not in ('DRAFT','ACTIVE','PAUSED'):raise ValueError('Choose draft, publish or paused')
   existing_count=d.execute('SELECT count(*) FROM market_images WHERE listing=?',(ident,)).fetchone()[0] if ident else 0
   if state=='ACTIVE' and not (photos if photos is not None else existing_count):raise ValueError('Add at least one product photograph to publish')
   if state=='ACTIVE' and (config['review_required'] or any(re.search(r'\b'+re.escape(term)+r'\b',title+' '+description,re.I) for term in config['prohibited_terms'])):state='PENDING_REVIEW'
   if not ident:
    from market import MAX_ACTIVE_ADS,MAX_NEW_ADS_PER_HOUR
    if d.execute("SELECT count(*) FROM market_ads WHERE uid=? AND status NOT IN ('removed','sold')",(uid,)).fetchone()[0]>=config['max_listings']:raise ValueError('Shop listing limit reached')
    if d.execute('SELECT count(*) FROM market_ads WHERE uid=? AND created>?',(uid,now-3600)).fetchone()[0]>=config['max_new_hour']:raise ValueError('Please slow down before posting more listings')
    if d.execute("SELECT id FROM market_ads WHERE uid=? AND lower(title)=lower(?) AND status NOT IN ('removed','sold')",(uid,title)).fetchone():raise ValueError('A listing with that title already exists. Edit it instead.')
    ident=uuid.uuid4().hex;d.execute('INSERT INTO market_ads(id,uid,title,description,category,price,created,expires,status) VALUES(?,?,?,?,?,?,?,?,?)',(ident,uid,title,description,cat['name'],str(b['price']),now,now+config['life_days']*86400,'held' if state=='PENDING_REVIEW' else state.lower()))
   else:d.execute('UPDATE market_ads SET title=?,description=?,category=?,price=?,status=? WHERE id=?',(title,description,cat['name'],str(b['price']),'held' if state=='PENDING_REVIEW' else state.lower(),ident))
   if state=='ACTIVE':d.execute('UPDATE market_ads SET expires=max(expires,?) WHERE id=?',(now+config['life_days']*86400,ident))
   revision=old['revision']+1 if old else 1
   d.execute('INSERT INTO market_listing_meta(id,category_id,subcategory,amount_minor,currency,condition,country,city,attributes,delivery,availability,state,revision,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET category_id=excluded.category_id,subcategory=excluded.subcategory,amount_minor=excluded.amount_minor,currency=excluded.currency,condition=excluded.condition,country=excluded.country,city=excluded.city,attributes=excluded.attributes,delivery=excluded.delivery,availability=excluded.availability,state=excluded.state,revision=excluded.revision,updated=excluded.updated',(ident,category,sub,minor,currency,condition,country,city,json.dumps(attrs),json.dumps(delivery),availability,state,revision,now))
   if photos is not None:
    d.execute('DELETE FROM market_images WHERE listing=?',(ident,))
    for pos,data in enumerate(photos):d.execute('INSERT INTO market_images VALUES(?,?,?,?,?)',(uuid.uuid4().hex,ident,'image/jpeg',data,pos))
   d.execute('INSERT INTO market_seller_meta(uid,country,city) VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET country=excluded.country,city=excluded.city',(uid,country,city))
   d.execute('UPDATE market_listing_meta SET delivery_regions=? WHERE id=?',(json.dumps(regions),ident))
   d.execute('INSERT INTO market_listing_audit(listing,actor,action,created,revision) VALUES(?,?,?,?,?)',(ident,uid,'save:'+state,now,revision))
   if not old:d.execute('INSERT INTO market_pilot_keys VALUES(?,?,?,?)',(uid,key,fingerprint,ident))
   if state=='ACTIVE' and (not old or old['state']!='ACTIVE'):notify(d,uid,'published',ident,'Your listing is published: '+title)
   elif state=='PENDING_REVIEW':notify(d,uid,'review',ident,'Listing waiting for moderation: '+title)
   elif old:notify(d,uid,'edited',ident,'Listing updated: '+title)
   return {'ok':True,'id':ident,'revision':revision}
 if action=='listing_state':
  with server.db() as d:
   d.execute('BEGIN IMMEDIATE');seller(d,uid);v=accessible(d,uid,b.get('id'),True);state=b.get('state')
   transitions={'DRAFT':{'ACTIVE','REMOVED'},'ACTIVE':{'PAUSED','SOLD','REMOVED'},'PAUSED':{'ACTIVE','REMOVED'},'SOLD':{'REMOVED'}}
   if b.get('revision')!=v['revision']:raise ValueError('Listing changed. Reopen it first.')
   if state not in transitions.get(v['state'],set()):raise ValueError('This state transition is not allowed')
   if state=='REMOVED' and b.get('confirmed') is not True:raise ValueError('Confirm removal')
   if state=='ACTIVE' and not v['legacy'] and not v['images']:raise ValueError('Add a product photograph first')
   config=__import__('market_admin').settings(d)
   if state=='ACTIVE' and (config['review_required'] or any(re.search(r'\b'+re.escape(term)+r'\b',v['title']+' '+v['description'],re.I) for term in config['prohibited_terms'])):state='PENDING_REVIEW'
   if v['legacy']:
    d.execute('INSERT INTO market_listing_meta(id,category_id,state,revision,updated) VALUES(?,?,?,?,?)',(v['id'],v['category_id'],state,1,now))
   else:d.execute('UPDATE market_listing_meta SET state=?,revision=revision+1,updated=? WHERE id=?',(state,now,v['id']))
   d.execute('UPDATE market_ads SET status=? WHERE id=?',('held' if state=='PENDING_REVIEW' else state.lower(),v['id']));d.execute('INSERT INTO market_listing_audit(listing,actor,action,created,revision) VALUES(?,?,?,?,?)',(v['id'],uid,state,now,v['revision']+1))
   if state=='ACTIVE':d.execute('UPDATE market_ads SET expires=max(expires,?) WHERE id=?',(now+config['life_days']*86400,v['id']))
   notify(d,uid,state.lower(),v['id'],'Listing '+state.lower()+': '+v['title']);return {'ok':True}
 if action=='report_seller':
  with server.db() as d:
   if b.get('id')==uid or not d.execute('SELECT 1 FROM market_accounts WHERE uid=?',(b.get('id'),)).fetchone():raise ValueError('Choose another seller')
   d.execute('INSERT OR IGNORE INTO market_seller_reports VALUES(?,?,?,?)',(b['id'],uid,text(b.get('reason',''),500,True),now));return {'ok':True}
 raise ValueError('Unknown Market pilot action')
