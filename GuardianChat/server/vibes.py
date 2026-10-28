"""Expiring account Vibes. Every media read rechecks audience, block and expiry."""
import base64,hashlib,io,json,time,uuid
from pathlib import Path
from PIL import Image
HOURS=(12,24,48)
EMOJI=('❤️','🔥','😂','👏','😮','🎉')

def init(server):
 with server.db() as d:d.executescript('''
 CREATE TABLE IF NOT EXISTS vibe_settings(uid TEXT PRIMARY KEY,public_hours INTEGER NOT NULL DEFAULT 24,private_hours INTEGER NOT NULL DEFAULT 24);
 CREATE TABLE IF NOT EXISTS vibe_items(id TEXT PRIMARY KEY,uid TEXT NOT NULL,visibility TEXT NOT NULL,mime TEXT NOT NULL,media BLOB,caption TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,client_id TEXT NOT NULL,digest TEXT NOT NULL,UNIQUE(uid,client_id));
 CREATE TABLE IF NOT EXISTS vibe_audience(item TEXT NOT NULL,uid TEXT NOT NULL,PRIMARY KEY(item,uid));
 CREATE TABLE IF NOT EXISTS vibe_views(item TEXT NOT NULL,uid TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,opens INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(item,uid));
 CREATE TABLE IF NOT EXISTS vibe_reactions(item TEXT NOT NULL,uid TEXT NOT NULL,emoji TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(item,uid));
 CREATE INDEX IF NOT EXISTS vibe_active ON vibe_items(expires,uid,visibility);
 CREATE TABLE IF NOT EXISTS vibe_replies(message_id INTEGER PRIMARY KEY,item TEXT NOT NULL,visibility TEXT NOT NULL,sender TEXT NOT NULL,client_id TEXT NOT NULL,UNIQUE(sender,client_id));
 ''')
 with server.db() as d:
  d.execute('CREATE TABLE IF NOT EXISTS vibe_media_metadata(item TEXT PRIMARY KEY,asset TEXT,duration_ms INTEGER NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL)')
  __import__('vibe_sources').schema(d)
  __import__('vibe_privacy').schema(d)

def recipients(d,uid,visibility,audience):
 if not isinstance(audience,list) or len(audience)>200 or any(not isinstance(x,str) for x in audience):raise ValueError('Choose valid private recipients')
 if visibility!='private':return []
 if not audience:raise ValueError('Choose at least one existing contact for this Private Vibe')
 import social
 for target in set(audience):
  if not d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,target)).fetchone() or social.blocked(d,uid,target) or not __import__('vibe_privacy').permitted(d,target,uid,'private'):raise PermissionError('Private Vibe recipients must be your available, permitted contacts')
 return sorted(set(audience))

def preferences(d,uid):
 r=d.execute('SELECT * FROM vibe_settings WHERE uid=?',(uid,)).fetchone()
 return dict(r) if r else {'public_hours':24,'private_hours':24}

def allowed(d,uid,item,now=None):
 import social
 if item is None or item['expires']<=(int(time.time()) if now is None else now) or item['media'] is None:return False
 if item['uid']==uid:return True
 if social.blocked(d,uid,item['uid']) or not __import__('vibe_privacy').permitted(d,uid,item['uid'],item['visibility']):return False
 return item['visibility']=='public' or bool(d.execute('SELECT 1 FROM vibe_audience a JOIN contacts c ON c.owner=? AND c.peer=a.uid WHERE a.item=? AND a.uid=?',(item['uid'],item['id'],uid)).fetchone())

def item(d,uid,ident):
 r=d.execute('SELECT * FROM vibe_items WHERE id=?',(ident,)).fetchone()
 if not allowed(d,uid,r):raise PermissionError('This Vibe expired or is unavailable to your account')
 return r

def cache_tag(r,source):
 return r['digest']+':'+hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()

