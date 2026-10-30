import concurrent.futures,sqlite3,time,unittest,urllib.error
import test_server,wallet
class WalletTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call;register=test_server.ChatTest.register
 def users(self):
  self.a=self.register('Wallet owner');self.b=self.register('Recipient');self.c=self.register('Other');self.call('/password',{'password':'test-wallet-pass'},self.a['token']);self.server.wallet_fixtures=True;wallet.provision_test_funds(self.server,self.a['id'],10000,'fixture-start')
 def quote(self,amount=1000,target=None):return self.call('/wallet/quote',{'recipient':target or self.b['id'],'amount_kobo':amount},self.a['token'])
 def send(self,q,key='test-transfer-key-0001',token=None,password='test-wallet-pass'):return self.call('/wallet/transfer',{'quote':q['quote'],'idempotency_key':key,'password':password},token or self.a['token'])
 def funds(self,u):return self.call('/wallet/summary',token=u['token'])
 def test_accounts_migrate_once_and_ownership_survives_profile_changes(self):
  a=self.register('Non gamer');w=self.funds(a);self.assertEqual(w['mode'],'test');self.assertFalse(w['real_payments_enabled']);self.assertEqual(w['available_kobo'],0);wallet.init(self.server);wallet.init(self.server)
  self.call('/profile',{'name':'Renamed','nickname':'renamed_wallet'},a['token']);self.assertEqual(self.funds(a)['id'],w['id'])
  with self.server.db() as d:d.execute('INSERT INTO users(id,name,token_hash,nickname) VALUES(?,?,?,?)',('legacy','Legacy','legacy-hash','legacy'))
  wallet.init(self.server);wallet.init(self.server)
  with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM fin_wallets').fetchone()[0],2)
 def test_transfer_balanced_private_password_authorized_and_idempotent(self):
  self.users();q=self.quote();r=self.send(q);self.assertEqual(self.send(q),r);self.assertEqual(self.funds(self.a)['available_kobo'],9000);self.assertEqual(self.funds(self.b)['available_kobo'],1000)
  h=self.call('/wallet/history',token=self.b['token'])['transactions'];self.assertEqual(len(h),1);self.assertEqual(h[0]['available_change_kobo'],1000);self.assertEqual(self.call('/wallet/history?owner='+self.a['id'],token=self.c['token'])['transactions'],[])
  with self.server.db() as d:
   self.assertEqual(d.execute('SELECT COUNT(*) FROM fin_operations').fetchone()[0],1);self.assertTrue(all(x[0]==0 for x in d.execute('SELECT SUM(amount) FROM fin_postings GROUP BY journal')));d.execute('INSERT INTO game_admin VALUES(?)',(self.a['id'],));d.execute("INSERT OR IGNORE INTO fin_permissions VALUES(?,'overview')",(self.a['id'],))
  wallet.init(self.server);o=self.call('/wallet/overview',token=self.a['token']);self.assertTrue(o['reconciliation']['balanced']);self.assertEqual(o['transfer_volume_kobo'],1000)
  with self.assertRaises(urllib.error.HTTPError):self.call('/wallet/overview',token=self.b['token'])
  with self.server.db() as d:d.execute('DELETE FROM game_admin')
  with self.assertRaises(urllib.error.HTTPError):self.call('/wallet/overview',token=self.a['token'])
 def test_amounts_unsupported_routes_and_unauthorised_access(self):
  self.users()
  for value in (True,0,-1,1.1,'100',1000001):
   with self.assertRaises(urllib.error.HTTPError):self.quote(value)
  for target in (self.a['id'],'missing-recipient'):
   with self.assertRaises(urllib.error.HTTPError):self.quote(target=target)
  for operation in ('fund','deposit','withdraw','mint','adjust','capture','grant','refund','pay_entry'):
   with self.assertRaises(urllib.error.HTTPError):self.call('/wallet/'+operation,{'amount_kobo':1000},self.a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/wallet/summary')
  with self.assertRaises(urllib.error.HTTPError):self.send(self.quote(),token=self.c['token'])
  self.assertEqual(self.funds(self.a)['available_kobo'],10000)
 def test_wrong_password_throttle_persists(self):
  self.users();q=self.quote()
  for _ in range(8):
   with self.assertRaises(urllib.error.HTTPError):self.send(q,password='wrong')
  with self.assertRaises(urllib.error.HTTPError):self.send(q)
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count FROM fin_rate WHERE owner=? AND action='authorize'",(self.a['id'],)).fetchone()[0],8)
  self.assertEqual(self.funds(self.b)['available_kobo'],0)
 def test_expiry_identity_binding_restriction_and_key_conflict(self):
  self.users();q=self.quote(target='@'+self.b['id']);self.call('/profile',{'name':'Renamed','nickname':'new_recipient'},self.b['token']);self.assertEqual(self.send(q)['recipient'],self.b['id']);q2=self.quote()
  with self.assertRaises(urllib.error.HTTPError):self.send(q2)
  with self.server.db() as d:d.execute('UPDATE fin_quotes SET expires=0 WHERE id=?',(q2['quote'],))
  with self.assertRaises(urllib.error.HTTPError):self.send(q2,'test-expired-key-0001')
  q3=self.quote()
  with self.server.db() as d:d.execute("UPDATE fin_wallets SET status='restricted' WHERE owner=?",(self.b['id'],))
  with self.assertRaises(urllib.error.HTTPError):self.send(q3,'test-restrict-key-001')
 def test_concurrent_spending(self):
  self.users();qs=[self.quote(8000),self.quote(8000)]
  def run(i):
   try:return self.send(qs[i],'race-transfer-key-'+str(i))
   except urllib.error.HTTPError:return None
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
  self.assertEqual(sum(x is not None for x in results),1);self.assertEqual(self.funds(self.a)['available_kobo'],2000);self.assertEqual(self.funds(self.b)['available_kobo'],8000);wallet.init(self.server);self.assertEqual(self.funds(self.b)['available_kobo'],8000)
 def test_simultaneous_same_key(self):
  self.users();q=self.quote()
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(lambda _:self.send(q),range(2)))
  self.assertEqual(r[0],r[1]);self.assertEqual(self.funds(self.b)['available_kobo'],1000)
 def test_reserve_release_expiry_and_fixture_gate(self):
  self.users();expiry=int(time.time())+120
  with self.server.db() as d:
   d.execute('BEGIN IMMEDIATE');hid=wallet.reserve(d,self.a['id'],3000,'test-hold',expiry);self.assertEqual(wallet.reserve(d,self.a['id'],3000,'test-hold',expiry),hid)
  self.assertEqual(self.funds(self.a)['available_kobo'],7000);self.assertEqual(self.funds(self.a)['reserved_kobo'],3000)
  with self.server.db() as d:
   d.execute('BEGIN IMMEDIATE')
   with self.assertRaises(PermissionError):wallet.release(d,hid,self.c['id'])
   wallet.expire(d,expiry+1);wallet.expire(d,expiry+1)
  self.assertEqual(self.funds(self.a)['available_kobo'],10000);self.assertEqual(self.funds(self.a)['reserved_kobo'],0);wallet.provision_test_funds(self.server,self.a['id'],10000,'fixture-start')
  with self.assertRaises(ValueError):wallet.provision_test_funds(self.server,self.b['id'],10000,'fixture-start')
  self.server.wallet_fixtures=False
  with self.assertRaises(PermissionError):wallet.provision_test_funds(self.server,self.a['id'],1000,'blocked')
 def test_immutability_and_unbalanced_draft_rejection(self):
  self.users()
  for sql in ["UPDATE fin_postings SET amount=99","DELETE FROM fin_postings","UPDATE fin_journals SET description='changed'","DELETE FROM fin_journals","UPDATE fin_wallets SET owner='other'","UPDATE fin_accounts SET normal=1","DELETE FROM fin_audit"]:
   with self.assertRaises(sqlite3.IntegrityError):
    with self.server.db() as d:d.execute(sql)
  with self.assertRaises(sqlite3.IntegrityError):
   with self.server.db() as d:d.execute("INSERT INTO fin_journals VALUES('bad','bad','bad','bad',1,1,'bad')")
  with self.assertRaises(sqlite3.IntegrityError):
   with self.server.db() as d:
    d.execute("INSERT INTO fin_journals VALUES('bad','bad','bad','bad',1,0,'bad')");d.execute("INSERT INTO fin_postings VALUES('bad','test-treasury',1)");d.execute("UPDATE fin_journals SET posted=1 WHERE id='bad'")
  with self.server.db() as d:self.assertFalse(d.execute("SELECT 1 FROM fin_journals WHERE id='bad'").fetchone())
 def test_history_pagination_and_rolling_limit(self):
  self.users()
  for i in range(6):wallet.provision_test_funds(self.server,self.a['id'],1000000,'limit-fund-'+str(i))
  for i in range(5):self.send(self.quote(1000000),'limit-transfer-key-'+str(i))
  with self.assertRaises(urllib.error.HTTPError):self.send(self.quote(1),'limit-transfer-key-last')
  with self.server.db() as d:
   d.execute('BEGIN IMMEDIATE')
   for i in range(35):wallet.post_journal(d,'test_fixture','fixture','page-'+str(i),'TEST page fixture',{'test-treasury':1,wallet.account(d,self.c['id']):-1})
  first=self.call('/wallet/history',token=self.c['token']);second=self.call('/wallet/history?before='+str(first['next_before']),token=self.c['token']);self.assertEqual(len(first['transactions']),30);self.assertEqual(len(second['transactions']),5);self.assertFalse(set(t['id'] for t in first['transactions'])&set(t['id'] for t in second['transactions']))
 def test_insufficient_funds_roll_back(self):
  self.users();q=self.quote(20000)
  with self.assertRaises(urllib.error.HTTPError):self.send(q)
  with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM fin_journals WHERE posted=0').fetchone()[0],0);self.assertEqual(d.execute('SELECT COUNT(*) FROM fin_operations').fetchone()[0],0)
  self.assertEqual(self.funds(self.b)['available_kobo'],0)
 def test_registration_failure_rolls_back_account_and_wallet(self):
  from unittest.mock import patch
  with patch('wallet.create_wallet',side_effect=RuntimeError('fixture failure')):
   with self.assertRaises(urllib.error.HTTPError):self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Rollback','nickname':'rollback_wallet'})
  with self.server.db() as d:self.assertFalse(d.execute("SELECT 1 FROM users WHERE nickname='rollback_wallet'").fetchone());self.assertEqual(d.execute('SELECT COUNT(*) FROM fin_wallets').fetchone()[0],0)
 def test_server_restart_and_different_key_cannot_reuse_confirmation(self):
  import threading
  from server import ChatServer
  self.users();q=self.quote();self.send(q)
  with self.assertRaises(urllib.error.HTTPError):self.send(q,'another-idempotency-key')
  self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
  self.server=ChatServer(('127.0.0.1',0),self.tmp.name);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base='http://127.0.0.1:'+str(self.server.server_port)
  self.assertEqual(self.funds(self.a)['available_kobo'],9000);self.assertEqual(self.funds(self.b)['available_kobo'],1000);self.assertEqual(self.send(q)['status'],'posted')
  with self.assertRaises(PermissionError):wallet.provision_test_funds(self.server,self.a['id'],1000,'after-restart')
 def test_reserved_value_is_not_spendable_and_reconciliation_detects_draft(self):
  self.users()
  with self.server.db() as d:
   d.execute('BEGIN IMMEDIATE');wallet.reserve(d,self.a['id'],3000,'spend-hold',int(time.time())+120)
  with self.assertRaises(urllib.error.HTTPError):self.send(self.quote(8000))
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(self.a['id'],));d.execute("INSERT OR IGNORE INTO fin_permissions VALUES(?,'overview')",(self.a['id'],))
  wallet.init(self.server)
  with self.server.db() as d:d.execute("INSERT INTO fin_journals VALUES('draft-review','fixture','fixture','draft-review',1,0,'TEST draft')")
  overview=self.call('/wallet/overview',token=self.a['token']);self.assertFalse(overview['reconciliation']['balanced']);self.assertEqual(overview['reconciliation']['draft_journals'],1);self.assertEqual(self.funds(self.a)['available_kobo'],7000)

 def test_hold_expiry_maintenance_survives_gaming_task_failure(self):
  from unittest.mock import patch
  self.users()
  with self.server.db() as d:
   d.execute('BEGIN IMMEDIATE');wallet.reserve(d,self.a['id'],3000,'background-hold',int(time.time())+60)
  self.server.next_gamebox_tick=0
  with patch('gamebox_core.tick',side_effect=RuntimeError('fixture')),patch('wallet.time.time',return_value=time.time()+120),patch('builtins.print'):
   self.server._gamebox_service_actions()
  self.assertEqual(self.funds(self.a)['reserved_kobo'],0)

 def test_new_gaming_admin_does_not_inherit_finance_and_revocation_persists(self):
  self.users()
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(self.a['id'],))
  wallet.init(self.server)
  with self.assertRaises(urllib.error.HTTPError):self.call('/wallet/overview',token=self.a['token'])
  with self.server.db() as d:d.execute("INSERT INTO fin_permissions VALUES(?,'overview')",(self.a['id'],))
  self.assertTrue(self.call('/wallet/overview',token=self.a['token'])['reconciliation']['balanced'])
  with self.server.db() as d:d.execute('DELETE FROM fin_permissions WHERE owner=?',(self.a['id'],))
  wallet.init(self.server)
  with self.assertRaises(urllib.error.HTTPError):self.call('/wallet/overview',token=self.a['token'])
 def test_first_migration_bootstraps_only_existing_admin_reporting(self):
  self.users()
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(self.a['id'],));d.execute("DELETE FROM fin_meta WHERE key='overview_bootstrap'")
  wallet.init(self.server)
  self.assertTrue(self.call('/wallet/summary',token=self.a['token'])['finance_overview']);self.assertFalse(self.call('/wallet/summary',token=self.b['token'])['finance_overview'])
  with self.server.db() as d:d.execute('DELETE FROM fin_permissions')
  wallet.init(self.server)
  self.assertFalse(self.call('/wallet/summary',token=self.a['token'])['finance_overview'])
