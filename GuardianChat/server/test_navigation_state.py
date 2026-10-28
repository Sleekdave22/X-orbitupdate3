import unittest,time,urllib.error
import test_vibes_activity

class NavigationStateTest(unittest.TestCase):
 setUp=test_vibes_activity.VibeTest.setUp;tearDown=test_vibes_activity.VibeTest.tearDown;call=test_vibes_activity.VibeTest.call;register=test_vibes_activity.VibeTest.register
 photo=test_vibes_activity.VibeTest.photo;publish=test_vibes_activity.VibeTest.publish
 def state(self,u):return self.call('/navigation/state',token=u['token'])
 def test_unread_is_account_scoped_and_clears_only_on_read(self):
  a=self.register('Sender');b=self.register('Reader');c=self.register('Other')
  for i in range(2):self.call('/messages',dict(peer=b['id'],text='Unread '+str(i),client_id='nav-'+str(i)),a['token'])
  self.assertEqual(self.state(a)['unread_messages'],0);self.assertEqual(self.state(b)['unread_messages'],2);self.assertEqual(self.state(c)['unread_messages'],0)
  rows=self.call('/messages?peer='+a['id'],token=b['token'])['messages'];self.assertEqual(self.state(b)['unread_messages'],2,'Fetching must not mark messages read')
  self.call('/read',{'peer':a['id'],'through':rows[-1]['id']},b['token']);self.assertEqual(self.state(b)['unread_messages'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/navigation/state')
 def test_unread_total_spans_chats_and_partial_read(self):
  a=self.register('Alpha');b=self.register('Beta');r=self.register('Reader')
  for sender,count in [(a,2),(b,3)]:
   for i in range(count):self.call('/messages',dict(peer=r['id'],text='Unread',client_id=sender['id']+str(i)),sender['token'])
  self.assertEqual(self.state(r)['unread_messages'],5)
  rows=self.call('/messages?peer='+a['id'],token=r['token'])['messages']
  self.call('/read',{'peer':a['id'],'through':rows[-1]['id']},r['token']);self.assertEqual(self.state(r)['unread_messages'],3)
 def missed(self,a,b):
  c=self.call('/calls/start',{'peer':b['id'],'offer':{'type':'offer','sdp':'test'}},a['token'])
  self.call('/calls/end',{'id':c['id']},a['token']);return c['id']
 def test_missed_calls_clear_only_displayed_snapshot_and_are_idempotent(self):
  a=self.register('Caller');b=self.register('Reader');first=self.missed(a,b)
  self.assertEqual(self.state(a)['missed_calls'],0);self.assertEqual(self.state(b)['missed_calls'],1)
  history=self.call('/call-history',token=b['token'])['calls'];self.assertEqual(history[0]['id'],first)
  self.assertEqual(self.state(b)['missed_calls'],1,'Fetching or polling must not acknowledge history')
  second=self.missed(a,b)
  for _ in range(2):self.call('/navigation/calls-seen',{'ids':[first]},b['token'])
  self.assertEqual(self.state(b)['missed_calls'],1,'A new call outside the displayed snapshot stays unseen')
  self.call('/navigation/calls-seen',{'ids':[second]},b['token']);self.assertEqual(self.state(b)['missed_calls'],0)
  self.assertEqual(self.state(b)['unread_messages'],0,'Calls are separate from message counts')
 def test_missed_ack_is_authorized_atomic_and_validated(self):
  a=self.register('Caller');b=self.register('Reader');c=self.register('Other');first=self.missed(a,b);other=self.missed(a,c)
  for ids in ([first,other],['missing']):
   with self.assertRaises(urllib.error.HTTPError) as err:self.call('/navigation/calls-seen',{'ids':ids},b['token'])
   self.assertEqual(err.exception.code,403)
  self.assertEqual(self.state(b)['missed_calls'],1)
  for ids in ('wrong',[None],['x']*201):
   with self.assertRaises(urllib.error.HTTPError) as err:self.call('/navigation/calls-seen',{'ids':ids},b['token'])
   self.assertEqual(err.exception.code,400)
  with self.assertRaises(urllib.error.HTTPError):self.call('/navigation/calls-seen',{'ids':[first]})
  self.call('/social/block',{'target':a['id']},b['token']);self.assertEqual(self.state(b)['missed_calls'],0)
 def test_missed_count_excludes_connected_declined_and_active_calls(self):
  a=self.register('Caller');b=self.register('Reader')
  with self.server.db() as d:
   for i,outcome in enumerate(('missed','cancelled','completed','declined','ringing','disconnected')):
    d.execute('INSERT INTO call_history(id,caller,recipient,started,ended,outcome) VALUES(?,?,?,?,?,?)',(str(i),a['id'],b['id'],time.time(),None if outcome=='ringing' else time.time(),outcome))
  self.assertEqual(self.state(b)['missed_calls'],2)
 def test_missed_ack_survives_server_restart(self):
  import threading
  from server import ChatServer
  a=self.register('Caller');b=self.register('Reader');ident=self.missed(a,b)
  self.call('/navigation/calls-seen',{'ids':[ident]},b['token'])
  self.server.shutdown();self.server.server_close();self.server=ChatServer(('127.0.0.1',0),self.tmp.name)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f'http://127.0.0.1:{self.server.server_port}'
  self.assertEqual(self.state(b)['missed_calls'],0)
  self.assertEqual(len(self.call('/call-history',token=b['token'])['calls']),1,'Acknowledging retains call history')
 def test_unseen_vibes_count_posts_not_authors_and_only_clear_after_view(self):
  a=self.register('Author');b=self.register('Viewer');c=self.register('Other')
  x=self.publish(a);y=self.publish(a,'private',audience=[b['id']]);self.publish(b)
  self.assertEqual(self.state(b)['unseen_vibes'],2);self.assertEqual(self.state(c)['unseen_vibes'],2)
  self.call('/vibe/feed',token=b['token']);self.assertEqual(self.state(b)['unseen_vibes'],2)
  self.call('/vibe/view',{'id':x['id']},b['token']);self.assertEqual(self.state(b)['unseen_vibes'],1)
  self.call('/vibe/view',{'id':x['id']},b['token']);self.assertEqual(self.state(b)['unseen_vibes'],1)
  self.call('/vibe/view',{'id':y['id']},b['token']);self.assertEqual(self.state(b)['unseen_vibes'],0)
 def test_unseen_vibes_exclude_muted_excluded_expired_and_unshared_private(self):
  a=self.register('Author');b=self.register('Viewer');c=self.register('Other');x=self.publish(a);self.publish(a,'private',audience=[c['id']])
  self.assertEqual(self.state(b)['unseen_vibes'],1)
  self.call('/vibe/privacy',{'public_audience':'everyone','exclude':[],'mute':[a['id']]},b['token']);self.assertEqual(self.state(b)['unseen_vibes'],0)
  self.call('/vibe/privacy',{'public_audience':'everyone','exclude':[],'mute':[]},b['token'])
  self.call('/vibe/privacy',{'public_audience':'everyone','exclude':[b['id']],'mute':[]},a['token']);self.assertEqual(self.state(b)['unseen_vibes'],0)
  self.call('/vibe/privacy',{'public_audience':'everyone','exclude':[],'mute':[]},a['token'])
  with self.server.db() as d:d.execute('UPDATE vibe_items SET expires=1 WHERE id=?',(x['id'],))
  self.assertEqual(self.state(b)['unseen_vibes'],0)
 def test_unseen_count_matches_contact_feed_not_unrelated_public_authors(self):
  a=self.register('Author');b=self.call('/register',{'invite':self.server.invite,'name':'Unconnected'})
  self.publish(a);self.assertEqual(self.state(b)['unseen_vibes'],0)
  self.call('/contacts',{'code':a['id']},b['token']);self.assertEqual(self.state(b)['unseen_vibes'],1)
 def test_vibe_indicator_has_latest_reference_and_selected_audience_only(self):
  a=self.register('Author');b=self.register('Allowed');c=self.register('Excluded')
  x=self.publish(a,'private',audience=[b['id']]);y=self.publish(a,'private',audience=[b['id']]);badge=self.state(b)['vibes'][a['id']]
  self.assertEqual(badge['count'],2);self.assertEqual(badge['item'],y['id']);self.assertEqual(badge['visibility'],'private');self.assertNotIn(a['id'],self.state(c)['vibes'])
  self.assertEqual(self.call('/vibe/media?id='+x['id']+'&protected=1',token=b['token'])['next_id'],y['id'])
  self.assertIsNone(self.call('/vibe/media?id='+y['id']+'&protected=1',token=b['token'])['next_id'])
  with self.server.db() as d:d.execute('UPDATE vibe_items SET expires=1 WHERE uid=?',(a['id'],))
  self.assertNotIn(a['id'],self.state(b)['vibes'])
 def test_hidden_deleted_and_blocked_messages_do_not_badge(self):
  a=self.register('Sender');b=self.register('Reader');mid=self.call('/messages',dict(peer=b['id'],text='Hidden unread',client_id='nav-hidden'),a['token'])['id']
  with self.server.db() as d:d.execute('INSERT INTO message_hidden(user_id,message_id) VALUES(?,?)',(b['id'],mid))
  self.assertEqual(self.state(b)['unread_messages'],0)
  deleted=self.call('/messages',dict(peer=b['id'],text='Deleted unread',client_id='nav-deleted'),a['token'])['id']
  with self.server.db() as d:d.execute('UPDATE messages SET deleted_all=1 WHERE id=?',(deleted,))
  self.assertEqual(self.state(b)['unread_messages'],0)
  self.call('/messages',dict(peer=b['id'],text='Blocked unread',client_id='nav-blocked'),a['token']);self.call('/social/block',{'target':a['id']},b['token'])
  self.assertEqual(self.state(b)['unread_messages'],0);self.assertNotIn(a['id'],self.state(b)['vibes'])

if __name__=='__main__':unittest.main()
