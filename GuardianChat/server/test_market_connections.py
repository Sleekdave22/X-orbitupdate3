import unittest,urllib.error,time
from concurrent.futures import ThreadPoolExecutor
import test_market_pilot

class MarketConnectionsTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register;shop=test_market_pilot.MarketPilotTest.shop;body=test_market_pilot.MarketPilotTest.body;save=test_market_pilot.MarketPilotTest.save
 def offer(self,u,i,key='offer'):return self.call('/market/offer_create',{'listing':i,'price':'100000','client_id':key},u['token'])['id']
 def test_offer_counter_accept_and_history_no_payment(self):
  a=self.shop();b=self.register('Buyer');i=self.save(a,self.body())['id'];o=self.offer(b,i)
  self.call('/market/offer_action',{'id':o,'revision':1,'action':'counter','price':'110000','client_id':'counter'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/offer_action',{'id':o,'revision':2,'action':'accept','client_id':'wrong-turn'},a['token'])
  self.call('/market/offer_action',{'id':o,'revision':2,'action':'accept','client_id':'accept'},b['token'])
  result=self.call('/market/offer?id='+o,token=b['token'])['offer'];self.assertEqual(result['state'],'ACCEPTED');self.assertEqual(result['amount_minor'],11000000);self.assertEqual(len(result['history']),3)
  with self.server.db() as d:self.assertEqual(d.execute('SELECT state FROM market_listing_meta WHERE id=?',(i,)).fetchone()[0],'RESERVED');self.assertEqual(d.execute('SELECT count(*) FROM fin_journals').fetchone()[0],0)
 def test_two_seller_accepts_cannot_double_reserve(self):
  a=self.shop();buyers=[self.register('Buyer1'),self.register('Buyer2')];i=self.save(a,self.body())['id'];offers=[self.offer(b,i,'offer-'+str(n)) for n,b in enumerate(buyers)]
  def accept(o):
   try:self.call('/market/offer_action',{'id':o,'revision':1,'action':'accept','client_id':'accept-'+o},a['token']);return True
   except urllib.error.HTTPError:return False
  with ThreadPoolExecutor(2) as p:results=list(p.map(accept,offers))
  self.assertEqual(results.count(True),1)
  with self.server.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM market_reservations').fetchone()[0],1)
 def test_idempotency_cancel_expire_ownership_and_block(self):
  a=self.shop();b=self.register('Buyer');c=self.register('Other');i=self.save(a,self.body())['id'];o=self.offer(b,i);self.assertEqual(self.offer(b,i),o)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/offer?id='+o,token=c['token'])
  self.call('/market/offer_action',{'id':o,'revision':1,'action':'cancel','client_id':'cancel'},b['token'])
  self.assertEqual(self.call('/market/offer?id='+o,token=a['token'])['offer']['state'],'CANCELLED')
  other=self.offer(c,i,'new')
  with self.server.db() as d:d.execute('UPDATE market_offers SET expires=1 WHERE id=?',(other,))
  self.assertEqual(self.call('/market/offer?id='+other,token=a['token'])['offer']['state'],'EXPIRED')
  self.call('/social/block',{'target':a['id'],'blocked':True},b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.offer(b,i,'blocked')
 def test_saved_changed_activity_routes_and_receipts(self):
  a=self.shop();b=self.register('Buyer');c=self.register('Other');i=self.save(a,self.body())['id'];self.call('/market/save_item',{'id':i,'saved':True},b['token']);self.call('/market/save_item',{'id':i,'saved':True},b['token'])
  self.assertEqual(len(self.call('/market/saved',token=b['token'])['listings']),1)
  self.call('/market/listing_state',{'id':i,'revision':1,'state':'PAUSED'},a['token'])
  event=self.call('/market/activity',token=b['token'])['notifications'][0];self.assertEqual(event['target']['listing'],i);self.assertEqual(event['target']['event'],'saved_changed')
  self.call('/market/activity_seen',{'through_id':event['id']},c['token']);self.assertEqual(self.call('/market/activity',token=b['token'])['unread'],1)
  self.call('/market/activity_seen',{'ids':[event['id']]},b['token']);r=self.call('/market/activity',token=b['token']);self.assertEqual(r['unread'],0);self.assertEqual(len(r['notifications']),1);self.assertTrue(r['notifications'][0]['seen'])
 def test_inquiry_context_reuses_chat_permission_and_dedupes(self):
  a=self.shop();b=self.register('Buyer');i=self.save(a,self.body())['id'];self.call('/market/inquiry',{'id':i},b['token']);self.call('/market/inquiry',{'id':i},b['token'])
  context=self.call('/market/chat_context?peer='+a['id'],token=b['token']);self.assertTrue(context['can_chat']);self.assertEqual(context['items'][0]['id'],i)
  events=self.call('/market/activity',token=a['token'])['notifications'];self.assertEqual(sum(n['target'].get('event')=='inquiry' for n in events),1)
  stranger=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Stranger'})
  r=self.call('/market/inquiry',{'id':i},stranger['token']);self.assertEqual(r['state'],'pending');self.assertFalse(self.call('/market/chat_context?peer='+a['id'],token=stranger['token'])['can_chat'])
  self.call('/social/message_accept',{'target':stranger['id']},a['token']);self.assertTrue(self.call('/market/chat_context?peer='+a['id'],token=stranger['token'])['can_chat'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/inquiry',{'id':i},a['token'])
  self.call('/social/block',{'target':b['id'],'blocked':True},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/inquiry',{'id':i},b['token'])

if __name__=='__main__':unittest.main()