def get(server,uid,action,q):
 if action=='privacy':return __import__('vibe_privacy').get(server,uid)
 with server.db() as d:
  if action=='prompts':return {'prompts':__import__('vibe_sources').prompts(d,uid)}
  if action=='achievements':
   target=q.get('id',[uid])[0];game=q.get('game',[''])[0]
   records=[]
   for source in __import__('vibe_sources').prompts(d,target,True):
    if game and source['game']!=game:continue
    try:records.append(__import__('vibe_sources').resolve(d,uid,target,source['kind'],source['source'],source['game']))
    except (ValueError,PermissionError):continue
   return {'achievements':records}
  if action=='item':
   r=item(d,uid,q.get('id',[''])[0]);u=d.execute('SELECT id,name,nickname FROM users WHERE id=?',(r['uid'],)).fetchone()
   return {'group':dict(u)|{'uid':r['uid'],'items':[{'id':r['id'],'expires':r['expires'],'viewed':False}]},'visibility':r['visibility']}
  if action=='milestone_policy':
   __import__('gamebox_core').authorised(d,uid)
   return {'thresholds':json.loads(d.execute('SELECT thresholds FROM vibe_milestone_policy WHERE id=1').fetchone()[0])}
  if action=='feed':
   visibility=q.get('visibility',['public'])[0]
   if visibility not in ('public','private'):raise ValueError('Choose Public or Private Vibe')
   groups={}
   for r in d.execute('SELECT i.id,i.uid,i.visibility,i.mime,i.caption,i.created,i.expires,1 AS media,u.name,u.nickname,u.avatar,u.avatar_mime FROM vibe_items i JOIN users u ON u.id=i.uid WHERE i.visibility=? AND i.expires>? AND i.media IS NOT NULL ORDER BY i.created,i.rowid',(visibility,int(time.time()))):
    if not allowed(d,uid,r) or __import__('vibe_privacy').muted(d,uid,r['uid']):continue
    contact=bool(d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,r['uid'])).fetchone())
    following=bool(d.execute("SELECT 1 FROM social_follows WHERE follower=? AND target=? AND state='accepted'",(uid,r['uid'])).fetchone())
    group=groups.setdefault(r['uid'],{'uid':r['uid'],'name':r['name'],'nickname':r['nickname'],'contact':contact,'following':following,'avatar':r['avatar'] if contact or r['uid']==uid else None,'avatar_mime':r['avatar_mime'] if contact or r['uid']==uid else None,'items':[]})
    v=d.execute('SELECT 1 FROM vibe_views WHERE item=? AND uid=?',(r['id'],uid)).fetchone()
    source=__import__('vibe_sources').linked(d,uid,r)
    group['items'].append({'source_version':hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest() if source else None,'id':r['id'],'created':r['created'],'expires':r['expires'],'caption':r['caption'] if visibility=='public' or r['uid']==uid else '', 'mime':r['mime'],'viewed':bool(v),'views':d.execute('SELECT COUNT(*) FROM vibe_views WHERE item=?',(r['id'],)).fetchone()[0] if r['uid']==uid else None})
   own=d.execute('SELECT id,name,nickname,avatar,avatar_mime FROM users WHERE id=?',(uid,)).fetchone()
   ordered=sorted(groups.values(),key=lambda g:(all(i['viewed'] for i in g['items']),-max(i['created'] for i in g['items']),g['uid']))
   return {'groups':ordered,'account':dict(own),'preferences':preferences(d,uid),'emoji':EMOJI}
  if action=='preview':
   r=item(d,uid,q.get('id',[''])[0])
   # Private media stays in the protected viewer, including thumbnails.
   if r['visibility']=='private':raise PermissionError('Private previews stay in the protected viewer')
   source=__import__('vibe_sources').linked(d,uid,r)
   raw=__import__('vibe_sources').card(d,source) if source else r['media']
   from PIL import ImageOps
   if r['mime'].startswith('image/'):
    with Image.open(io.BytesIO(raw)) as im:preview=ImageOps.exif_transpose(im).convert('RGB')
   else:
    import av
    with av.open(io.BytesIO(r['media'])) as container:
     preview=next(container.decode(video=0)).to_image().convert('RGB')
   preview.thumbnail((160,160));out=io.BytesIO();preview.save(out,format='JPEG',quality=75)
   return {'data':base64.b64encode(out.getvalue()).decode(),'mime':'image/jpeg','expires':r['expires']}
  if action=='status':
   r=item(d,uid,q.get('id',[''])[0]);source=__import__('vibe_sources').linked(d,uid,r)
   response={'active':True,'expires':r['expires'],'server_now':int(time.time()),'visibility':r['visibility'],'source':source if r['visibility']=='public' else None,'source_available':source is None or source['available']}
   if r['visibility']=='public':response.update(cache_tag=cache_tag(r,source),relationship=__import__('social').public(d,uid,r['uid'])['relationship'],view_count=d.execute('SELECT COUNT(*) FROM vibe_views WHERE item=?',(r['id'],)).fetchone()[0] if r['uid']==uid else None)
   return response
  if action=='viewers':
   r=item(d,uid,q.get('id',[''])[0])
   if r['uid']!=uid:raise PermissionError('Only the author can inspect viewers')
   return {'viewers':[dict(v) for v in d.execute('SELECT v.uid,u.name,u.nickname,v.first_seen,v.last_seen,v.opens,r.emoji FROM vibe_views v JOIN users u ON u.id=v.uid LEFT JOIN vibe_reactions r ON r.item=v.item AND r.uid=v.uid WHERE v.item=? ORDER BY v.last_seen DESC',(r['id'],))]}
  raise ValueError('Unknown Vibe action')

