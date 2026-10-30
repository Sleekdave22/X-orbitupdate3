import unittest,urllib.error,time
import test_server
class SpacesTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call
 def reg(self,name):return self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':name})
 def act(self,u,action,**body):return self.call('/spaces/'+action,body,u['token'])
 def setup_space(self):
  a,b,c=self.reg('Owner'),self.reg('Member'),self.reg('Stranger');sid=self.act(a,'create',name='Test community',game='Chess')['id'];self.act(b,'join',space=sid);return a,b,c,sid
 def test_membership_and_scoped_posts(self):
  a,b,c,sid=self.setup_space();pid=self.act(a,'publish',space=sid,text='Hello community')['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/spaces/posts?space='+sid,token=c['token'])
  with self.assertRaises(urllib.error.HTTPError):self.act(c,'publish',space=sid,text='Unauthorized')
  self.assertEqual(self.call('/spaces/posts?space='+sid,token=b['token'])['posts'][0]['id'],pid)
  self.act(b,'leave',space=sid)
  with self.assertRaises(urllib.error.HTTPError):self.act(b,'like',space=sid,post=pid)
 def test_poll_votes_are_one_per_account_and_likes_idempotent(self):
  a,b,c,sid=self.setup_space();pid=self.act(a,'publish',space=sid,text='When to play?',kind='poll',options=['Today','Tomorrow'])['id']
  for choice in (0,1):self.act(b,'vote',space=sid,post=pid,choice=choice)
  for _ in range(2):self.act(b,'like',space=sid,post=pid)
  p=self.call('/spaces/posts?space='+sid,token=a['token'])['posts'][0];self.assertEqual(p['votes'],[{'choice':1,'total':1}]);self.assertEqual(p['likes'],1)
  with self.assertRaises(urllib.error.HTTPError):self.act(b,'vote',space=sid,post=pid,choice=3)
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'publish',space=sid,text='Duplicate poll',kind='poll',options=['Same','Same'])
 def test_moderation_is_author_or_owner_and_keeps_history(self):
  a,b,c,sid=self.setup_space();pid=self.act(a,'publish',space=sid,text='Owner message')['id']
  with self.assertRaises(urllib.error.HTTPError):self.act(b,'hide',space=sid,post=pid,reason='Not my post')
  self.act(a,'hide',space=sid,post=pid,reason='Own correction')
  self.assertEqual(self.call('/spaces/posts?space='+sid,token=b['token'])['posts'],[])
  with self.assertRaises(urllib.error.HTTPError):self.call('/spaces/moderation?space='+sid,token=b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.act(b,'restore',space=sid,post=pid,reason='Not the owner')
  self.act(a,'restore',space=sid,post=pid,reason='Correction reviewed')
  self.assertEqual(len(self.call('/spaces/posts?space='+sid,token=b['token'])['posts']),1)
  self.assertEqual(len(self.call('/spaces/moderation?space='+sid,token=a['token'])['actions']),2)
 def test_reply_notifications_and_cross_community_denial(self):
  a,b,c,sid=self.setup_space();pid=self.act(a,'publish',space=sid,text='Welcome')['id'];self.act(b,'publish',space=sid,text='Thank you',parent=pid)
  self.assertEqual(self.call('/social/notices',token=a['token'])['notices'][0]['kind'],'community_reply')
  other=self.act(b,'create',name='Other community',game='FC')['id']
  with self.assertRaises(urllib.error.HTTPError):self.act(b,'publish',space=other,text='Wrong room',parent=pid)
 def test_blocks_and_clip_validation(self):
  a,b,c,sid=self.setup_space()
  with self.assertRaises(urllib.error.HTTPError):self.act(a,'publish',space=sid,text='Unsafe clip',kind='clip',url='javascript:alert(1)')
  self.call('/social/block',{'target':b['id']},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/spaces/posts?space='+sid,token=b['token'])
  self.assertEqual(self.call('/spaces/communities',token=b['token'])['communities'],[])
 def test_squad_filters_expiry_and_account_scoping(self):
  a,b=self.reg('A'),self.reg('B');body=dict(game='Chess',region='Lagos',language='English',platform='Phone',rank='Beginner',availability='Evenings')
  self.act(a,'squad_save',**body);self.assertEqual(len(self.call('/spaces/squads?game=Chess&region=lagos',token=b['token'])['listings']),1)
  self.assertEqual(self.call('/spaces/squads?platform=Console',token=b['token'])['listings'],[])
  self.act(b,'squad_remove');self.assertEqual(len(self.call('/spaces/squads',token=a['token'])['listings']),1)
  with self.server.db() as d:d.execute('UPDATE squad_listings SET created=?',(int(time.time())-86401,));self.assertEqual(d.execute('SELECT COUNT(*) FROM fixtures').fetchone()[0],0)
  self.assertEqual(self.call('/spaces/squads',token=b['token'])['listings'],[])
