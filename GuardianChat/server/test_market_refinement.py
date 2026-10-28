import unittest,urllib.error
from urllib.parse import urlencode
import market_location as geo,test_market_listing_types

class MarketRefinementTest(unittest.TestCase):
 setUp=test_market_listing_types.TypedMarketTest.setUp;tearDown=test_market_listing_types.TypedMarketTest.tearDown;register=test_market_listing_types.TypedMarketTest.register;call=test_market_listing_types.TypedMarketTest.call;shop=test_market_listing_types.TypedMarketTest.shop;save=test_market_listing_types.TypedMarketTest.save;body=test_market_listing_types.TypedMarketTest.body;listing=test_market_listing_types.TypedMarketTest.listing
 def browse(self,u,**q):return self.call('/market/listings?'+urlencode(q),token=u['token'])
 def test_approximate_coordinates_validate_and_do_not_invent_distance(self):
  self.assertEqual(geo.coordinates('6.52448','3.37923'),(6.52,3.38));self.assertAlmostEqual(geo.distance(0,0,0,1),111.2,places=1)
  for lat,lon in [('NaN',1),(91,0),(0,181),(True,1),('',1),('infinity',0)]:
   with self.assertRaises(ValueError):geo.coordinates(lat,lon)
  a=self.shop();i=self.save(a,self.body(title='Without pin'))['id'];v=self.browse(a)['listings'][0];self.assertIsNone(v['distance_km']);self.assertIsNone(v['latitude'])
  with self.assertRaises(urllib.error.HTTPError):self.browse(a,location='distance')
 def test_radius_search_and_nearest_first_exclude_only_unknown_distance(self):
  a=self.shop();near=self.save(a,self.body(title='Near engineer',latitude=6.52,longitude=3.38))['id'];far=self.save(a,self.body(title='Far engineer',latitude=9.07,longitude=7.49))['id'];unknown=self.save(a,self.body(title='Unlocated engineer'))['id']
  all_items=self.browse(a,latitude=6.52,longitude=3.38,sort='distance')['listings'];self.assertEqual([x['id'] for x in all_items],[near,far,unknown]);self.assertIsNone(all_items[-1]['distance_km'])
  close=self.browse(a,location='distance',latitude=6.52,longitude=3.38,radius_km=25)['listings'];self.assertEqual([x['id'] for x in close],[near]);self.assertEqual(self.browse(a)['total'],3)
  for q in ({'sort':'distance'},{'sort':'invalid'},{'location':'distance','latitude':6.52,'longitude':3.38,'radius_km':'NaN'}):
   with self.assertRaises(urllib.error.HTTPError):self.browse(a,**q)
 def test_price_orders_keep_price_free_adverts_last_and_preserve_search(self):
  a=self.shop();free=self.save(a,self.body(title='Engineer free'))['id'];low=self.save(a,self.body(title='Engineer budget',pricing_mode='starting_from',price='10'))['id'];high=self.save(a,self.body(title='Engineer premium',pricing_mode='starting_from',price='500'))['id']
  for sort,expected in [('price_asc',[low,high,free]),('price_desc',[high,low,free])]:
   r=self.browse(a,q='Engineer',sort=sort,currency='NGN');self.assertEqual([x['id'] for x in r['listings']],expected);self.assertFalse(r['recommendations'])
  self.save(a,self.body(title='Engineer foreign',pricing_mode='starting_from',price='1',currency='USD'))
  with self.assertRaises(urllib.error.HTTPError):self.browse(a,sort='price_asc')
 def test_location_pin_edit_clear_and_ownership(self):
  a=self.shop();b=self.register('Other');body=self.body(latitude='6.52448',longitude='3.37923');i=self.save(a,body)['id'];self.assertEqual(self.listing(a,i)['latitude'],6.52)
  change=body|{'id':i,'revision':1,'latitude':'','longitude':''}
  with self.assertRaises(urllib.error.HTTPError):self.save(b,change)
  self.save(a,change);self.assertIsNone(self.listing(a,i)['latitude']);self.assertEqual(self.listing(a,i)['city'],'Lagos')

if __name__=='__main__':unittest.main()
