import unittest,urllib.error
import test_server
class SocialTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call
 def reg(self,name):return self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':name})
 def act(self,u,action,**body):return self.call('/social/'+action,body,u['token'])
 def profile(self,viewer,u):return self.call('/social/profile?id='+u['id'],token=viewer['token'])
 def test_message_requests_require_recipient_acceptance(self):
  a,b,c=self.reg('Requester'),self.reg('Recipient'),self.reg('Stranger')
  self.act(a,'message_request',target=b['id']);self.act(a,'message_request',target=b['id'])
  self.assertEqual(self.call('/users',token=a['token'])['users'],[])
  self.assertEqual(len(self.call('/social/message_requests',token=b['token'])['users']),1)
  with self.assertRaises(urllib.error.HTTPError):self.act(c,'message_accept',target=a['id'])
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'message_accept',target=b['id'])
  self.act(b,'message_accept',target=a['id']);self.act(b,'message_accept',target=a['id'])
  self.assertEqual([u['id'] for u in self.call('/users',token=a['token'])['users']],[b['id']])
  self.assertEqual(self.profile(a,b)['followers'],0)
  notices=self.call('/social/notices',token=b['token'])['notices'];self.assertEqual(len(notices),1)
  self.act(b,'seen',through=notices[0]['id']);self.assertTrue(self.call('/social/notices',token=b['token'])['notices'][0]['seen'])
 def test_message_decline_and_blocks_do_not_grant_contacts(self):
  a,b=self.reg('A'),self.reg('B');self.act(a,'message_request',target=b['id']);self.act(b,'message_decline',target=a['id'])
  self.assertEqual(self.act(b,'message_accept',target=a['id'])['state'],'declined')
  self.assertEqual(self.call('/users',token=a['token'])['users'],[])
  self.act(b,'block',target=a['id'])
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'message_request',target=b['id'])
 def test_report_decisions_are_admin_only_and_keep_history(self):
  a,b=self.reg('A'),self.reg('B');self.act(a,'report',target=b['id'],reason='Test report reason')
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(b['id'],))
  report=self.call('/social/reports',token=b['token'])['reports'][0]['id']
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'resolve_report',report=report,state='resolved',note='Test review decision')
  self.act(b,'resolve_report',report=report,state='reviewing',note='Checking the evidence')
  self.act(b,'resolve_report',report=report,state='resolved',note='Review completed with explanation')
  history=self.call('/social/report_history?report='+str(report),token=b['token'])['actions'];self.assertEqual([h['state'] for h in history],['reviewing','resolved'])
 def test_follow_is_idempotent_and_does_not_create_contact(self):
  a,b=self.reg('A'),self.reg('B')
  for _ in range(2):self.act(a,'follow',target=b['id'])
  self.assertEqual(self.profile(a,b)['followers'],1)
  self.assertEqual(self.call('/users',token=a['token'])['users'],[])
  self.assertEqual(len(self.call('/social/notices',token=b['token'])['notices']),1)
  self.act(a,'unfollow',target=b['id']);self.assertEqual(self.profile(a,b)['followers'],0)
 def test_private_requests_owner_only_and_lists_restricted(self):
  a,b,c=self.reg('A'),self.reg('B'),self.reg('C');self.act(b,'settings',private=True,bio='Private biography')
  self.assertEqual(self.act(a,'follow',target=b['id'])['relationship'],'pending')
  self.assertEqual(self.profile(a,b)['bio'],'');self.assertEqual(self.profile(a,b)['followers'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/social/followers?id='+b['id'],token=a['token'])
  self.act(c,'accept',target=a['id']);self.assertEqual(self.profile(a,b)['relationship'],'pending')
  self.act(b,'accept',target=a['id']);self.assertEqual(self.profile(a,b)['bio'],'Private biography');self.assertEqual(self.profile(a,b)['followers'],1)
 def test_blocks_remove_edges_and_prevent_contact_and_messages(self):
  a,b=self.reg('A'),self.reg('B');self.call('/contacts',{'code':b['id']},a['token']);self.act(a,'follow',target=b['id']);self.act(b,'follow',target=a['id']);self.act(a,'block',target=b['id'])
  for action in ['follow','report']:
   with self.assertRaises(urllib.error.HTTPError):self.act(b,action,target=a['id'],reason='test reason')
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages',{'peer':a['id'],'text':'Blocked','client_id':'blocked-1'},b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/contacts',{'code':a['id']},b['token'])
  self.act(a,'unblock',target=b['id']);self.assertEqual(self.profile(a,b)['followers'],0)
 def test_settings_validation_and_notifications_preference(self):
  a,b=self.reg('A'),self.reg('B');self.act(b,'settings',alerts=False)
  self.act(a,'follow',target=b['id']);self.assertEqual(self.call('/social/notices',token=b['token'])['notices'],[])
  for body in [dict(private='true'),dict(bio='x'*301)]:
   with self.assertRaises(urllib.error.HTTPError):self.act(b,'settings',**body)
 def test_reports_are_admin_only_and_self_follow_rejected(self):
  a,b=self.reg('A'),self.reg('B');self.act(a,'report',target=b['id'],reason='Abusive account')
  with self.assertRaises(urllib.error.HTTPError):self.call('/social/reports',token=a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'follow',target=a['id'])
 def test_migration_is_idempotent(self):
  import social
  a,b=self.reg('A'),self.reg('B');self.act(a,'follow',target=b['id']);social.init(self.server);social.init(self.server);self.assertEqual(self.profile(a,b)['followers'],1)
 def test_rate_limit_and_account_scoping(self):
  a,b=self.reg('A'),self.reg('B')
  for _ in range(30):self.act(a,'unfollow',target=b['id'])
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'follow',target=b['id'])
  self.act(b,'follow',target=a['id']);self.assertEqual(self.profile(b,a)['followers'],1)

 def test_suggestions_require_optin_public_and_unblocked(self):
  a,b,c=self.reg('A'),self.reg('B'),self.reg('C')
  def suggested():return self.call('/social/suggestions',token=a['token'])['users']
  self.assertEqual(suggested(),[])
  self.act(b,'settings',discoverable=True);self.act(c,'settings',discoverable=True,private=True)
  self.assertEqual([u['id'] for u in suggested()],[b['id']])
  self.act(a,'follow',target=b['id']);self.assertEqual(suggested(),[])
  self.act(a,'unfollow',target=b['id']);self.act(b,'block',target=a['id']);self.assertEqual(suggested(),[])

 def test_social_push_is_session_scoped_and_has_no_profile_payload(self):
  import social,threading
  a,b=self.reg('A'),self.reg('B');self.call('/password',{'password':'test social passphrase'},b['token']);token='social-push-token-'+'x'*40
  self.call('/push/register',{'push_token':token},b['token'])
  class FakePush:
   enabled=True
   def __init__(self):self.events=[];self.ready=threading.Event()
   def send(self,t,data):self.events.append((t,data));self.ready.set()
  fake=FakePush();self.server.push=fake;self.act(a,'follow',target=b['id']);social.dispatch_notices(self.server);self.assertTrue(fake.ready.wait(3));t,payload=fake.events[0]
  self.assertEqual(t,token);self.assertEqual(payload['event'],'social_notice');self.assertEqual(payload['recipient'],b['id']);self.assertEqual(set(payload),{'event','notice_id','recipient','expires_at'})
  self.call('/logout',{},b['token']);self.act(a,'unfollow',target=b['id']);self.act(a,'follow',target=b['id']);social.dispatch_notices(self.server);self.assertEqual(len(fake.events),1)

 def test_maintenance_keeps_view_cleanup_and_notice_dispatch(self):
  from unittest.mock import patch
  import gamebox_core,social
  seen=[];self.server.next_gamebox_tick=0
  with patch.object(self.server,'expire_views',side_effect=lambda:seen.append('views')),patch.object(gamebox_core,'tick',side_effect=lambda _:seen.append('gaming')),patch.object(gamebox_core,'dispatch_notices',side_effect=lambda _:seen.append('game_notices')),patch.object(social,'dispatch_notices',side_effect=lambda _:seen.append('social_notices')):
   self.server.service_actions()
  self.assertEqual(seen,['views','gaming','game_notices','social_notices'])
