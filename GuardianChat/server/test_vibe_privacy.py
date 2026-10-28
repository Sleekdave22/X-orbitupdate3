import time,unittest,urllib.error
import test_vibes_activity

class VibePrivacyTest(unittest.TestCase):
 setUp=test_vibes_activity.VibeTest.setUp;tearDown=test_vibes_activity.VibeTest.tearDown;call=test_vibes_activity.VibeTest.call;register=test_vibes_activity.VibeTest.register;photo=test_vibes_activity.VibeTest.photo;publish=test_vibes_activity.VibeTest.publish
 def privacy(self,u,**values):return self.call('/vibe/privacy',{'public_audience':'everyone','exclude':[],'mute':[]}|values,u['token'])
 def test_excluded_viewer_cannot_read_any_capture_or_metadata(self):
  a=self.register('Author');b=self.register('Viewer');c=self.register('Allowed');post=self.publish(a);private=self.publish(a,'private',audience=[b['id'],c['id']]);self.privacy(a,exclude=[b['id']])
  for item in (post,private):
   for path in ('/vibe/media?id='+item['id']+'&protected=1','/vibe/preview?id='+item['id'],'/vibe/item?id='+item['id'],'/vibe/status?id='+item['id']):
    with self.assertRaises(urllib.error.HTTPError):self.call(path,token=b['token'])
   for action in ('view','react','reply'):
    with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/'+action,{'id':item['id'],'emoji':'🔥','text':'no','client_id':'blocked-reply'},b['token'])
  self.assertEqual(self.call('/vibe/feed',token=b['token'])['groups'],[]);self.assertNotIn(a['id'],self.call('/navigation/state',token=b['token'])['vibes']);self.assertTrue(self.call('/vibe/media?id='+post['id'],token=c['token'])['data'])
  with self.assertRaises(urllib.error.HTTPError):self.publish(a,'private',audience=[b['id']])
 def test_public_audience_contacts_and_followers_enforced_for_direct_links(self):
  a=self.register('Author');b=self.register('Contact');stranger=self.call('/register',{'invite':self.server.invite,'name':'Stranger'});post=self.publish(a);self.privacy(a,public_audience='contacts')
  self.assertTrue(self.call('/vibe/media?id='+post['id'],token=b['token'])['data'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+post['id'],token=stranger['token'])
  self.privacy(a,public_audience='followers')
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+post['id'],token=b['token'])
  with self.server.db() as d:d.execute("INSERT INTO social_follows VALUES(?,?,'accepted',?)",(b['id'],a['id'],int(time.time())))
  self.assertTrue(self.call('/vibe/media?id='+post['id'],token=b['token'])['data'])
 def test_muting_only_changes_own_feed_and_can_be_reversed(self):
  a=self.register('Author');b=self.register('Viewer');self.publish(a);self.privacy(b,mute=[a['id']]);self.assertEqual(self.call('/vibe/feed',token=b['token'])['groups'],[]);self.assertNotIn(a['id'],self.call('/navigation/state',token=b['token'])['vibes'])
  self.assertEqual(self.call('/vibe/privacy',token=a['token'])['mute'],[]);self.privacy(b);self.assertEqual(len(self.call('/vibe/feed',token=b['token'])['groups']),1)
 def test_settings_ownership_validation_and_removal(self):
  a=self.register('Author');b=self.register('Other');self.privacy(a,exclude=[b['id']]);self.assertEqual(self.call('/vibe/privacy',token=a['token'])['exclude'],[b['id']]);self.assertEqual(self.call('/vibe/privacy',token=b['token'])['exclude'],[])
  for body in ({'public_audience':'invalid'},{'exclude':[a['id']]},{'exclude':['unknown']},{'mute':'not-list'}):
   with self.assertRaises(urllib.error.HTTPError):self.privacy(a,**body)
  self.assertEqual(self.call('/vibe/privacy',token=a['token'])['exclude'],[b['id']])
 def test_feed_newest_first_with_viewed_groups_at_end(self):
  a=self.register('Older');b=self.register('Newer');viewer=self.register('Viewer');old=self.publish(a);new=self.publish(b)
  with self.server.db() as d:d.execute('UPDATE vibe_items SET created=created-10 WHERE id=?',(old['id'],))
  self.assertEqual([g['uid'] for g in self.call('/vibe/feed',token=viewer['token'])['groups']],[b['id'],a['id']]);self.call('/vibe/view',{'id':new['id']},viewer['token']);self.assertEqual([g['uid'] for g in self.call('/vibe/feed',token=viewer['token'])['groups']],[a['id'],b['id']])

if __name__=='__main__':unittest.main()
