"""Typed adverts extend existing listing metadata; IDs and legacy routes stay intact."""
import datetime
import ipaddress
import json
from urllib.parse import urlsplit

TYPES = {'PRODUCT': 'Products', 'SERVICE': 'Services', 'SKILL': 'Skills / Expertise', 'JOB': 'Jobs / Employment'}
MODES = {
 'PRODUCT': {'fixed': 'Fixed price', 'negotiable': 'Negotiable', 'contact': 'Contact for pricing'},
 'SERVICE': {'fixed': 'Fixed price', 'starting_from': 'Starting from', 'hourly': 'Hourly rate', 'negotiable': 'Negotiable', 'quote': 'Request quotation', 'contact': 'Contact for pricing'},
 'SKILL': {'opportunities': 'Contact for opportunities', 'offers': 'Open to offers', 'negotiable': 'Negotiable', 'for_hire': 'Available for hire', 'starting_from': 'Starting from'},
 'JOB': {'not_disclosed': 'Salary not disclosed', 'fixed_salary': 'Fixed salary', 'salary_range': 'Salary range', 'negotiable': 'Negotiable salary'}
}
DEFAULT = {'PRODUCT': 'fixed', 'SERVICE': 'contact', 'SKILL': 'opportunities', 'JOB': 'not_disclosed'}
NUMERIC = {'fixed', 'starting_from', 'hourly', 'fixed_salary', 'salary_range'}
FIELDS = {
 'PRODUCT': [],
 'SERVICE': ['work_mode', 'experience', 'qualifications'],
 'SKILL': ['specialization', 'experience', 'certifications', 'work_mode', 'work_availability'],
 'JOB': ['employer', 'employment_type', 'work_mode', 'required_skills', 'experience', 'application_instructions', 'application_url', 'application_deadline', 'salary_max_minor']
}
EMPLOYMENT = {'full_time', 'part_time', 'contract', 'freelance', 'internship', 'temporary'}

def init(d):
 columns={r[1] for r in d.execute('PRAGMA table_info(market_listing_meta)')}
 for name,definition in [('listing_type', "TEXT NOT NULL DEFAULT 'PRODUCT'"), ('pricing_mode', "TEXT NOT NULL DEFAULT 'fixed'"), ('type_details', "TEXT NOT NULL DEFAULT '{}' "),('latitude','REAL'),('longitude','REAL')]:
  if name not in columns:d.execute('ALTER TABLE market_listing_meta ADD COLUMN '+name+' '+definition)
 d.execute('CREATE INDEX IF NOT EXISTS market_listing_type ON market_listing_meta(listing_type,state)')

def catalog():
 return [{'id':kind,'name':name,'pricing_modes':[{'id':key,'name':value,'requires_amount':key in NUMERIC} for key,value in MODES[kind].items()],'default_mode':DEFAULT[kind]} for kind,name in TYPES.items()]

def application_url(value):
 """Only ordinary external HTTPS destinations; never executable or local URLs."""
 from market_pilot import text
 value=text(value,500)
 if not value:return ''
 try:
  u=urlsplit(value);host=(u.hostname or '').lower();port=u.port
  if u.scheme!='https' or not host or u.username or u.password or port not in (None,443) or any(c.isspace() or ord(c)<32 or c=='\\' for c in value):raise ValueError()
  if '.' not in host or host.endswith(('.localhost','.local','.internal')) or host.replace('.','').isdigit():raise ValueError()
  try:
   if not ipaddress.ip_address(host).is_global:raise ValueError('Local addresses are not allowed')
  except ValueError as e:
   if str(e)=='Local addresses are not allowed':raise
  return value
 except (ValueError,TypeError):raise ValueError('Use a valid external HTTPS application link')

def validate(b,old=None):
 from market_pilot import amount, text, CURRENCIES
 kind=b.get('listing_type',old['listing_type'] if old else 'PRODUCT')
 if not isinstance(kind,str) or kind not in TYPES:raise ValueError('Choose Product, Service, Skill or Job')
 mode=b.get('pricing_mode',old['pricing_mode'] if old and old['listing_type']==kind and old['pricing_mode']!='legacy' else DEFAULT[kind])
 if not isinstance(mode,str) or mode not in MODES[kind]:raise ValueError('Choose a pricing mode for this listing type')
 currency=b.get('currency','')
 if not isinstance(currency,str) or currency and currency not in CURRENCIES:raise ValueError('Choose a supported currency')
 raw=b.get('price');minor=amount(raw,currency) if mode in NUMERIC else None
 if mode not in NUMERIC and raw not in (None,''):raise ValueError('This pricing mode does not use an amount')
 details=b.get('type_details',{})
 if not isinstance(details,dict) or set(details)-set(FIELDS[kind]):raise ValueError('Unsupported fields for this listing type')
 details={k:text(v,1500 if k in ('application_instructions','required_skills') else 500) for k,v in details.items() if k!='salary_max_minor'}
 if kind!='PRODUCT':
  details.setdefault('work_mode','local')
  if details['work_mode'] not in ('local','remote','hybrid'):raise ValueError('Choose local, remote or hybrid work')
 if kind=='SKILL':
  details.setdefault('work_availability','available')
  if details['work_availability'] not in ('available','limited','unavailable'):raise ValueError('Choose availability for work')
 if kind=='JOB':
  if not details.get('employer') or details.get('employment_type') not in EMPLOYMENT or not details.get('application_instructions'):raise ValueError('Add employer, employment type and application instructions')
  details['application_url']=application_url(details.get('application_url',''))
  deadline=details.get('application_deadline','')
  if deadline:
   try:
    if datetime.date.fromisoformat(deadline).isoformat()!=deadline:raise ValueError()
   except ValueError:raise ValueError('Use an application deadline in YYYY-MM-DD format')
  if mode=='salary_range':
   high=amount(b.get('salary_max'),currency)
   if high<minor:raise ValueError('Maximum salary must not be below the minimum')
   details['salary_max_minor']=high
  elif b.get('salary_max') not in (None,''):raise ValueError('A maximum salary is only used for a salary range')
 return kind,mode,minor,currency,details

def extend(out):
 out.setdefault('listing_type','PRODUCT')
 out.setdefault('pricing_mode','legacy' if out['legacy'] else 'fixed')
 out['type_details']=json.loads(out.get('type_details','{}'))
 out['can_offer']=out['listing_type']=='PRODUCT' and out['amount_minor'] is not None
 out['application_open']=True
 deadline=out['type_details'].get('application_deadline')
 if out['listing_type']=='JOB' and deadline:out['application_open']=datetime.date.today()<=datetime.date.fromisoformat(deadline)
 return out
