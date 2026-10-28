import base64,io,time,urllib.error,unittest
from unittest.mock import patch
from PIL import Image
from test_server import ChatTest
import vibes,account_notifications,gamebox_core

class VibeTest(unittest.TestCase):
 setUp=ChatTest.setUp;tearDown=ChatTest.tearDown;call=ChatTest.call;register=ChatTest.register
 def photo(self):
  out=io.BytesIO();Image.new('RGB',(30,20),'blue').save(out,format='PNG');return base64.b64encode(out.getvalue()).decode()
 def publish(self,user,visibility='public',**extra):return self.call('/vibe/publish',{'visibility':visibility,'client_id':'capture-'+str(time.time_ns()),'media':self.photo(),'mime':'image/png',**extra},user['token'])
 def test_individual_expiry_and_separate_defaults(self):
  u=self.register('Author');self.call('/vibe/preferences',{'public_hours':12,'private_hours':48},u['token'])
  with patch('vibes.time.time',return_value=2000000000):a=self.publish(u)
  with patch('vibes.time.time',return_value=2000000100):b=self.publish(u)
  self.assertEqual(a['expires'],2000000000+12*3600);self.assertEqual(b['expires']-a['expires'],100)
  self.call('/vibe/preferences',{'public_hours':24,'private_hours':12},u['token'])
  with self.server.db() as d:self.assertEqual(d.execute('SELECT expires FROM vibe_items WHERE id=?',(a['id'],)).fetchone()[0],a['expires'])
 def test_private_audience_block_and_media_boundary(self):
  a=self.register('Author');b=self.register('Recipient');c=self.register('Other');r=self.publish(a,'private',audience=[b['id']])
  self.assertEqual(len(self.call('/vibe/feed?visibility=private',token=b['token'])['groups']),1)
  self.assertEqual(self.call('/vibe/feed?visibility=private',token=c['token'])['groups'],[])
  for target in (b,c):
   with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+r['id'],token=target['token'])
  self.assertEqual(self.call('/vibe/media?id='+r['id']+'&protected=1',token=b['token'])['mime'],'image/png')
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+r['id']+'&protected=1',token=c['token'])
  with self.server.db() as d:d.execute('INSERT INTO social_blocks VALUES(?,?)',(a['id'],b['id']))
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+r['id']+'&protected=1',token=b['token'])
 def test_viewers_reactions_and_author_only_history(self):
  a=self.register('Author');b=self.register('Viewer');r=self.publish(a)
  for _ in range(2):self.call('/vibe/view',{'id':r['id']},b['token'])
  self.call('/vibe/react',{'id':r['id'],'emoji':'🔥'},b['token'])
  viewer=self.call('/vibe/viewers?id='+r['id'],token=a['token'])['viewers'][0]
  self.assertEqual(viewer['uid'],b['id']);self.assertEqual(viewer['opens'],2);self.assertEqual(viewer['emoji'],'🔥');self.assertLessEqual(viewer['first_seen'],viewer['last_seen'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/viewers?id='+r['id'],token=b['token'])
  self.assertEqual(len(self.call('/notifications?category=vibe',token=a['token'])['notifications']),1)
 def test_private_navigation_and_owner_view_count(self):
  a=self.register('Author');b=self.register('Viewer');c=self.register('Other')
  first=self.publish(a,'private',audience=[b['id']]);hidden=self.publish(a,'private',audience=[c['id']]);last=self.publish(a,'private',audience=[b['id']])
  self.call('/vibe/view',{'id':first['id']},b['token'])
  own=self.call('/vibe/media?id='+first['id']+'&protected=1',token=a['token']);self.assertEqual(own['view_count'],1)
  allowed=self.call('/vibe/media?id='+first['id']+'&protected=1',token=b['token']);self.assertEqual(allowed['next_id'],last['id']);self.assertIsNone(allowed['view_count'])
  reverse=self.call('/vibe/media?id='+last['id']+'&protected=1',token=b['token']);self.assertEqual(reverse['previous_id'],first['id']);self.assertNotEqual(reverse['previous_id'],hidden['id'])
 def test_expiry_denies_every_action_and_purges_bytes(self):
  a=self.register('Author');b=self.register('Viewer');r=self.publish(a)
  with self.server.db() as d:d.execute('UPDATE vibe_items SET expires=? WHERE id=?',(int(time.time())-1,r['id']))
  for path,body in [('/vibe/media?id='+r['id'],None),('/vibe/view',{'id':r['id']}),('/vibe/react',{'id':r['id'],'emoji':'🔥'})]:
   with self.assertRaises(urllib.error.HTTPError):self.call(path,body,b['token'])
  vibes.purge(self.server)
  with self.server.db() as d:self.assertIsNone(d.execute('SELECT media FROM vibe_items WHERE id=?',(r['id'],)).fetchone()[0])
 def test_upload_retry_and_bad_media(self):
  a=self.register('Author');body={'visibility':'public','client_id':'same-retry','media':self.photo(),'mime':'image/png'}
  first=self.call('/vibe/publish',body,a['token']);second=self.call('/vibe/publish',body,a['token']);self.assertEqual(first['id'],second['id']);self.assertTrue(second['already_published'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/publish',body|{'caption':'Changed'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/publish',body|{'media':base64.b64encode(b'broken').decode()},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.publish(a,'private',audience=[])
 def test_notification_receipts_are_account_category_and_snapshot_scoped(self):
  a=self.register('First');b=self.register('Second')
  with self.server.db() as d:
   play=gamebox_core.notice(d,a['id'],'Match ready');account_notifications.add(d,a['id'],'market','shop','Advert update');account_notifications.add(d,b['id'],'market','shop','Other update')
  own=self.call('/notifications?category=market',token=a['token']);self.assertEqual(len(own['notifications']),1);ident=own['notifications'][0]['id']
  self.call('/notifications/seen',{'category':'market','ids':[ident]},b['token']);self.assertEqual(len(self.call('/notifications?category=market',token=a['token'])['notifications']),1)
  self.call('/notifications/seen',{'category':'market','ids':[ident]},a['token']);self.assertEqual(self.call('/notifications?category=market',token=a['token'])['notifications'],[])
  self.assertEqual(len(self.call('/notifications?category=play',token=a['token'])['notifications']),1)
  with self.server.db() as d:account_notifications.add(d,a['id'],'market','shop','New update')
  self.call('/notifications/seen',{'category':'market','ids':[ident]},a['token']);self.assertEqual(len(self.call('/notifications?category=market',token=a['token'])['notifications']),1)

if __name__=='__main__':unittest.main()
