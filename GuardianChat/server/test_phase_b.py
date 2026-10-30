import unittest,urllib.error,json,time
import test_server,rankings,game_identities,gamebox_core
class PhaseBTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call
 def user(self,name):
  u=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':name});self.call('/gaming/profile',{'tag':name,'game_id':'legacy-'+u['id'],'adult':True},u['token']);return u
 def identity(self,u,game='efootball',gid=None,**extra):return self.call('/identities/save',dict(dict(game=game,game_id=gid or 'game-'+u['id'],region='Nigeria',tz='Africa/Lagos',availability=[],nickname=u['name'],platform='mobile',country='NG',visible=True),**extra),u['token'])
 def admin(self,u):
  with self.server.db() as d:d.execute('INSERT OR IGNORE INTO game_admin VALUES(?)',(u['id'],))
 def rated(self,a,b,game='efootball',score=(1,0)):
  # Real result path, with synthetic fixture setup to isolate ratings from matchmaking limits.
  mid=__import__('uuid').uuid4().hex
  with self.server.db() as d:
   version=gamebox_core.current(d);d.execute("INSERT INTO gb_matches(id,game,a,b,gid_a,gid_b,state,created,deadline,version,rules) VALUES(?,?,?,?,?,?,'awaiting_results',?,?,?,?)",(mid,game,a['id'],b['id'],'a','b',int(time.time()),int(time.time())+3600,version['id'],version['config']))
  for u in (a,b):self.call('/gamebox/report',{'match':mid,'a':score[0],'b':score[1]},u['token'])
  return mid
 def rank(self,u,game='efootball',query=''):return self.call('/rankings/leaderboard?game='+game+query,token=u['token'])
 def test_two_games_duplicates_and_privacy_defaults(self):
  a,b=self.user('Alpha'),self.user('Beta');self.identity(a,gid='PlayerOne');self.identity(a,game='fc_mobile',gid='PlayerOne')
  with self.assertRaises(urllib.error.HTTPError):self.identity(b,gid='playerone')
  with self.assertRaises(urllib.error.HTTPError):self.identity(b,gid='ＰｌａｙｅｒＯｎｅ')
  identities=self.call('/identities/mine',token=a['token'])['identities'];self.assertEqual(len(identities),2)
  self.assertEqual(self.rank(a)['my_rank']['rating'],1500);self.assertTrue(self.rank(a)['my_rank']['provisional'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/rankings/leaderboard?game=efootball')
 def test_changes_are_reviewed_and_snapshot_preserved(self):
  a,b=self.user('Alpha'),self.user('Reviewer');self.admin(b);self.identity(a)
  with self.assertRaises(urllib.error.HTTPError):self.identity(a,gid='different')
  request=self.call('/identities/change',{'game':'efootball','new_id':'reviewed-new-id','reason':'Publisher display ID changed'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/identities/review',{'request':request['id'],'decision':'approve','note':'Checking my own request is not allowed'},a['token'])
  self.call('/identities/review',{'request':request['id'],'decision':'approve','note':'Ownership independently inspected in publisher profile'},b['token'])
  self.assertEqual(self.call('/identities/mine',token=a['token'])['identities'][0]['game_id'],'reviewed-new-id')
  with self.assertRaises(urllib.error.HTTPError):self.call('/identities/review',{'request':request['id'],'decision':'approve','note':'Duplicate review should not apply'},b['token'])
 def test_commitments_block_change_disable_and_missing_game_registration(self):
  a=self.user('Alpha');self.admin(a);self.identity(a)
  lid=self.call('/gaming/create',{'game':'efootball','name':'Identity commitments'},a['token'])['id'];self.call('/gaming/join',{'league':lid},a['token'])
  for action in ('change','disable'):
   with self.assertRaises(urllib.error.HTTPError):self.call('/identities/'+action,{'game':'efootball','new_id':'changed','reason':'A new publisher account ID'},a['token'])
  b=self.user('Beta')
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/join',{'league':lid},b['token'])
 def test_manual_verification_is_not_publisher_verification_and_no_self_review(self):
  a,b=self.user('Alpha'),self.user('Reviewer');self.admin(a);self.admin(b);self.identity(a)
  req=self.call('/identities/verification',{'game':'efootball','reason':'I can show my public publisher profile'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/identities/review',{'request':req['id'],'decision':'approve','note':'I cannot independently review myself'},a['token'])
  self.call('/identities/review',{'request':req['id'],'decision':'approve','note':'Challenge inspected on the publisher public profile'},b['token'])
  self.assertEqual(self.call('/identities/mine',token=a['token'])['identities'][0]['verification'],'manual_reviewed')
 def test_disable_reactivate_keeps_rating_and_history(self):
  a,b=self.user('Alpha'),self.user('Beta');self.identity(a);self.identity(b);self.rated(a,b)
  self.call('/identities/disable',{'game':'efootball'},a['token']);self.assertIsNone(self.rank(a)['my_rank'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/queue',{'game':'efootball'},a['token'])
  self.identity(a);self.assertEqual(self.rank(a)['my_rank']['played'],1);self.assertEqual(self.rank(a)['my_rank']['rating'],1512)
 def test_ten_placements_and_game_isolation_and_once_only_awards(self):
  a,b=self.user('Alpha'),self.user('Beta');self.identity(a);self.identity(b);self.identity(a,game='fc_mobile')
  for n in range(10):mid=self.rated(a,b,score=(1,1))
  r=self.rank(a)['my_rank'];self.assertFalse(r['provisional']);self.assertEqual(r['grade'],'Gold');self.assertIsNotNone(r['global_rank']);self.assertEqual(r['verified_placements'],10)
  self.assertEqual(self.rank(a,'fc_mobile')['my_rank']['rating'],1500);self.assertTrue(self.rank(a,'fc_mobile')['my_rank']['provisional'])
  with self.server.db() as d:
   m=dict(d.execute('SELECT * FROM gb_matches WHERE id=?',(mid,)).fetchone());self.assertIsNone(rankings.award(d,'open',m));self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],10)
  self.assertTrue(self.call('/gamebox/report',{'match':mid,'a':1,'b':1},a['token'])['already_submitted'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/report',{'match':mid,'a':2,'b':1},a['token'])
 def test_filters_keep_global_ranks_and_pagination(self):
  a,b,c=self.user('Alpha'),self.user('Beta'),self.user('Gamma');self.identity(a);self.identity(b);self.identity(c)
  with self.server.db() as d:d.execute('INSERT INTO gb_rank_baselines VALUES(?,?,?,?,?,?)',(a['id'],'efootball',1500,10,10,int(time.time())));d.execute('INSERT INTO gb_rank_baselines VALUES(?,?,?,?,?,?)',(b['id'],'efootball',1500,10,10,int(time.time())));d.execute("UPDATE gb_identity_meta SET country='GB' WHERE uid=?",(b['id'],))
  allrows=self.rank(a)['players'];own=next(p for p in allrows if p.get('uid')==a['id']);self.assertEqual(self.rank(a,query='&country=NG')['my_rank']['global_rank'],own['global_rank'])
  self.call('/contacts',{'code':b['id']},a['token']);self.assertEqual(self.rank(a,query='&friends=1')['total'],2)
  first=self.rank(a,query='&limit=1');second=self.rank(a,query='&limit=1&offset=1');self.assertNotEqual(first['players'][0]['uid'],second['players'][0]['uid'])
 def test_privacy_and_blocks_apply_even_with_warm_rating_cache(self):
  a,b=self.user('Alpha'),self.user('Beta');self.identity(a);self.identity(b);self.rank(a)
  self.call('/social/settings',{'private':True},b['token']);row=next(p for p in self.rank(a)['players'] if p.get('uid')!=a['id']);self.assertNotIn('uid',row);self.assertEqual(row['nickname'],'Private player')
  with self.assertRaises(urllib.error.HTTPError):self.call('/rankings/profile?game=efootball&id='+b['id'],token=a['token'])
  self.call('/social/settings',{'private':False},b['token']);self.call('/social/block',{'target':a['id']},b['token']);self.assertFalse(any(p.get('uid')==b['id'] for p in self.rank(a)['players']))
 def test_policy_version_freezes_existing_result_math(self):
  a,b=self.user('Alpha'),self.user('Beta');self.admin(a);self.identity(a);self.identity(b)
  with self.server.db() as d:
   v=gamebox_core.current(d);d.execute("INSERT INTO gb_matches(id,game,a,b,gid_a,gid_b,state,created,deadline,version,rules) VALUES('frozen','efootball',?,?, 'a','b','awaiting_results',?,?,?,?)",(a['id'],b['id'],int(time.time()),int(time.time())+3600,v['id'],v['config']))
  p=self.call('/rankings/policy',token=a['token']);p['config']['k']=48
  with self.assertRaises(urllib.error.HTTPError):self.call('/rankings/publish',{'base':p['id'],'config':p['config'],'reason':'Unauthorized settings change'},b['token'])
  self.call('/rankings/publish',{'base':p['id'],'config':p['config'],'reason':'Calibrate future matches only'},a['token'])
  for u in (a,b):self.call('/gamebox/report',{'match':'frozen','a':1,'b':0},u['token'])
  self.assertEqual(self.rank(a)['my_rank']['rating'],1512)
  with self.assertRaises(urllib.error.HTTPError):self.call('/rankings/publish',{'base':p['id'],'config':p['config'],'reason':'Stale policy cannot publish'},a['token'])
 def test_migrations_repeat_without_reset_or_double_placement_counts(self):
  a,b=self.user('Alpha'),self.user('Beta');self.identity(a);self.identity(b);self.rated(a,b)
  game_identities.init(self.server);rankings.init(self.server);rankings.init(self.server)
  self.assertEqual(self.rank(a)['my_rank']['verified_placements'],1);self.assertEqual(self.rank(a)['my_rank']['played'],1)

 def test_change_request_rejects_invalid_and_normalized_same_id(self):
  a=self.user('Alpha');self.identity(a,gid='PlayerOne')
  for gid in ('ＰｌａｙｅｒＯｎｅ','new\nidentifier'):
   with self.assertRaises(urllib.error.HTTPError):self.call('/identities/change',{'game':'efootball','new_id':gid,'reason':'Request a publisher identity change'},a['token'])
  request=self.call('/identities/change',{'game':'efootball','new_id':'ＮｅｗＰｌａｙｅｒ','reason':'Request a publisher identity change'},a['token'])
  with self.server.db() as d:self.assertEqual(d.execute('SELECT new_id FROM gb_identity_requests WHERE id=?',(request['id'],)).fetchone()[0],'NewPlayer')