def media(server,uid,ident,protected=False):
 with server.db() as d:
  r=item(d,uid,ident)
  if r['visibility']=='private' and not protected:raise PermissionError('Open Private Vibe in the GuardianLab-protected Android viewer')
  source=__import__('vibe_sources').linked(d,uid,r);raw=__import__('vibe_sources').card(d,source) if source else r['media']
  queue=[x['id'] for x in d.execute('SELECT id,uid,visibility,expires,1 AS media FROM vibe_items WHERE uid=? AND visibility=? AND expires>? AND media IS NOT NULL ORDER BY created,rowid',(r['uid'],r['visibility'],int(time.time()))) if allowed(d,uid,x)]
  index=queue.index(r['id']) if r['id'] in queue else -1
  metadata=d.execute('SELECT duration_ms,start_ms,end_ms FROM vibe_media_metadata WHERE item=?',(ident,)).fetchone()
  return {'cache_tag':cache_tag(r,source) if r['visibility']=='public' else None,'data':base64.b64encode(raw).decode(),'mime':r['mime'],'expires':r['expires'],'server_now':int(time.time()),'caption':r['caption'],'uid':r['uid'],'visibility':r['visibility'],'source':source,'relationship':__import__('social').public(d,uid,r['uid'])['relationship'],'next_id':queue[index+1] if 0<=index<len(queue)-1 else None,'previous_id':queue[index-1] if index>0 else None,'view_count':d.execute('SELECT COUNT(*) FROM vibe_views WHERE item=?',(ident,)).fetchone()[0] if r['uid']==uid else None}|(dict(metadata) if metadata else {})

def validate(b):
 try:raw=base64.b64decode(b.get('media',''),validate=True)
 except Exception as e:raise ValueError('Invalid Vibe media') from e
 mime=str(b.get('mime',''))
 if not raw or len(raw)>20*1024*1024:raise ValueError('Use media up to 20 MB')
 if mime in ('image/jpeg','image/png'):
  if len(raw)>5*1024*1024:raise ValueError('Use a photo up to 5 MB')
  try:
   with Image.open(io.BytesIO(raw)) as im:
    if im.width*im.height>24000000 or im.format not in ('JPEG','PNG'):raise ValueError()
    actual='image/jpeg' if im.format=='JPEG' else 'image/png';im.verify()
  except Exception as e:raise ValueError('Use a complete JPEG or PNG photo') from e
  return raw,actual
 if mime.startswith('video/'):
  import subprocess,sys
  code='import json,sys;from media_processing import validate_vibe_video;print(json.dumps(validate_vibe_video(sys.stdin.buffer.read())))'
  try:info=json.loads(subprocess.run([sys.executable,'-c',code],input=raw,capture_output=True,cwd=Path(__file__).parent,timeout=25,check=True).stdout)
  except Exception as e:raise ValueError('Use a valid video up to 60 seconds and 20 MB, or split it in the editor') from e
  return raw,info['mime']
 raise ValueError('Vibes support JPEG, PNG, MP4 and WebM')

