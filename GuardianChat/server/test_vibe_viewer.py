import concurrent.futures, time, urllib.error, unittest
from test_vibes_activity import VibeTest


class VibeViewerTest(VibeTest):
 def test_previews_do_not_mark_seen_and_private_previews_stay_protected(self):
  author=self.register('Author');viewer=self.register('Viewer');public=self.publish(author)
  preview=self.call('/vibe/preview?id='+public['id'],token=viewer['token'])
  self.assertEqual(preview['mime'],'image/jpeg');self.assertTrue(preview['data'])
  self.assertEqual(self.call('/vibe/viewers?id='+public['id'],token=author['token'])['viewers'],[])
  private=self.publish(author,'private',audience=[viewer['id']])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/preview?id='+private['id'],token=viewer['token'])
  self.call('/vibe/view',{'id':public['id']},viewer['token'])
  self.assertEqual(len(self.call('/vibe/viewers?id='+public['id'],token=author['token'])['viewers']),1)

 def test_feed_identifies_self_and_contacts_without_private_caption_leak(self):
  author=self.register('Author');viewer=self.register('Viewer');stranger=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Stranger'})
  self.publish(author,caption='Public post')
  feed=self.call('/vibe/feed',token=viewer['token']);self.assertEqual(feed['account']['id'],viewer['id']);self.assertTrue(feed['groups'][0]['contact'])
  self.assertFalse(self.call('/vibe/feed',token=stranger['token'])['groups'][0]['contact'])
  self.publish(author,'private',audience=[viewer['id']],caption='Private caption')
  self.assertEqual(self.call('/vibe/feed?visibility=private',token=viewer['token'])['groups'][0]['items'][0]['caption'],'')

 def test_inline_reply_is_private_tagged_and_idempotent_after_expiry(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author)
  body={'id':post['id'],'text':'Great game!','client_id':'reply-1'}
  first=self.call('/vibe/reply',body,viewer['token']);self.assertTrue(first['sent'])
  self.assertEqual(self.call('/vibe/reply',body,viewer['token'])['id'],first['id'])
  rows=self.call('/messages?peer='+viewer['id'],token=author['token'])['messages']
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['text'],'↪ Reply to your Vibe\nGreat game!')
  with self.server.db() as d:
   self.assertEqual(d.execute('SELECT item FROM vibe_replies WHERE message_id=?',(first['id'],)).fetchone()[0],post['id'])
   d.execute('UPDATE vibe_items SET expires=? WHERE id=?',(int(time.time())-1,post['id']))
  self.assertEqual(self.call('/vibe/reply',body,viewer['token'])['id'],first['id'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/reply',dict(body,client_id='new-after-expiry'),viewer['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/reply',dict(body,text='Changed'),viewer['token'])

 def test_reply_does_not_create_contacts_or_bypass_blocks_or_private_audience(self):
  author=self.register('Author');viewer=self.register('Viewer');stranger=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Stranger'});post=self.publish(author)
  body={'id':post['id'],'text':'Hello','client_id':'protected-reply'}
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/reply',body,stranger['token'])
  private=self.publish(author,'private',audience=[viewer['id']])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/reply',dict(body,id=private['id']),stranger['token'])
  result=self.call('/vibe/reply',dict(body,id=private['id']),viewer['token'])
  self.assertIn('Reply to your Private Vibe',self.call('/messages?peer='+author['id'],token=viewer['token'])['messages'][0]['text'])
  self.call('/social/block',{'target':viewer['id']},author['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/reply',dict(body,client_id='blocked'),viewer['token'])
  with self.server.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM contacts WHERE owner=?',(stranger['id'],)).fetchone()[0],0)

 def test_concurrent_retry_delivers_one_message(self):
  author=self.register('Author');viewer=self.register('Viewer');post=self.publish(author)
  body={'id':post['id'],'text':'Only once','client_id':'same-concurrent-reply'}
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.call('/vibe/reply',body,viewer['token']),range(2)))
  self.assertEqual(results[0]['id'],results[1]['id'])
  with self.server.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM messages WHERE sender=?',(viewer['id'],)).fetchone()[0],1)


if __name__=='__main__':unittest.main()
