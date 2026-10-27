import urllib.error, unittest
from test_vibes_activity import VibeTest


class VibePrivacyTest(VibeTest):
 def feed_ids(self,user,visibility='public'):
  return [i['id'] for g in self.call('/vibe/feed?visibility='+visibility,token=user['token'])['groups'] for i in g['items']]

 def test_author_can_stop_one_person_from_viewing_every_vibe(self):
  author=self.register('Author');friend=self.register('Friend');blocked=self.register('Blocked')
  public=self.publish(author);private=self.publish(author,'private',audience=[friend['id'],blocked['id']])
  self.assertIn(public['id'],self.feed_ids(blocked))
  self.call('/vibe/viewer_block',{'target':blocked['id']},author['token'])
  self.assertEqual(self.feed_ids(blocked),[]);self.assertEqual(self.feed_ids(blocked,'private'),[])
  for path in ('/vibe/preview?id='+public['id'],'/vibe/media?id='+public['id']):
   with self.assertRaises(urllib.error.HTTPError):self.call(path,token=blocked['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/view',{'id':public['id']},blocked['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/reply',{'id':public['id'],'text':'hi','client_id':'abcdefgh12'},blocked['token'])
  self.assertIn(public['id'],self.feed_ids(friend));self.assertIn(private['id'],self.feed_ids(friend,'private'))
  self.assertIn(public['id'],self.feed_ids(author))

 def test_unblock_restores_access_and_lists_are_private(self):
  author=self.register('Author');other=self.register('Other');post=self.publish(author)
  self.call('/vibe/viewer_block',{'target':other['id']},author['token'])
  self.assertEqual([p['uid'] for p in self.call('/vibe/privacy',token=author['token'])['blocked']],[other['id']])
  self.assertEqual(self.call('/vibe/privacy',token=other['token'])['blocked'],[])
  self.call('/vibe/viewer_unblock',{'target':other['id']},author['token'])
  self.assertIn(post['id'],self.feed_ids(other))

 def test_viewer_can_hide_someones_vibes_without_telling_them(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author)
  self.call('/vibe/hide',{'target':author['id']},viewer['token']);self.assertEqual(self.feed_ids(viewer),[])
  self.assertIn(post['id'],self.feed_ids(author));self.assertEqual(self.call('/vibe/privacy',token=author['token'])['hidden'],[])
  self.assertEqual([p['uid'] for p in self.call('/vibe/privacy',token=viewer['token'])['hidden']],[author['id']])
  self.call('/vibe/unhide',{'target':author['id']},viewer['token']);self.assertIn(post['id'],self.feed_ids(viewer))

 def test_cannot_target_self_or_unknown_account(self):
  author=self.register('Author')
  for action in ('viewer_block','hide'):
   for target in (author['id'],'nobody'):
    with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/'+action,{'target':target},author['token'])

 def test_author_removes_own_post_and_it_disappears_for_everyone(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author)
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/remove',{'id':post['id']},viewer['token'])
  self.call('/vibe/remove',{'id':post['id']},author['token'])
  self.assertEqual(self.feed_ids(viewer),[]);self.assertEqual(self.feed_ids(author),[])


if __name__=='__main__':unittest.main()
