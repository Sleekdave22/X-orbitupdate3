"""Role-gated Market configuration and read-only demo metrics in existing Studio."""
import json,re,time
from market_pilot import catalog,text
DEFAULTS={'max_listings':20,'max_new_hour':5,'life_days':30,'review_required':False,'notifications_enabled':True,'prohibited_terms':[]}

def init(server):
 with server.db() as d:d.executescript('''CREATE TABLE IF NOT EXISTS market_configuration(key TEXT PRIMARY KEY,value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS market_admin_audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL,reason TEXT NOT NULL,before_value TEXT NOT NULL,after_value TEXT NOT NULL,created INTEGER NOT NULL);
 ''')
def settings(d):return DEFAULTS|{r['key']:json.loads(r['value']) for r in d.execute('SELECT * FROM market_configuration')}
def audit(d,uid,action,target,reason,before,after):d.execute('INSERT INTO market_admin_audit(actor,action,target,reason,before_value,after_value,created) VALUES(?,?,?,?,?,?,?)',(uid,action,target,reason,json.dumps(before),json.dumps(after),int(time.time())))
def authorize(d,uid):
 from market import is_admin
 if not is_admin(d,uid):raise ValueError('Plaza administration is restricted')

def get(server,uid):
 with server.db() as d:
  authorize(d,uid)
  reports=[dict(r) for r in d.execute('SELECT r.ad,r.reason,r.created,a.title,a.status FROM market_reports r JOIN market_ads a ON a.id=r.ad ORDER BY r.created DESC LIMIT 100')]
  disputes=[__import__('market_demo').order_view(d,uid,r['id'],True) for r in d.execute("SELECT id FROM market_demo_orders WHERE state='DISPUTED' ORDER BY updated DESC LIMIT 100")]
  totals=[dict(r) for r in d.execute('SELECT j.currency,count(*) AS postings,coalesce(sum(p.amount),0) AS net FROM market_demo_postings p JOIN market_demo_journals j ON j.id=p.journal WHERE j.sealed=1 GROUP BY j.currency')]
  return {'categories':catalog(d,True),'config':settings(d),'synonyms':[dict(r) for r in d.execute('SELECT * FROM market_synonyms ORDER BY term')],'reports':reports,'seller_reports':[dict(r) for r in d.execute('SELECT * FROM market_seller_reports ORDER BY created DESC LIMIT 100')],'restrictions':[dict(r) for r in d.execute('SELECT uid,restricted,reason FROM market_seller_meta WHERE restricted=1')],'disputes':disputes,'demo_metrics':totals,'demo_journals':[dict(r) for r in d.execute('SELECT id,kind,currency,order_id,created FROM market_demo_journals WHERE sealed=1 ORDER BY created DESC LIMIT 100')],'audit':[dict(r) for r in d.execute('SELECT id,actor,action,target,reason,created FROM market_admin_audit ORDER BY id DESC LIMIT 100')],'simulation':True}

def post(server,uid,action,b):
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE');authorize(d,uid);reason=text(b.get('reason',''),500,True);target='market'
  if action=='admin_config':
   value=b.get('config')
   if not isinstance(value,dict) or set(value)!=set(DEFAULTS):raise ValueError('Supply the complete Market configuration')
   for key,low,high in [('max_listings',1,100),('max_new_hour',1,20),('life_days',1,90)]:
    if type(value[key])!=int or not low<=value[key]<=high:raise ValueError('Invalid Market limit')
   if any(type(value[k])!=bool for k in ('review_required','notifications_enabled')):raise ValueError('Choose valid notification and review settings')
   terms=value['prohibited_terms']
   if not isinstance(terms,list) or len(terms)>50 or any(not isinstance(t,str) or not 2<=len(t)<=40 for t in terms):raise ValueError('Use up to fifty moderation terms')
   before=settings(d)
   for key,v in value.items():d.execute('INSERT INTO market_configuration VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(v)))
   after=value
  elif action=='admin_category':
   target=text(b.get('id',''),40,True)
   if not re.fullmatch('[a-z][a-z0-9-]{1,39}',target):raise ValueError('Use a stable lowercase category ID')
   name=text(b.get('name',''),60,True);icon=text(b.get('icon',''),8,True);subs=b.get('subcategories');attrs=b.get('attributes');enabled=b.get('enabled')
   if not isinstance(subs,list) or not 1<=len(subs)<=30 or any(not isinstance(s,str) or not 1<=len(s)<=80 for s in subs) or len(set(subs))!=len(subs):raise ValueError('Use one to thirty unique subcategories')
   if not isinstance(attrs,list) or len(attrs)>20 or any(not isinstance(a,str) or not re.fullmatch('[a-z][a-z_]{0,31}',a) for a in attrs) or type(enabled)!=bool:raise ValueError('Check category attributes and availability')
   old=d.execute('SELECT * FROM market_categories WHERE id=?',(target,)).fetchone();before=dict(old) if old else None
   d.execute('INSERT INTO market_categories VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,icon=excluded.icon,subcategories=excluded.subcategories,attributes=excluded.attributes,enabled=excluded.enabled',(target,name,icon,json.dumps(subs),json.dumps(attrs),int(enabled)));after=b
  elif action=='admin_seller':
   target=text(b.get('uid',''),12,True);restricted=b.get('restricted')
   if type(restricted)!=bool or not d.execute('SELECT 1 FROM market_accounts WHERE uid=?',(target,)).fetchone():raise ValueError('Choose an existing seller and restriction state')
   old=d.execute('SELECT restricted,reason FROM market_seller_meta WHERE uid=?',(target,)).fetchone();before=dict(old) if old else None
   d.execute('INSERT INTO market_seller_meta(uid,restricted,reason) VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET restricted=excluded.restricted,reason=excluded.reason',(target,int(restricted),reason));after={'restricted':restricted}
  elif action=='admin_feature':
   target=text(b.get('id',''),32,True);featured=b.get('featured')
   old=d.execute('SELECT featured,state FROM market_listing_meta WHERE id=?',(target,)).fetchone()
   if not old or type(featured)!=bool or old['state']!='ACTIVE':raise ValueError('Choose an active structured listing')
   before=dict(old);d.execute('UPDATE market_listing_meta SET featured=? WHERE id=?',(int(featured),target));after={'featured':featured}
  elif action=='admin_synonym':
   from market_search import tokens
   target=text(b.get('term',''),40,True).lower();replacement=text(b.get('replacement',''),40).lower()
   if len(tokens(target))!=1 or replacement and len(tokens(replacement))!=1:raise ValueError('Use single-word synonym pairs; empty replacement removes the rule')
   old=d.execute('SELECT replacement FROM market_synonyms WHERE term=?',(target,)).fetchone();before=dict(old) if old else None
   if replacement:d.execute('INSERT INTO market_synonyms VALUES(?,?) ON CONFLICT(term) DO UPDATE SET replacement=excluded.replacement',(target,replacement))
   else:d.execute('DELETE FROM market_synonyms WHERE term=?',(target,))
   after={'replacement':replacement}
  else:raise ValueError('Unknown Market administrator action')
  audit(d,uid,action,target,reason,before,after);return {'ok':True}