def post(server,uid,action,b):
 now=int(time.time())
 edited=None
 if action=='publish':
  if b.get('media_id'):
   with server.db() as d:edited=__import__('media_editor').render(d,uid,b['media_id'],'vibe');raw,mime=edited['data'],edited['mime']
  else:raw,mime=validate(b)
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  if action=='privacy':return __import__('vibe_privacy').save(d,uid,b)
  if action=='share':return __import__('vibe_sources').publish(d,uid,b)
  if action=='dismiss_prompt':
   kind=b.get('kind');source=b.get('source')
   if kind not in __import__('vibe_sources').KINDS or not isinstance(source,str) or len(source)>100:raise ValueError('Invalid share prompt')
   d.execute('INSERT OR IGNORE INTO vibe_prompt_dismissals VALUES(?,?,?)',(uid,kind,source));return {'ok':True}
  if action=='milestone_policy':
   __import__('gamebox_core').authorised(d,uid);values=b.get('thresholds');reason=b.get('reason','')
   if not isinstance(values,list) or not 1<=len(values)<=10 or any(type(v)!=int or not 1<=v<=10000 for v in values) or not isinstance(reason,str) or len(reason.strip())<5:raise ValueError('Use 1–10 unique positive ranking thresholds and explain the change')
   old=json.loads(d.execute('SELECT thresholds FROM vibe_milestone_policy WHERE id=1').fetchone()[0]);values=sorted(set(values));d.execute('UPDATE vibe_milestone_policy SET thresholds=? WHERE id=1',(json.dumps(values),));__import__('gamebox_core').event(d,'vibe',uid,'vibe_milestone_policy',old=old,new=values,reason=reason.strip());return {'ok':True}
  if action=='preferences':
   public=b.get('public_hours');private=b.get('private_hours')
   if type(public)!=int or public not in HOURS or type(private)!=int or private not in HOURS:raise ValueError('Choose 12, 24 or 48 hours independently')
   d.execute('INSERT INTO vibe_settings VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET public_hours=excluded.public_hours,private_hours=excluded.private_hours',(uid,public,private));return {'ok':True}
  if action=='publish':
   visibility=b.get('visibility');client=str(b.get('client_id',''));caption=str(b.get('caption','')).strip()
   if visibility not in ('public','private') or not 8<=len(client)<=100 or len(caption)>500:raise ValueError('Invalid Vibe publication')
   digest=hashlib.sha256(raw).hexdigest();old=d.execute('SELECT * FROM vibe_items WHERE uid=? AND client_id=?',(uid,client)).fetchone()
   audience=recipients(d,uid,visibility,b.get('audience',[]))
   if old:
    if old['digest']!=digest or old['visibility']!=visibility or old['caption']!=caption:raise ValueError('A retry cannot replace an existing Vibe')
    if audience!=[r[0] for r in d.execute('SELECT uid FROM vibe_audience WHERE item=? ORDER BY uid',(old['id'],))]:raise ValueError('A retry cannot replace the audience')
    return {'id':old['id'],'expires':old['expires'],'already_published':True}
   if d.execute('SELECT COUNT(*) FROM vibe_items WHERE uid=? AND created>?',(uid,now-3600)).fetchone()[0]>=30:raise ValueError('Limit: 30 Vibe uploads per hour')
   audience=b.get('audience',[])
   if not isinstance(audience,list) or len(audience)>200 or any(not isinstance(x,str) for x in audience):raise ValueError('Choose valid private recipients')
   # Private audiences are explicit and frozen; publishing never creates contacts.
   if visibility=='private':
    if not audience:raise ValueError('Choose at least one existing contact for this Private Vibe')
    import social
    for target in set(audience):
     if not d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,target)).fetchone() or social.blocked(d,uid,target):raise PermissionError('Private Vibe recipients must be your available contacts')
   ident=uuid.uuid4().hex;expires=now+preferences(d,uid)[visibility+'_hours']*3600
   d.execute('INSERT INTO vibe_items VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,uid,visibility,mime,raw,caption,now,expires,client,digest))
   if edited:d.execute('INSERT INTO vibe_media_metadata VALUES(?,?,?,?,?)',(ident,edited['asset'],edited['duration_ms'],edited['start_ms'],edited['end_ms']))
   for target in set(audience) if visibility=='private' else ():
    d.execute('INSERT INTO vibe_audience VALUES(?,?)',(ident,target))
    __import__('account_notifications').add(d,target,'vibe','private','A contact shared a Private Vibe with you.',{'item':ident,'visibility':'private'})
   return {'id':ident,'expires':expires}
  r=item(d,uid,str(b.get('id','')))
  if action=='view':
   if r['uid']!=uid:d.execute('INSERT INTO vibe_views VALUES(?,?,?,?,1) ON CONFLICT(item,uid) DO UPDATE SET last_seen=excluded.last_seen,opens=opens+1',(r['id'],uid,now,now))
   return {'ok':True}
  if action=='react':
   emoji=b.get('emoji')
   if emoji not in EMOJI or r['uid']==uid:raise ValueError('Choose an available reaction to another account')
   prior=d.execute('SELECT emoji FROM vibe_reactions WHERE item=? AND uid=?',(r['id'],uid)).fetchone()
   d.execute('INSERT INTO vibe_reactions VALUES(?,?,?,?) ON CONFLICT(item,uid) DO UPDATE SET emoji=excluded.emoji,created=excluded.created',(r['id'],uid,emoji,now))
   if not prior or prior['emoji']!=emoji:__import__('account_notifications').add(d,r['uid'],'vibe',r['visibility'],'Someone reacted '+emoji+' to your Vibe.',{'item':r['id'],'visibility':r['visibility']})
   return {'ok':True}
  if action=='remove':
   if r['uid']!=uid:raise PermissionError('Only the author can remove this Vibe')
   d.execute('UPDATE vibe_items SET expires=?,media=NULL WHERE id=?',(now,r['id']));return {'ok':True}
  raise ValueError('Unknown Vibe action')

def reply(server,uid,b):
 """Send from the viewer using the existing contact, block and push contracts."""
 ident=str(b.get('id',''));client=b.get('client_id');text=b.get('text')
 if not isinstance(client,str) or not 1<=len(client)<=80 or not isinstance(text,str) or not 1<=len(text.strip())<=3800:raise ValueError('Write a reply of up to 3800 characters')
 text=text.strip()
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  prior=d.execute('SELECT v.item,m.id,m.text,m.recipient FROM vibe_replies v JOIN messages m ON m.id=v.message_id WHERE v.sender=? AND v.client_id=?',(uid,client)).fetchone()
  if prior:
   if prior['item']!=ident or prior['text'].split('\n',1)[-1]!=text:raise ValueError('This retry belongs to another reply')
   __import__('social').ensure(d,uid,prior['recipient'])
   return {'id':prior['id'],'sent':True}
  r=item(d,uid,ident);target=r['uid']
  if target==uid:raise ValueError('Choose a contact’s Vibe to reply')
  if not d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,target)).fetchone():raise PermissionError('Add this account to your chats before replying')
  if d.execute('SELECT 1 FROM messages WHERE sender=? AND client_id=?',(uid,client)).fetchone():raise ValueError('This retry key belongs to another message')
  heading='↪ Reply to your '+('Private Vibe' if r['visibility']=='private' else 'Vibe')
  mid=d.execute('INSERT INTO messages(sender,recipient,text,time,client_id,size) VALUES(?,?,?,?,?,0)',(uid,target,heading+'\n'+text,int(time.time()*1000),client)).lastrowid
  d.execute('INSERT INTO vibe_replies VALUES(?,?,?,?,?)',(mid,ident,r['visibility'],uid,client))
  d.execute('DELETE FROM chat_hidden WHERE owner=? AND peer=?',(uid,target))
 __import__('message_notifications').dispatch(server,mid)
 return {'id':mid,'sent':True}

def purge(server):
 with server.db() as d:
  d.execute('UPDATE vibe_items SET media=NULL WHERE expires<=? AND media IS NOT NULL',(int(time.time()),))
  # Metadata is kept briefly for deduplication, then discarded with view history.
  old=[r[0] for r in d.execute('SELECT id FROM vibe_items WHERE expires<?',(int(time.time())-7*86400,))]
  for ident in old:
   for table in ('vibe_views','vibe_audience','vibe_reactions','vibe_links'):d.execute('DELETE FROM '+table+' WHERE item=?',(ident,))
   d.execute('DELETE FROM vibe_items WHERE id=?',(ident,))
