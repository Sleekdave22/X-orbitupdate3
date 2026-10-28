import datetime,json,time,unittest,urllib.error
from urllib.parse import urlencode
import market,market_listing_types as typed,test_market_pilot

class TypedMarketTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register;shop=test_market_pilot.MarketPilotTest.shop;save=test_market_pilot.MarketPilotTest.save;listing=test_market_pilot.MarketPilotTest.listing
 def body(self,kind='SKILL',**kw):
  b=dict(client_id='typed-'+str(time.time_ns()),listing_type=kind,title='Structural engineer '+kind,description='Structural engineer with building design experience',category_id='services',subcategory='Professional',country='NG',city='Lagos',currency='NGN',state='ACTIVE',attributes={},type_details={})
  if kind=='JOB':b['type_details']={'employer':'Example engineering','employment_type':'contract','work_mode':'remote','required_skills':'structural engineer','application_instructions':'Send your qualifications through Orbit Chat'}
  return b|kw
 def test_non_product_types_publish_without_price_photos_or_delivery(self):
  a=self.shop();b=self.register('Reader')
  for kind in ('SERVICE','SKILL','JOB'):
   ident=self.save(a,self.body(kind))['id'];v=self.listing(b,ident)
   self.assertEqual(v['listing_type'],kind);self.assertIsNone(v['amount_minor']);self.assertEqual(v['price'],'');self.assertEqual(v['images'],[]);self.assertEqual(v['delivery'],[]);self.assertFalse(v['can_offer'])
   with self.assertRaises(urllib.error.HTTPError):self.call('/market/listing_state',{'id':ident,'revision':1,'state':'SOLD'},a['token'])
  with self.server.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM fin_journals').fetchone()[0],0)
 def test_product_rules_and_existing_prices_are_preserved(self):
  a=self.shop();body=test_market_pilot.MarketPilotTest.body(self)
  for delta in ({'price':''},{'images':[]},{'delivery':[]}):
   with self.assertRaises(urllib.error.HTTPError):self.save(a,body|delta)
  i=self.save(a,body)['id'];v=self.listing(a,i);self.assertEqual(v['listing_type'],'PRODUCT');self.assertEqual(v['amount_minor'],12500050);self.assertTrue(v['can_offer'])
 def test_each_numeric_mode_requires_valid_amount_and_currency(self):
  a=self.shop()
  for kind,modes in typed.MODES.items():
   for mode in modes:
    if mode not in typed.NUMERIC:continue
    base=self.body(kind,pricing_mode=mode)
    for delta in ({},{'price':'NaN'},{'price':'-1'},{'price':'1.001'},{'price':'1','currency':'bad'}):
     with self.subTest(kind=kind,mode=mode,delta=delta):
      with self.assertRaises(urllib.error.HTTPError):self.save(a,base|delta)
  for kind in ('SERVICE','SKILL','JOB'):
   with self.assertRaises(urllib.error.HTTPError):self.save(a,self.body(kind,price='0'))
 def test_salary_range_and_external_application_validation(self):
  a=self.shop();base=self.body('JOB',pricing_mode='salary_range',price='1000',salary_max='2000');r=self.save(a,base);v=self.listing(a,r['id']);self.assertEqual(v['type_details']['salary_max_minor'],200000)
  for change in ({'salary_max':'999'},{'salary_max':'bad'},{'salary_max':None},{'type_details':base['type_details']|{'application_url':'javascript:alert(1)'}},{'type_details':base['type_details']|{'application_url':'https://localhost/x'}},{'type_details':base['type_details']|{'application_url':'https://user:pass@example.com/x'}},{'type_details':base['type_details']|{'application_url':'https://127.0.0.1/x'}},{'type_details':base['type_details']|{'application_deadline':'2026-02-30'}}):
   with self.assertRaises(urllib.error.HTTPError):self.save(a,base|change|{'title':str(time.time_ns()),'client_id':str(time.time_ns())})
  self.assertEqual(typed.application_url('https://example.com/apply'),'https://example.com/apply')
  for url in ('https://127.1/x','https://127.0.0.1/x','https://example.com:8080/x','https://example.com/\\bad'):
   with self.assertRaises(ValueError):typed.application_url(url)
 def test_updates_type_switching_ownership_and_revision(self):
  a=self.shop();b=self.register('Other');base=self.body();r=self.save(a,base);edit=base|{'id':r['id'],'revision':1,'listing_type':'SERVICE','pricing_mode':'hourly','price':'50','type_details':{'work_mode':'remote'},'city':''}
  with self.assertRaises(urllib.error.HTTPError):self.save(b,edit)
  self.save(a,edit);v=self.listing(a,r['id']);self.assertEqual(v['amount_minor'],5000);self.assertEqual(v['revision'],2)
  with self.assertRaises(urllib.error.HTTPError):self.save(a,edit)
  with self.assertRaises(urllib.error.HTTPError):self.save(a,edit|{'revision':2,'listing_type':'PRODUCT'})
  self.assertEqual(self.listing(a,r['id'])['listing_type'],'SERVICE')
 def test_type_search_cross_category_and_salary_filters(self):
  a=self.shop();expected={}
  for kind in ('SERVICE','SKILL','JOB'):expected[kind]=self.save(a,self.body(kind))['id']
  r=self.call('/market/listings?'+urlencode({'q':'Structural engineer'}),token=a['token']);self.assertEqual({v['id'] for v in r['listings']},set(expected.values()))
  for kind,ident in expected.items():self.assertEqual([v['id'] for v in self.call('/market/listings?listing_type='+kind,token=a['token'])['listings']],[ident])
  self.assertEqual(self.call('/market/listings?listing_type=JOB&currency=NGN&min_salary=1',token=a['token'])['total'],0)
  for query in ('listing_type=INVALID','listing_type=JOB&currency=NGN&max_price=1','currency=NGN&min_salary=1'):
   with self.assertRaises(urllib.error.HTTPError):self.call('/market/listings?'+query,token=a['token'])
 def test_inquiries_reuse_chat_notify_once_and_never_start_payment(self):
  a=self.shop();b=self.register('Client');i=self.save(a,self.body('SERVICE'))['id']
  for _ in range(2):r=self.call('/market/inquiry',{'id':i,'intent':'quote'},b['token'])
  self.assertEqual(r['peer'],a['id']);context=self.call('/market/chat_context?peer='+a['id'],token=b['token']);self.assertTrue(context['can_chat']);self.assertEqual(context['items'][0]['listing_type'],'SERVICE')
  notices=self.call('/market/activity',token=a['token'])['notifications'];inquiries=[n for n in notices if n['target'].get('event')=='inquiry'];self.assertEqual(len(inquiries),1);self.assertIn('Quotation request',inquiries[0]['text']);self.assertEqual(inquiries[0]['target']['listing'],i)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/offer_create',{'listing':i,'price':'1','client_id':'bad-offer'},b['token'])
  with self.server.db() as d:
   self.assertEqual(d.execute('SELECT count(*) FROM market_demo_orders').fetchone()[0],0);self.assertEqual(d.execute('SELECT count(*) FROM market_demo_journals').fetchone()[0],0)
 def test_non_product_numeric_prices_do_not_enable_offers(self):
  a=self.shop();b=self.register('Client')
  for kind,mode in [('SERVICE','fixed'),('SKILL','starting_from'),('JOB','fixed_salary')]:
   i=self.save(a,self.body(kind,pricing_mode=mode,price='50'))['id'];self.assertFalse(self.listing(b,i)['can_offer'])
   with self.assertRaises(urllib.error.HTTPError):self.call('/market/offer_create',{'listing':i,'price':'1','client_id':kind},b['token'])
 def test_job_deadline_blocks_new_inquiries_without_claiming_applications(self):
  a=self.shop();b=self.register('Applicant');base=self.body('JOB');base['type_details']['application_deadline']='2000-01-01';i=self.save(a,base)['id'];self.assertFalse(self.listing(b,i)['application_open'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/inquiry',{'id':i},b['token'])
 def test_backwards_migration_saved_ids_and_legacy_routes(self):
  a=self.shop();b=self.register('Reader');i=self.call('/market/post_ad',{'title':'Legacy advert','price':'Ask seller','category':'Services'},a['token'])['id'];self.call('/market/save_item',{'id':i,'saved':True},b['token'])
  modern=self.save(a,test_market_pilot.MarketPilotTest.body(self))['id']
  with self.server.db() as d:
   d.execute('DROP INDEX market_listing_type')
   for column in ('listing_type','pricing_mode','type_details'):d.execute('ALTER TABLE market_listing_meta DROP COLUMN '+column)
  market.init(self.server);market.init(self.server)
  self.assertEqual(self.listing(b,modern)['listing_type'],'PRODUCT');self.assertEqual(self.listing(b,modern)['amount_minor'],12500050);self.assertEqual(self.listing(b,i)['pricing_mode'],'legacy');self.assertEqual(self.call('/market/saved',token=b['token'])['listings'][0]['id'],i)

if __name__=='__main__':unittest.main()
