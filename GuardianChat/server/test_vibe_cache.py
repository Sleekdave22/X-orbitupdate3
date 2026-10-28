import time,unittest,urllib.error
import test_vibes_activity as fixture
import vibes

class VibeCacheContractTest(unittest.TestCase):
 setUp=fixture.VibeTest.setUp;tearDown=fixture.VibeTest.tearDown;call=fixture.VibeTest.call;register=fixture.VibeTest.register;photo=fixture.VibeTest.photo;publish=fixture.VibeTest.publish
 def test_authorized_status_matches_media_and_has_no_media_bytes(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author)
  media=self.call('/vibe/media?id='+post['id'],token=author['token']);status=self.call('/vibe/status?id='+post['id'],token=author['token'])
  self.assertEqual(media['cache_tag'],status['cache_tag']);self.assertEqual(status['visibility'],'public');self.assertNotIn('data',status);self.assertEqual(status['view_count'],0)
  self.call('/vibe/view',{'id':post['id']},viewer['token'])
  refreshed=self.call('/vibe/status?id='+post['id'],token=author['token']);self.assertEqual(refreshed['cache_tag'],media['cache_tag']);self.assertEqual(refreshed['view_count'],1)
 def test_cached_item_reauthorization_rejects_privacy_and_expiry(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author)
  self.call('/vibe/media?id='+post['id'],token=viewer['token'])
  self.call('/vibe/privacy',{'public_audience':'everyone','exclude':[viewer['id']],'mute':[]},author['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/status?id='+post['id'],token=viewer['token'])
  with self.server.db() as d:d.execute('UPDATE vibe_items SET expires=? WHERE id=?',(int(time.time())-1,post['id']))
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/status?id='+post['id'],token=author['token'])
 def test_private_metadata_has_no_cache_tag_and_link_changes_invalidate(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author,'private',audience=[viewer['id']])
  status=self.call('/vibe/status?id='+post['id'],token=viewer['token']);self.assertNotIn('cache_tag',status);self.assertNotIn('caption',status)
  row={'digest':'same-media'};self.assertEqual(vibes.cache_tag(row,None),vibes.cache_tag(row,None));self.assertNotEqual(vibes.cache_tag(row,{'available':True}),vibes.cache_tag(row,{'available':False}))
