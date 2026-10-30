import unittest, threading, tempfile, urllib.request, urllib.error, json, base64
from server import ChatServer
from pathlib import Path
class ChatTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.server=ChatServer(('127.0.0.1',0),self.tmp.name)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.base=f'http://127.0.0.1:{self.server.server_port}'
 def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
 def call(self,path,body=None,token=''):
  request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urllib.request.urlopen(request,timeout=5) as r:
   data=r.read();return json.loads(data) if r.headers.get_content_type()=='application/json' else data
 def register(self,name):
  user=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':name})
  # Existing transfer tests use explicitly paired test accounts.
  for other in getattr(self,'accounts',[]):self.call('/contacts',{'code':other['id']},user['token'])
  self.accounts=getattr(self,'accounts',[])+[user]
  return user
 def test_call_push_is_session_scoped_and_contains_no_media(self):
  a=self.register('Caller');b=self.register('Receiver');token='test-push-token-'+'a'*40
  self.call('/push/register',{'push_token':token},b['token'])
  self.call('/push/unregister',{'push_token':token},a['token'])
  class FakePush:
   enabled=True
   def __init__(self):self.events=[];self.ready=threading.Event()
   def send(self,token,data):self.events.append((token,data));self.ready.set()
  fake=FakePush();self.server.push=fake
  call=self.call('/calls/start',{'peer':b['id'],'offer':{'type':'offer','sdp':'test offer'}},a['token']);self.assertTrue(fake.ready.wait(2));self.assertEqual(fake.events[0][0],token);payload=fake.events[0][1];self.assertEqual(payload['event'],'call_ringing');self.assertEqual(payload['recipient'],b['id']);self.assertEqual(set(payload),{'event','call_id','recipient','expires_at'})
  fake.ready.clear();self.call('/calls/end',{'id':call['id']},a['token']);self.assertTrue(fake.ready.wait(2));self.assertEqual(fake.events[-1][1]['event'],'call_cancelled')
  self.call('/password',{'password':'test-pass-123'},b['token']);self.call('/logout',{},b['token'])
  with self.server.db() as db:active=list(db.execute('SELECT p.token FROM push_devices p JOIN sessions s ON s.token_hash=p.session_hash AND s.user_id=p.user_id WHERE p.user_id=?',(b['id'],)));self.assertEqual(active,[])
 def test_push_registration_requires_login(self):
  with self.assertRaises(urllib.error.HTTPError):self.call('/push/register',{'push_token':'x'*40})
 def test_protected_media_transfer_binding_and_recovery_denial(self):
  a=self.register('Sender');b=self.register('Receiver');device='original-'+'a'*40;other='replacement-'+'b'*40
  mid=self.call('/messages',{'peer':b['id'],'text':'Private caption','filename':'secret.png','mime':'image/png','data':base64.b64encode(b'protected').decode(),'client_id':'sealed','protected_media':True},a['token'])['id']
  visible=self.call('/messages?peer='+a['id'],token=b['token'])['messages'][0];self.assertEqual(visible['protected_media'],1);self.assertIsNone(visible['fileid']);self.assertEqual(visible['text'],'');self.assertNotIn('protected_device',visible)
  with self.assertRaises(urllib.error.HTTPError):self.call('/protected/open',{'message_id':mid,'device':device},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages/forward',{'message_id':mid,'peer':b['id'],'client_id':'blocked'},a['token'])
  item=self.call('/protected/open',{'message_id':mid,'device':device},b['token']);fid=item['fileid'];self.assertTrue(self.call('/message-status?id='+str(mid),token=b['token'])['protected_transfer_pending'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/files/'+fid,token=b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/protected/open',{'message_id':mid,'device':other},b['token'])
  request=urllib.request.Request(self.base+'/files/'+fid,headers={'Authorization':'Bearer '+b['token'],'X-View-Token':item['view_token'],'X-Protected-Device':device})
  with urllib.request.urlopen(request) as response:self.assertEqual(response.read(),b'protected')
  self.assertEqual(self.call('/media?peer='+a['id'],token=b['token'])['media'],[])
  self.call('/protected/received',{'message_id':mid,'device':device},b['token']);self.call('/protected/received',{'message_id':mid,'device':device},b['token'])
  self.assertFalse(self.server.file_path(fid,item['filename'],item['mime']).exists());self.assertFalse(self.call('/message-status?id='+str(mid),token=b['token'])['protected_transfer_pending'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/protected/open',{'message_id':mid,'device':other},b['token'])
  with self.server.db() as db:row=db.execute('SELECT text,fileid,protected_media FROM messages WHERE id=?',(mid,)).fetchone();self.assertIsNone(row['fileid']);self.assertEqual(row['text'],'');self.assertEqual(row['protected_media'],1)
 def test_protected_ack_never_removes_ordinary_media(self):
  a=self.register('Sender');b=self.register('Receiver');base={'peer':b['id'],'filename':'photo.png','mime':'image/png','data':base64.b64encode(b'photo').decode(),'client_id':'conflict','protected_media':True,'view_once':True}
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages',base,a['token'])
  base.update(client_id='ordinary',protected_media=False,view_once=False);mid=self.call('/messages',base,a['token'])['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/protected/received',{'message_id':mid,'device':'secret-'+'a'*40},b['token'])
  item=self.call('/messages?peer='+a['id'],token=b['token'])['messages'][0];self.assertEqual(self.call('/files/'+item['fileid'],token=b['token']),b'photo')
 def test_view_once_prefetch_does_not_consume_content(self):
  a=self.register('Sender');b=self.register('Receiver')
  mid=self.call('/messages',{'peer':b['id'],'text':'Caption','filename':'photo.png','mime':'image/png','data':base64.b64encode(b'photo').decode(),'client_id':'prefetch','view_once':True},a['token'])['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/once/download',{'message_id':mid},a['token'])
  item=self.call('/once/download',{'message_id':mid},b['token']);self.assertEqual(item['opened'],0)
  request=urllib.request.Request(self.base+'/files/'+item['fileid'],headers={'Authorization':'Bearer '+b['token'],'X-View-Token':item['view_token']})
  with urllib.request.urlopen(request) as response:self.assertEqual(response.read(),b'photo')
  opened=self.call('/open',{'message_id':mid},b['token']);self.assertEqual(opened['opened'],1)
  with self.assertRaises(urllib.error.HTTPError):self.call('/once/download',{'message_id':mid},b['token'])
  self.call('/close',{'message_id':mid},b['token'])
 def test_presence_is_account_scoped_and_expires(self):
  import time
  a=self.register('Present');b=self.register('Contact');stranger=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Stranger'})
  with self.assertRaises(urllib.error.HTTPError):self.call('/presence',{})
  self.call('/presence',{},a['token'])
  status=self.call('/profile?id='+a['id'],token=b['token']);self.assertTrue(status['online']);self.assertGreater(status['last_seen'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/profile?id='+a['id'],token=stranger['token'])
  with self.server.db() as db:db.execute('UPDATE users SET last_seen=? WHERE id=?',(int(time.time())-46,a['id']))
  status=self.call('/profile?id='+a['id'],token=b['token']);self.assertFalse(status['online']);self.assertGreater(status['last_seen'],0)
  self.assertFalse(next(u for u in self.call('/users',token=b['token'])['users'] if u['id']==a['id'])['online'])
 def test_multi_recipient_view_once_copies_are_independent(self):
  a=self.register('Sender');b=self.register('First');c=self.register('Second')
  body={'text':'Caption','view_once':True,'filename':'image.png','mime':'image/png','data':base64.b64encode(b'picture').decode()}
  first=self.call('/messages',dict(body,peer=b['id'],client_id='first-copy'),a['token'])['id'];second=self.call('/messages',dict(body,peer=c['id'],client_id='second-copy'),a['token'])['id']
  self.assertEqual(self.call('/messages',dict(body,peer=b['id'],client_id='first-copy'),a['token'])['id'],first)
  with self.server.db() as db:
   rows=list(db.execute('SELECT fileid,recipient,text,view_once FROM messages WHERE id IN (?,?)',(first,second)))
  self.assertEqual(len(rows),2);self.assertNotEqual(rows[0]['fileid'],rows[1]['fileid']);self.assertTrue(all(row['view_once'] and row['text']=='Caption' for row in rows))
 def test_voice_call_contact_authorization_and_lifecycle(self):
  a=self.register('Caller');b=self.register('Recipient');stranger=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Stranger'})
  offer={'type':'offer','sdp':'test offer'};answer={'type':'answer','sdp':'test answer'}
  with self.assertRaises(urllib.error.HTTPError):self.call('/calls/start',{'peer':stranger['id'],'offer':offer},a['token'])
  call=self.call('/calls/start',{'peer':b['id'],'offer':offer},a['token']);self.assertEqual(call['state'],'ringing')
  self.assertEqual(self.call('/calls',token=stranger['token'])['calls'],[])
  with self.assertRaises(urllib.error.HTTPError):self.call('/calls/answer',{'id':call['id'],'answer':answer},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/calls/end',{'id':call['id']},stranger['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/calls/start',{'peer':a['id'],'offer':offer},b['token'])
  active=self.call('/calls/answer',{'id':call['id'],'answer':answer},b['token']);self.assertEqual(active['state'],'active')
  self.assertEqual(self.call('/calls',token=a['token'])['calls'][0]['answer'],answer)
  ended=self.call('/calls/end',{'id':call['id']},a['token']);self.assertEqual(ended['state'],'ended');self.assertIsNone(ended['offer']);self.assertIsNone(ended['answer'])
 def test_voice_call_timeout_clears_signalling(self):
  a=self.register('Caller');b=self.register('Recipient');call=self.call('/calls/start',{'peer':b['id'],'offer':{'type':'offer','sdp':'offer'}},a['token'])
  with self.server.call_lock:self.server.calls[call['id']]['created']-=46
  ended=self.call('/calls',token=a['token'])['calls'][0];self.assertEqual(ended['state'],'ended');self.assertIsNone(ended['offer'])
 def test_call_history_is_account_scoped_and_keeps_connected_duration(self):
  a=self.register('Caller');b=self.register('Recipient');c=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Other account'})
  call=self.call('/calls/start',{'peer':b['id'],'offer':{'type':'offer','sdp':'offer'}},a['token'])
  self.call('/calls/answer',{'id':call['id'],'answer':{'type':'answer','sdp':'answer'}},b['token'])
  first=self.call('/calls/connected',{'id':call['id']},a['token'])['connected']
  self.assertEqual(self.call('/calls/connected',{'id':call['id']},b['token'])['connected'],first)
  with self.server.db() as db:db.execute('UPDATE call_history SET connected=connected-5 WHERE id=?',(call['id'],))
  self.call('/calls/end',{'id':call['id']},b['token'])
  outgoing=self.call('/call-history',token=a['token'])['calls'][0];incoming=self.call('/call-history',token=b['token'])['calls'][0]
  self.assertEqual(outgoing['peer'],b['id']);self.assertEqual(outgoing['direction'],'outgoing');self.assertEqual(incoming['direction'],'incoming');self.assertEqual(outgoing['outcome'],'completed');self.assertGreaterEqual(outgoing['duration'],5)
  self.assertEqual(self.call('/call-history?uid='+a['id'],token=c['token'])['calls'],[])
  with self.assertRaises(urllib.error.HTTPError):self.call('/calls/connected',{'id':call['id']},c['token'])
 def test_call_history_survives_server_restart(self):
  a=self.register('Caller');b=self.register('Recipient');call=self.call('/calls/start',{'peer':b['id'],'offer':{'type':'offer','sdp':'offer'}},a['token']);self.call('/calls/end',{'id':call['id']},a['token'])
  self.server.shutdown();self.server.server_close();self.server=ChatServer(('127.0.0.1',0),self.tmp.name,reset_call_history=True);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.base=f'http://127.0.0.1:{self.server.server_port}'
  history=self.call('/call-history',token=a['token'])['calls'];self.assertEqual(history[0]['id'],call['id']);self.assertEqual(history[0]['outcome'],'cancelled');self.assertEqual(len(self.call('/messages?peer='+b['id'],token=a['token'])['messages']),1)
 def test_media_library_is_conversation_scoped_and_excludes_view_once(self):
  a=self.register('A');b=self.register('B');c=self.register('C');outsider=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Outsider'})
  for once in [False,True]:self.call('/messages',{'peer':b['id'],'text':'','client_id':str(once),'filename':'photo.png','mime':'image/png','data':base64.b64encode(b'image test').decode(),'view_once':once},a['token'])
  self.call('/messages',{'peer':c['id'],'text':'','client_id':'other-chat','filename':'other.png','mime':'image/png','data':base64.b64encode(b'other image').decode()},a['token'])
  for owner,peer in [(a,b),(b,a)]:
   media=self.call('/media?peer='+peer['id'],token=owner['token'])['media'];self.assertEqual(len(media),1);self.assertEqual(media[0]['filename'],'photo.png');self.assertEqual(media[0]['view_once'],0);self.assertNotIn('lease_hash',media[0])
  self.assertEqual(self.call('/media?peer='+c['id'],token=b['token'])['media'],[])
  for path,token in [('/media',a['token']),('/media?peer='+b['id'],outsider['token'])]:
   with self.assertRaises(urllib.error.HTTPError):self.call(path,token=token)
 def test_delete_everyone_is_sender_only_and_revokes_file_access(self):
  a=self.register('Sender');b=self.register('Recipient');c=self.register('Other')
  mid=self.call('/messages',{'peer':b['id'],'text':'original secret','client_id':'everyone','filename':'photo.png','mime':'image/png','data':base64.b64encode(b'photo data').decode()},a['token'])['id']
  fid=self.call('/media?peer='+a['id'],token=b['token'])['media'][0]['fileid']
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages/delete',{'message_id':mid,'scope':'everyone'},b['token'])
  self.call('/messages/delete',{'message_id':mid,'scope':'everyone'},a['token'])
  for owner,peer in [(a,b),(b,a)]:
   result=self.call('/messages?peer='+peer['id']+'&after='+str(mid),token=owner['token']);self.assertIn(mid,result['deleted_ids'])
   placeholder=self.call('/messages?peer='+peer['id'],token=owner['token'])['messages'][0];self.assertEqual(placeholder['deleted_all'],1);self.assertNotIn('original secret',json.dumps(placeholder));self.assertIsNone(placeholder['fileid'])
   with self.assertRaises(urllib.error.HTTPError):self.call('/files/'+fid,token=owner['token'])
  self.assertTrue(self.call('/message-status?id='+str(mid),token=b['token'])['deleted'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/message-status?id='+str(mid),token=c['token'])
  self.assertEqual(self.call('/media?peer='+a['id'],token=b['token'])['media'],[])
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages/forward',{'message_id':mid,'peer':c['id'],'client_id':'revoked'},a['token'])
 def test_video_call_type_is_preserved_in_history_and_chat(self):
  a=self.register('A');b=self.register('B');offer={'type':'offer','sdp':'video offer'}
  with self.assertRaises(urllib.error.HTTPError):self.call('/calls/start',{'peer':b['id'],'kind':'invalid','offer':offer},a['token'])
  call=self.call('/calls/start',{'peer':b['id'],'kind':'video','offer':offer},a['token']);self.assertEqual(call['kind'],'video');self.assertEqual(self.call('/calls',token=b['token'])['calls'][0]['kind'],'video')
  self.call('/calls/end',{'id':call['id']},a['token']);event=self.call('/messages?peer='+a['id'],token=b['token'])['messages'][0]['call'];self.assertEqual(event['kind'],'video');self.assertEqual(event['label'],'Missed video call');self.assertEqual(self.call('/call-history',token=a['token'])['calls'][0]['kind'],'video')
 def test_forward_delete_and_reply_are_scoped_and_view_once_is_protected(self):
  a=self.register('A');b=self.register('B');c=self.register('C')
  m=self.call('/messages',{'peer':b['id'],'text':'Photo caption','client_id':'original','filename':'picture.png','mime':'image/png','data':base64.b64encode(b'picture').decode()},a['token'])['id']
  once=self.call('/messages',{'peer':b['id'],'text':'private','client_id':'once','view_once':True},a['token'])['id']
  for sender,mid in [(c,m),(b,once)]:
   with self.assertRaises(urllib.error.HTTPError):self.call('/messages/forward',{'message_id':mid,'peer':a['id'],'client_id':'denied'},sender['token'])
  forwarded=self.call('/messages/forward',{'message_id':m,'peer':c['id'],'client_id':'forward'},b['token'])['id'];self.assertEqual(self.call('/messages/forward',{'message_id':m,'peer':c['id'],'client_id':'forward'},b['token'])['id'],forwarded)
  copy=self.call('/media?peer='+b['id'],token=c['token'])['media'][0];self.assertEqual(self.call('/files/'+copy['fileid'],token=c['token']),b'picture')
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages',{'peer':c['id'],'text':'wrong reply','client_id':'badreply','reply_to':m},a['token'])
  self.call('/messages',{'peer':b['id'],'text':'reply','client_id':'reply','reply_to':once},a['token']);quoted=self.call('/messages?peer='+a['id'],token=b['token'])['messages'][-1]['reply'];self.assertEqual(quoted['text'],'View-once content');self.assertNotIn('private',json.dumps(quoted))
  self.call('/messages/delete',{'message_id':m},b['token']);self.assertNotIn(m,[x['id'] for x in self.call('/messages?peer='+a['id'],token=b['token'])['messages']]);self.assertIn(m,[x['id'] for x in self.call('/messages?peer='+b['id'],token=a['token'])['messages']]);self.assertEqual(self.call('/media?peer='+a['id'],token=b['token'])['media'],[])
  self.call('/chats/delete',{'peer':a['id']},b['token']);self.assertNotIn(a['id'],[x['id'] for x in self.call('/users',token=b['token'])['users']]);self.assertEqual(self.call('/messages?peer='+a['id'],token=b['token'])['messages'],[])
  self.call('/messages',{'peer':b['id'],'text':'new','client_id':'new'},a['token']);self.assertIn(a['id'],[x['id'] for x in self.call('/users',token=b['token'])['users']])
 def test_chat_list_uses_latest_activity_time_in_both_directions(self):
  owner=self.register('Owner');a=self.register('Alpha');z=self.register('Zebra');quiet=self.register('Quiet')
  first=self.call('/messages',{'peer':a['id'],'text':'Incoming','client_id':'incoming'},owner['token'])['id']
  second=self.call('/messages',{'peer':owner['id'],'text':'Recent reply','client_id':'reply'},z['token'])['id']
  with self.server.db() as db:
   db.execute('UPDATE messages SET time=2000 WHERE id=?',(first,));db.execute('UPDATE messages SET time=1000 WHERE id=?',(second,))
  users=self.call('/users',token=owner['token'])['users'];self.assertEqual([u['id'] for u in users],[a['id'],z['id'],quiet['id']])
  with self.server.db() as db:db.execute('UPDATE messages SET time=3000 WHERE id=?',(second,))
  self.assertEqual(self.call('/users',token=owner['token'])['users'][0]['id'],z['id'])
  call=self.call('/calls/start',{'peer':a['id'],'offer':{'type':'offer','sdp':'offer'}},owner['token']);self.call('/calls/end',{'id':call['id']},owner['token'])
  users=self.call('/users',token=owner['token'])['users'];self.assertEqual(users[0]['id'],a['id']);self.assertIn('audio call',users[0]['preview'])
 def test_call_message_is_unique_and_missed_label_is_per_account(self):
  a=self.register('A');b=self.register('B');call=self.call('/calls/start',{'peer':b['id'],'offer':{'type':'offer','sdp':'private signalling'}},a['token'])
  self.call('/calls/end',{'id':call['id']},a['token']);self.call('/calls/end',{'id':call['id']},a['token'])
  mine=self.call('/messages?peer='+b['id'],token=a['token'])['messages'];theirs=self.call('/messages?peer='+a['id'],token=b['token'])['messages']
  self.assertEqual(len(mine),1);self.assertEqual(mine[0]['kind'],'call');self.assertEqual(mine[0]['call']['label'],'Cancelled outgoing audio call');self.assertEqual(theirs[0]['call']['label'],'Missed audio call');self.assertTrue(theirs[0]['call']['missed']);self.assertNotIn('private signalling',json.dumps(mine))
  self.assertEqual(self.call('/users',token=b['token'])['users'][0]['preview'],'Missed audio call')
 def test_password_change_requires_current_password(self):
  a=self.register('Password account')
  self.call('/password',{'password':'first passphrase 123'},a['token'])
  for old in ['', 'wrong password']:
   with self.assertRaises(urllib.error.HTTPError):self.call('/password',{'password':'second passphrase 456','current_password':old},a['token'])
  self.call('/password',{'password':'second passphrase 456','current_password':'first passphrase 123'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/login',{'identity':a['id'],'password':'first passphrase 123'})
  self.assertEqual(self.call('/login',{'identity':a['id'],'password':'second passphrase 456'})['id'],a['id'])
 def test_account_login_keeps_data_and_revokes_only_logged_out_session(self):
  a=self.register('Account A');b=self.register('Account B')
  mid=self.call('/messages',{'peer':b['id'],'text':'Account-owned history','client_id':'history'},a['token'])['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/logout',{},a['token'])
  self.call('/password',{'password':'test passphrase 123'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/password',{'password':'overwrite password'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/login',{'identity':a['id'],'password':'incorrect'})
  signed=self.call('/login',{'identity':a['nickname'],'password':'test passphrase 123'})
  self.assertEqual(signed['id'],a['id'])
  self.assertEqual(self.call('/messages?peer='+b['id']+'&after=0',token=signed['token'])['messages'][0]['id'],mid)
  self.call('/logout',{},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/users',token=a['token'])
  self.assertEqual(self.call('/users',token=signed['token'])['users'][0]['id'],b['id'])
  c=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Account C'});self.assertEqual(self.call('/users',token=c['token'])['users'],[])
 def test_video_above_old_limit(self):
  a=self.register('Video sender');b=self.register('Video recipient')
  payload=base64.b64encode(b'v'*(8*1024*1024+1)).decode()
  body={'peer':b['id'],'client_id':'large-video','filename':'clip.mp4','mime':'video/mp4','data':payload}
  result=self.call('/messages',body,a['token']);self.assertGreater(result['id'],0)
  body.update(client_id='large-image',filename='image.jpg',mime='image/jpeg')
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/messages',body,a['token'])
  self.assertEqual(e.exception.code,413)
 def test_private_contacts_and_required_pairing(self):
  a=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'A'})
  b=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'B'})
  c=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'C'})
  self.assertEqual(self.call('/users',token=a['token'])['users'],[])
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/messages',{'peer':b['id'],'text':'blocked','client_id':'before'},a['token'])
  self.assertEqual(e.exception.code,403)
  for code in [a['id'],'unknown']:
   with self.assertRaises(urllib.error.HTTPError):self.call('/contacts',{'code':code},a['token'])
  self.call('/contacts',{'code':b['id'].upper()},a['token'])
  self.call('/contacts',{'code':b['id']},a['token'])
  self.assertEqual([u['id'] for u in self.call('/users',token=a['token'])['users']],[b['id']])
  self.assertEqual([u['id'] for u in self.call('/users',token=b['token'])['users']],[a['id']])
  self.assertEqual(self.call('/users',token=c['token'])['users'],[])
  self.call('/messages',{'peer':b['id'],'text':'allowed','client_id':'after'},a['token'])
 def test_real_transfer_and_access_boundaries(self):
  a,b,c=[self.register(n) for n in ['David','Test friend','Third account']]
  payload={'peer':b['id'],'text':'Test message','client_id':'unique-1','filename':'../../note.txt','mime':'text/plain','data':base64.b64encode(b'test attachment').decode()}
  sent=self.call('/messages',payload,a['token']);retry=self.call('/messages',payload,a['token']);self.assertEqual(sent,retry)
  received=self.call('/messages?peer='+a['id'],token=b['token'])['messages'];self.assertEqual(len(received),1);self.assertEqual(received[0]['filename'],'note.txt')
  fid=received[0]['fileid'];self.assertEqual(self.call('/files/'+fid,token=b['token']),b'test attachment')
  saved=self.server.file_path(fid,'note.txt','text/plain')
  self.assertTrue(saved.is_file());self.assertEqual(saved.suffix,'.txt');self.assertEqual(saved.read_bytes(),b'test attachment')
  legacy=Path(self.tmp.name)/'files'/fid;saved.rename(legacy)
  self.server.migrate_files();self.assertTrue(saved.exists());self.assertFalse(legacy.exists())
  self.assertEqual(self.call('/files/'+fid,token=b['token']),b'test attachment')
  with self.assertRaises(urllib.error.HTTPError) as error:self.call('/files/'+fid,token=c['token'])
  self.assertEqual(error.exception.code,404)
  self.assertEqual(self.call('/messages?peer='+a['id'],token=c['token'])['messages'],[])
  with self.assertRaises(urllib.error.HTTPError) as error:self.call('/users')
  self.assertEqual(error.exception.code,401)
 def test_unread_counts_and_scoped_read(self):
  a,b,c=[self.register(n) for n in ['A','B','C']]
  first=self.call('/messages',{'peer':b['id'],'text':'one','client_id':'one'},a['token'])
  second=self.call('/messages',{'peer':b['id'],'text':'two','client_id':'two'},a['token'])
  users=self.call('/users',token=b['token'])['users'];self.assertEqual(next(u for u in users if u['id']==a['id'])['unread'],2)
  self.call('/read',{'peer':a['id'],'through':second['id']},c['token'])
  self.call('/read',{'peer':a['id'],'through':first['id']},b['token'])
  users=self.call('/users',token=b['token'])['users'];self.assertEqual(next(u for u in users if u['id']==a['id'])['unread'],1)
  self.call('/read',{'peer':a['id'],'through':second['id']},b['token'])
  users=self.call('/users',token=b['token'])['users'];self.assertEqual(next(u for u in users if u['id']==a['id'])['unread'],0)
 def test_delivery_and_read_receipts_belong_to_recipient(self):
  a,b,c=[self.register(n) for n in ['A','B','C']]
  sent=self.call('/messages',{'peer':b['id'],'text':'receipt','client_id':'receipt'},a['token'])
  def receipt():return self.call('/receipts?peer='+b['id'],token=a['token'])['receipts'][0]
  self.assertEqual(receipt()['delivered_at'],0);self.assertEqual(receipt()['read_at'],0)
  self.assertEqual(self.call('/inbox',token=b['token'])['ids'],[sent['id']])
  self.call('/delivered',{'ids':[sent['id']]},c['token']);self.assertEqual(receipt()['delivered_at'],0)
  self.call('/delivered',{'ids':[sent['id']]},b['token']);self.assertGreater(receipt()['delivered_at'],0);self.assertEqual(receipt()['read_at'],0)
  self.call('/read',{'peer':a['id'],'through':sent['id']},b['token']);self.assertGreater(receipt()['read_at'],0)
  self.assertEqual(self.call('/receipts?peer='+b['id'],token=c['token'])['receipts'],[])
 def test_legacy_messages_do_not_become_new_unread(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as folder:
   with sqlite3.connect(Path(folder)/'chat.sqlite') as db:
    db.execute('CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,sender TEXT,recipient TEXT,text TEXT,filename TEXT,mime TEXT,fileid TEXT,size INTEGER,time INTEGER,client_id TEXT,UNIQUE(sender,client_id))')
    db.execute("INSERT INTO messages(sender,recipient,text,time,client_id) VALUES('a','b','old',1,'legacy')")
   migrated=ChatServer(('127.0.0.1',0),folder)
   try:
    with migrated.db() as db:self.assertGreater(db.execute('SELECT read_at FROM messages').fetchone()[0],0)
   finally:migrated.server_close()
 def test_profiles_nicknames_and_private_contact_card(self):
  a=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Alice','nickname':'Alice_Test'})
  b=self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Bob','nickname':'bob_test'})
  self.assertEqual(a['nickname'],'alice_test')
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/register',{'invite':self.server.invite,'birth_date':'1995-05-05','sex':'undisclosed','name':'Duplicate','nickname':'ALICE_TEST'})
  self.assertEqual(e.exception.code,409)
  with self.assertRaises(urllib.error.HTTPError):self.call('/profile?id='+a['id'],token=b['token'])
  self.call('/contacts',{'code':'@ALICE_TEST'},b['token'])
  card=self.call('/profile?id='+a['id'],token=b['token']);self.assertEqual(card['id'],a['id']);self.assertNotIn('token_hash',card)
  changed=self.call('/profile',{'nickname':'new_alice','name':'Alice Updated'},a['token']);self.assertEqual(changed['id'],a['id'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/profile',{'nickname':'BOB_TEST'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/profile',{'avatar':base64.b64encode(b'<svg/>').decode(),'avatar_mime':'image/svg+xml'},a['token'])
  self.assertEqual(self.call('/profile',token=a['token'])['nickname'],'new_alice')
 def test_filename_extension_and_safety(self):
  path=self.server.file_path('123','../../photo','image/jpeg')
  self.assertEqual(path.name,'photo__123.jpg');self.assertEqual(path.parent,Path(self.tmp.name)/'files')
  self.assertEqual(self.server.file_path('456','photo','image/jpeg').name,'photo__456.jpg')
 def test_bad_invite_and_bad_recipient(self):
  with self.assertRaises(urllib.error.HTTPError):self.call('/register',{'invite':'wrong','name':'Nobody'})
  a=self.register('David')
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages',{'peer':'missing','text':'hello','client_id':'1'},a['token'])
 def test_oversized_file_and_invalid_base64(self):
  a,b=self.register('David'),self.register('Friend')
  for data in ['not valid base64!',base64.b64encode(b'x'*(8*1024*1024+1)).decode()]:
   with self.assertRaises(urllib.error.HTTPError):self.call('/messages',{'peer':b['id'],'client_id':'large','data':data},a['token'])
 def test_view_once_access_and_no_second_open(self):
  a,b,c=[self.register(n) for n in ['Sender','Recipient','Other']]
  sent=self.call('/messages',{'peer':b['id'],'text':'secret test text','client_id':'once1','view_once':True,'filename':'private.txt','mime':'text/plain','data':base64.b64encode(b'private test bytes').decode()},a['token'])
  listing=self.call('/messages?peer='+a['id'],token=b['token'])['messages'][0]
  self.assertEqual(listing['text'],'');self.assertIsNone(listing['fileid']);self.assertEqual(listing['view_once'],1)
  with self.server.db() as db:fid=db.execute('SELECT fileid FROM messages WHERE id=?',(sent['id'],)).fetchone()['fileid']
  with self.assertRaises(urllib.error.HTTPError):self.call('/files/'+fid,token=b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/open',{'message_id':sent['id']},c['token'])
  opened=self.call('/open',{'message_id':sent['id']},b['token']);self.assertEqual(opened['text'],'secret test text')
  req=urllib.request.Request(self.base+'/files/'+fid,headers={'Authorization':'Bearer '+b['token'],'X-View-Token':opened['view_token']})
  with urllib.request.urlopen(req) as r:self.assertEqual(r.read(),b'private test bytes')
  with self.assertRaises(urllib.error.HTTPError) as error:self.call('/open',{'message_id':sent['id']},b['token'])
  self.assertEqual(error.exception.code,409)
  self.call('/close',{'message_id':sent['id']},b['token'])
  with self.server.db() as db:
   cleared=db.execute('SELECT * FROM messages WHERE id=?',(sent['id'],)).fetchone()
  self.assertEqual(cleared['text'],'');self.assertIsNone(cleared['fileid']);self.assertIsNone(cleared['filename'])
  self.assertFalse(self.server.file_path(fid,'private.txt','text/plain').exists())
  self.assertEqual(self.call('/messages?peer='+b['id'],token=a['token'])['messages'][0]['text'],'')
  with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(req)
  self.assertEqual(self.call('/messages?peer='+a['id'],token=b['token'])['messages'][0]['opened'],1)
 def test_expired_view_deletes_content(self):
  a,b=self.register('Sender'),self.register('Recipient')
  sent=self.call('/messages',{'peer':b['id'],'text':'expiry test','client_id':'expiry','view_once':True,'filename':'photo.jpg','mime':'image/jpeg','data':base64.b64encode(b'image bytes').decode()},a['token'])
  opened=self.call('/open',{'message_id':sent['id']},b['token'])
  path=self.server.file_path(opened['fileid'],'photo.jpg','image/jpeg')
  with self.server.db() as db:db.execute('UPDATE messages SET lease_until=0 WHERE id=?',(sent['id'],))
  self.server.expire_views();self.assertFalse(path.exists())
  with self.server.db() as db:row=db.execute('SELECT * FROM messages WHERE id=?',(sent['id'],)).fetchone()
  self.assertEqual(row['text'],'');self.assertIsNone(row['fileid'])
 def test_view_once_text_and_unsupported_file(self):
  a,b=self.register('Sender'),self.register('Recipient')
  sent=self.call('/messages',{'peer':b['id'],'text':'text-only private test','client_id':'once-text','view_once':True},a['token'])
  self.assertEqual(self.call('/open',{'message_id':sent['id']},b['token'])['text'],'text-only private test')
  with self.assertRaises(urllib.error.HTTPError):self.call('/messages',{'peer':b['id'],'client_id':'once-file','view_once':True,'mime':'application/zip','data':base64.b64encode(b'zip').decode()},a['token'])
 def test_chat_pin_and_clear_are_account_specific(self):
  a=self.register('Alice');b=self.register('Bob');c=self.register('Chris')
  self.call('/messages',{'peer':b['id'],'text':'Keep for Bob','client_id':'clear-test'},a['token'])
  self.call('/chats/pin',{'peer':b['id'],'pinned':True},a['token'])
  rows=self.call('/users',token=a['token'])['users'];self.assertEqual(rows[0]['id'],b['id']);self.assertTrue(rows[0]['pinned'])
  self.assertFalse(next(r for r in self.call('/users',token=b['token'])['users'] if r['id']==a['id'])['pinned'])
  self.call('/chats/clear',{'peer':b['id']},a['token'])
  self.assertEqual(self.call('/messages?peer='+b['id'],token=a['token'])['messages'],[])
  self.assertEqual(len(self.call('/messages?peer='+a['id'],token=b['token'])['messages']),1)
  self.assertIn(b['id'],[r['id'] for r in self.call('/users',token=a['token'])['users']])
  self.call('/chats/pin',{'peer':b['id'],'pinned':False},a['token'])
  self.assertFalse(next(r for r in self.call('/users',token=a['token'])['users'] if r['id']==b['id'])['pinned'])
if __name__=='__main__':unittest.main()
